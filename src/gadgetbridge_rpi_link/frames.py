"""Frame encoding and decoding for the Gadgetbridge UART transport."""

from __future__ import annotations

import json
from typing import Any

from .constants import DEFAULT_TX_CHUNK_SIZE, F_BYTE_MARKER, L_BYTE_MARKER


class FrameDecoder:
    """Incrementally decode Gadgetbridge UART RX frames."""

    def __init__(self) -> None:
        self._buffer: bytearray | None = None
        self._suspended_buffers: list[bytearray] = []
        self.discarded_frames = 0

    def feed(self, data: bytes | bytearray | memoryview) -> list[str]:
        chunk = bytes(data)
        if not chunk:
            return []

        if chunk[0] == F_BYTE_MARKER:
            if self._buffer:
                if self._is_suspensible_http_frame(self._buffer):
                    self._suspended_buffers.append(self._buffer)
                else:
                    self.discarded_frames += 1
            self._buffer = bytearray(chunk)
        else:
            if self._buffer is None:
                self._buffer = bytearray()
            self._buffer.extend(chunk)

        if self._buffer is not None and chunk[-1] == L_BYTE_MARKER:
            frame = self._buffer.decode("utf-8", "ignore")
            self._buffer = (
                self._suspended_buffers.pop() if self._suspended_buffers else None
            )
            return [frame]

        return []

    @property
    def has_pending_frame(self) -> bool:
        return bool(self._buffer)

    @staticmethod
    def _is_suspensible_http_frame(buffer: bytearray) -> bool:
        return bytes(buffer).startswith(
            (
                bytes([F_BYTE_MARKER]) + b'GB({"t":"http"',
                bytes([F_BYTE_MARKER]) + b"GB({t:\"http\"",
            )
        )


class FrameEncoder:
    """Encode outgoing Gadgetbridge messages into BLE-sized chunks."""

    def __init__(self, chunk_size: int = DEFAULT_TX_CHUNK_SIZE) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self.chunk_size = chunk_size

    def build_payload(self, message: str | dict[str, Any]) -> bytes:
        text = message_to_text(message)
        return (text + "\\n\n").encode("utf-8")

    def encode(self, message: str | dict[str, Any]) -> list[bytes]:
        payload = self.build_payload(message)
        return [
            payload[index : index + self.chunk_size]
            for index in range(0, len(payload), self.chunk_size)
        ]


def message_to_text(message: str | dict[str, Any]) -> str:
    if isinstance(message, str):
        return message
    return json.dumps(message, separators=(",", ":"))
