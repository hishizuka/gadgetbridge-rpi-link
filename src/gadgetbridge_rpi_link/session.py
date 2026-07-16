"""Stateful Gadgetbridge session helpers."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from .events import GadgetbridgeEvent, HttpResponseEvent
from .http import write_http_download
from .outgoing import (
    build_gps_power_message,
    build_http_request_message,
    build_intent_message,
)
from .protocol import GadgetbridgeProtocol

Sender = Callable[[str], Any | Awaitable[Any]]
DEFAULT_HTTP_TEXT_URL = "https://pur3.co.uk/hello.txt"
DEFAULT_SENT_MESSAGE_LIMIT = 0


class GadgetbridgeSession:
    """Manage outgoing messages and pending Gadgetbridge HTTP requests."""

    def __init__(
        self,
        sender: Sender | None = None,
        protocol: GadgetbridgeProtocol | None = None,
        sent_message_limit: int | None = DEFAULT_SENT_MESSAGE_LIMIT,
    ) -> None:
        if sent_message_limit is not None and sent_message_limit < 0:
            raise ValueError("sent_message_limit must be >= 0 or None")
        self.sender = sender
        self.protocol = protocol or GadgetbridgeProtocol()
        self.sent_message_limit = sent_message_limit
        self.sent_messages: list[str] = []
        self._http_request_id = 0
        self._http_pending: dict[str, asyncio.Future[dict[str, Any]]] = {}

    def feed_rx(self, chunk: bytes | bytearray | memoryview) -> list[GadgetbridgeEvent]:
        events = self.protocol.feed_rx(chunk)
        for event in events:
            self.handle_event(event)
        return events

    def handle_event(self, event: GadgetbridgeEvent) -> None:
        if isinstance(event, HttpResponseEvent):
            self._complete_http_request(event)

    def send_message(self, message: str) -> Any:
        self.sent_messages.append(message)
        self._trim_sent_messages()
        if self.sender is None:
            return None
        return self.sender(message)

    async def send_message_async(self, message: str) -> Any:
        result = self.send_message(message)
        if inspect.isawaitable(result):
            return await result
        return result

    def gps_power(self, enabled: bool) -> Any:
        return self.send_message(build_gps_power_message(enabled))

    async def gps_power_async(self, enabled: bool) -> Any:
        return await self.send_message_async(build_gps_power_message(enabled))

    def send_intent(self, action: str, target: str = "activity", **kwargs: Any) -> Any:
        return self.send_message(build_intent_message(action, target=target, **kwargs))

    def _next_http_request_id(self) -> str:
        self._http_request_id += 1
        return str(self._http_request_id)

    async def request_http(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | dict[str, Any] | list[Any] | None = None,
        timeout: float = 30,
        insecure: bool = False,
        xpath: str | None = None,
        return_type: str | None = None,
    ) -> dict[str, Any]:
        if self.sender is None:
            raise RuntimeError("GadgetbridgeSession has no sender")

        loop = asyncio.get_running_loop()
        request_id = self._next_http_request_id()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._http_pending[request_id] = future

        message = build_http_request_message(
            request_id=request_id,
            url=url,
            method=method,
            headers=headers,
            body=body,
            insecure=insecure,
            xpath=xpath,
            return_type=return_type,
        )
        try:
            await self.send_message_async(message)
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            pending = self._http_pending.get(request_id)
            if pending is future:
                self._http_pending.pop(request_id, None)

    async def request_http_json(self, *args: Any, **kwargs: Any) -> Any:
        response = await self.request_http(*args, **kwargs)
        payload = response.get("resp")
        if payload in (None, ""):
            return None
        if isinstance(payload, bytes | bytearray):
            payload = bytes(payload).decode("utf-8")
        return json.loads(payload)

    async def download_http_file(
        self,
        url: str,
        save_path: str | Path,
        headers: dict[str, str] | None = None,
        method: str = "GET",
        body: str | dict[str, Any] | list[Any] | None = None,
        timeout: float = 120,
        insecure: bool = False,
        binary: bool | None = None,
        encoding: str = "utf-8",
    ) -> int:
        """Download an HTTP response payload and return 200 after a successful write.

        The return value is a success sentinel for the local write path, not a
        Gadgetbridge-side HTTP status code.
        """

        response = await self.request_http(
            url,
            method=method,
            headers=headers,
            body=body,
            timeout=timeout,
            insecure=insecure,
        )
        await asyncio.to_thread(
            write_http_download,
            save_path,
            response.get("resp", ""),
            binary=binary,
            encoding=encoding,
        )
        return 200

    async def download_http_text_sample(
        self,
        output_dir: str | Path = "tmp",
        product: str = "gadgetbridge-rpi-link",
        url: str = DEFAULT_HTTP_TEXT_URL,
    ) -> str:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        save_path = output_path / (
            f"gadgetbridge_http_text_" f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        await self.download_http_file(
            url,
            save_path,
            headers={"User-Agent": product},
            timeout=30,
            binary=False,
        )
        return str(save_path)

    async def download_http_files(
        self,
        urls: Iterable[str],
        save_paths: Iterable[str | Path],
        headers: dict[str, str] | None = None,
        methods: Iterable[str] | None = None,
        bodies: Iterable[str | dict[str, Any] | list[Any] | None] | None = None,
        timeout: float = 120,
        limit: int | None = None,
        insecure: bool = False,
        binary: bool | None = None,
        encoding: str = "utf-8",
    ) -> list[int]:
        """Download multiple HTTP payloads.

        Each result is 200 when the corresponding local write succeeds and -1
        when that item raises an exception. Cancellation still propagates.
        """

        url_list = list(urls)
        save_path_list = list(save_paths)
        if len(url_list) != len(save_path_list):
            raise ValueError(
                "save_paths length mismatch: "
                f"expected {len(url_list)}, got {len(save_path_list)}"
            )

        method_list = _normalize_batch_values("methods", methods, len(url_list), "GET")
        body_list = _normalize_batch_values("bodies", bodies, len(url_list), None)
        semaphore = asyncio.Semaphore(max(1, limit or len(url_list) or 1))

        async def _download_one(
            url: str,
            save_path: str | Path,
            method: str,
            request_body: str | dict[str, Any] | list[Any] | None,
        ) -> int:
            async with semaphore:
                try:
                    return await self.download_http_file(
                        url,
                        save_path,
                        headers=headers,
                        method=method,
                        body=request_body,
                        timeout=timeout,
                        insecure=insecure,
                        binary=binary,
                        encoding=encoding,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    return -1

        return await asyncio.gather(
            *[
                _download_one(url, save_path, method, request_body)
                for url, save_path, method, request_body in zip(
                    url_list,
                    save_path_list,
                    method_list,
                    body_list,
                )
            ]
        )

    def _complete_http_request(self, event: HttpResponseEvent) -> None:
        if event.request_id is None:
            return
        future = self._http_pending.pop(str(event.request_id), None)
        if future is None or future.done():
            return
        if event.error:
            future.set_exception(RuntimeError(event.error))
            return
        future.set_result(dict(event.raw))

    def _trim_sent_messages(self) -> None:
        if self.sent_message_limit is None:
            return
        if self.sent_message_limit == 0:
            self.sent_messages.clear()
            return
        over_limit = len(self.sent_messages) - self.sent_message_limit
        if over_limit > 0:
            del self.sent_messages[:over_limit]


def _normalize_batch_values(
    name: str,
    values: Iterable[Any] | None,
    expected_length: int,
    default_value: Any,
) -> list[Any]:
    if values is None:
        return [default_value] * expected_length
    value_list = list(values)
    if len(value_list) != expected_length:
        raise ValueError(
            f"{name} length mismatch: expected {expected_length}, "
            f"got {len(value_list)}"
        )
    return value_list


__all__ = [
    "DEFAULT_HTTP_TEXT_URL",
    "DEFAULT_SENT_MESSAGE_LIMIT",
    "GadgetbridgeSession",
    "Sender",
]
