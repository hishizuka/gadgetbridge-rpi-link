"""BlueZ UART host command-line probe."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence
from typing import Any

from gadgetbridge_rpi_link import (
    DEFAULT_HTTP_TEXT_URL,
    FindDeviceEvent,
    GadgetbridgeEvent,
    GadgetbridgeProtocol,
    GadgetbridgeSession,
    GpsActiveQueryEvent,
    GpsFixEvent,
    HttpResponseEvent,
    NavigationEvent,
    NotificationAddEvent,
    NotificationRemoveEvent,
    NotificationUpdateEvent,
    SetTimeEvent,
)
from gadgetbridge_rpi_link.bluez import (
    BluezUnavailableError,
    BluezGadgetbridgeUartServer,
    require_bluez,
)

LOG = logging.getLogger("gadgetbridge-rpi-bluez")


class ExampleHost:
    """Small host adapter wiring BlueZ transport to GadgetbridgeSession."""

    def __init__(
        self,
        product: str,
        output_dir: str,
        auto_gps: bool = False,
    ) -> None:
        self.product = product
        self.output_dir = output_dir
        self.auto_gps = auto_gps
        self.protocol = GadgetbridgeProtocol()
        self.session = GadgetbridgeSession(
            sender=self._send_message,
            protocol=self.protocol,
        )
        self.server: BluezGadgetbridgeUartServer | None = None

    async def start(self) -> None:
        require_bluez()
        self.server = BluezGadgetbridgeUartServer(
            product=self.product,
            on_event=self.handle_event,
            protocol=self.protocol,
        )
        await self.server.start()
        LOG.info("advertising as %s", self.product)

    async def stop(self) -> None:
        if self.server is not None:
            await self.server.stop()
            self.server = None

    async def command_loop(self) -> None:
        LOG.info(
            "commands: t=send Gadgetbridge text, g=GPS ON, "
            "G=voice command intent, h=HTTP download test, q=quit"
        )
        while True:
            command = await asyncio.to_thread(input, "> ")
            command = command.strip()
            if command == "q":
                return
            if command == "t":
                await self.send_text()
            elif command == "g":
                self.gps_on()
            elif command == "G":
                self.session.send_intent(
                    "android.intent.action.VOICE_COMMAND",
                    flags=["FLAG_ACTIVITY_NEW_TASK"],
                )
            elif command == "h":
                await self.download_text_sample()
            elif command:
                LOG.warning("unknown command: %s", command)

    def gps_on(self) -> None:
        LOG.info("requesting Gadgetbridge GPS ON")
        self.session.gps_power(True)

    async def send_text(self) -> None:
        text = await asyncio.to_thread(input, "text> ")
        text = text.strip()
        if not text:
            return
        LOG.info("sending raw text: %s", text)
        await self.session.send_message_async(text)

    async def download_text_sample(self) -> None:
        LOG.info("downloading %s", DEFAULT_HTTP_TEXT_URL)
        path = await self.session.download_http_text_sample(
            output_dir=self.output_dir,
            product=self.product,
        )
        LOG.info("saved HTTP text sample: %s", path)

    def _send_message(self, message: str) -> Any:
        if self.server is None:
            raise RuntimeError("Gadgetbridge service is not running")
        return self.server.send(message)

    def handle_event(self, event: GadgetbridgeEvent) -> None:
        self.session.handle_event(event)

        if isinstance(event, NotificationAddEvent | NotificationUpdateEvent):
            LOG.info("notification: %s - %s", event.title, event.body)
        elif isinstance(event, NotificationRemoveEvent):
            LOG.info("notification removed: %s", event.id)
        elif isinstance(event, FindDeviceEvent) and event.active:
            LOG.info("find-device request received")
        elif isinstance(event, GpsFixEvent):
            LOG.info(
                "gps: lat=%s lon=%s speed_mps=%s",
                event.lat,
                event.lon,
                event.speed_mps,
            )
        elif isinstance(event, GpsActiveQueryEvent):
            LOG.info("gps-active query received")
            if self.auto_gps:
                self.session.gps_power(True)
        elif isinstance(event, NavigationEvent):
            LOG.info("navigation: %s in %sm", event.turn_type, event.distance_m)
        elif isinstance(event, SetTimeEvent):
            LOG.info("set-time UTC: %s", event.utc_time.isoformat())
        elif isinstance(event, HttpResponseEvent):
            LOG.info(
                "HTTP response: id=%s error=%s preview=%r",
                event.request_id,
                event.error,
                _preview(event.response),
            )


def _preview(value: Any, limit: int = 120) -> str | bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value[:limit]
    text = str(value)
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a minimal Gadgetbridge BlueZ UART host probe."
    )
    parser.add_argument("--product", default="gadgetbridge-rpi-link")
    parser.add_argument("--output-dir", default="tmp")
    parser.add_argument("--auto-gps", action="store_true")
    return parser


async def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    host = ExampleHost(
        product=args.product,
        output_dir=args.output_dir,
        auto_gps=args.auto_gps,
    )
    await host.start()
    try:
        await host.command_loop()
    finally:
        await host.stop()


def cli() -> None:
    try:
        asyncio.run(main())
    except BluezUnavailableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    cli()
