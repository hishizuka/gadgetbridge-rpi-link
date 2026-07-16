#!/usr/bin/env python3
"""Set Linux system time from Gadgetbridge setTime events."""

from __future__ import annotations

import argparse
import asyncio
import logging
import subprocess
import sys
from collections.abc import Callable, Sequence
from typing import Any

from gadgetbridge_rpi_link import GadgetbridgeEvent, SetTimeEvent
from gadgetbridge_rpi_link.bluez import (
    BluezGadgetbridgeUartServer,
    BluezUnavailableError,
)

LOG = logging.getLogger("gadgetbridge-set-system-time")
SETTER = Callable[[SetTimeEvent], None]


def build_set_time_command(event: SetTimeEvent) -> list[str]:
    """Build a non-interactive GNU date command for a parsed time event."""

    return [
        "sudo",
        "-n",
        "date",
        "-u",
        "--set",
        event.utc_time.isoformat(),
    ]


def apply_system_time(
    event: SetTimeEvent,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> None:
    """Apply a parsed Gadgetbridge UTC timestamp to the Linux system clock."""

    runner(build_set_time_command(event), check=True)


class SetTimeHandler:
    """Handle only setTime events and optionally update the system clock."""

    def __init__(self, apply: bool, setter: SETTER = apply_system_time) -> None:
        self.apply = apply
        self.setter = setter

    def __call__(self, event: GadgetbridgeEvent) -> None:
        if not isinstance(event, SetTimeEvent):
            return

        LOG.info(
            "setTime received: utc=%s timezone_offset_hours=%s",
            event.utc_time.isoformat(),
            event.timezone_offset_hours,
        )
        if not self.apply:
            LOG.info("dry run: system clock was not changed; pass --apply to update it")
            return

        try:
            self.setter(event)
        except (OSError, subprocess.CalledProcessError) as exc:
            LOG.error("failed to set system time: %s", exc)
        else:
            LOG.info("system clock updated from Gadgetbridge")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Advertise a Gadgetbridge BLE UART service and handle setTime events. "
            "The default is a dry run."
        )
    )
    parser.add_argument("--product", default="gadgetbridge-rpi-link")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="run 'sudo -n date -u --set ...' when a setTime event arrives",
    )
    return parser


async def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    handler = SetTimeHandler(apply=args.apply)
    server = BluezGadgetbridgeUartServer(
        product=args.product,
        on_event=handler,
    )

    await server.start()
    LOG.info("advertising as %s", args.product)
    if not args.apply:
        LOG.info("dry-run mode; restart with --apply to update the system clock")
    try:
        await asyncio.Event().wait()
    finally:
        await server.stop()


def cli() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except BluezUnavailableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    cli()
