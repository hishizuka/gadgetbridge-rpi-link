"""High-level protocol object combining frame decoding, parsing, and encoding."""

from __future__ import annotations

from typing import Any

from .events import GadgetbridgeEvent
from .frames import FrameDecoder, FrameEncoder
from .parser import GadgetbridgeParser


class GadgetbridgeProtocol:
    """Stateless transport API with stateful time offset parsing."""

    def __init__(
        self,
        parser: GadgetbridgeParser | None = None,
        decoder: FrameDecoder | None = None,
        encoder: FrameEncoder | None = None,
    ) -> None:
        self.parser = parser or GadgetbridgeParser()
        self.decoder = decoder or FrameDecoder()
        self.encoder = encoder or FrameEncoder()

    def feed_rx(self, chunk: bytes | bytearray | memoryview) -> list[GadgetbridgeEvent]:
        events: list[GadgetbridgeEvent] = []
        for frame in self.decoder.feed(chunk):
            events.extend(self.parser.parse_text(frame))
        return events

    def parse_text(self, raw_message: str) -> list[GadgetbridgeEvent]:
        return self.parser.parse_text(raw_message)

    def encode_tx(self, message: str | dict[str, Any]) -> list[bytes]:
        return self.encoder.encode(message)
