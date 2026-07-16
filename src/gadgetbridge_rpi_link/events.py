"""Event models emitted by the Gadgetbridge parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class GadgetbridgeEvent:
    """Marker base class for parsed Gadgetbridge events."""


@dataclass(frozen=True)
class SetTimeEvent(GadgetbridgeEvent):
    timestamp_sec: int
    timezone_offset_hours: float
    utc_time: datetime
    raw_text: str = ""


@dataclass(frozen=True)
class NotificationAddEvent(GadgetbridgeEvent):
    id: str | int | None = None
    source: str = ""
    title: str = ""
    subject: str = ""
    body: str = ""
    sender: str = ""
    reply: bool = False
    raw: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass(frozen=True)
class NotificationUpdateEvent(GadgetbridgeEvent):
    id: str | int | None = None
    source: str = ""
    title: str = ""
    subject: str = ""
    body: str = ""
    sender: str = ""
    reply: bool = False
    raw: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass(frozen=True)
class NotificationRemoveEvent(GadgetbridgeEvent):
    id: str | int | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass(frozen=True)
class FindDeviceEvent(GadgetbridgeEvent):
    active: bool
    raw: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass(frozen=True)
class GpsFixEvent(GadgetbridgeEvent):
    lat: float | None = None
    lon: float | None = None
    alt_m: float | None = None
    speed_mps: float | None = None
    course_deg: float | None = None
    hdop: float | None = None
    fix_mode: int | None = None
    satellites: int | None = None
    timestamp_utc: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass(frozen=True)
class GpsActiveQueryEvent(GadgetbridgeEvent):
    raw: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass(frozen=True)
class NavigationEvent(GadgetbridgeEvent):
    action: str = ""
    instruction: str = ""
    distance_text: str = ""
    turn_type: str = ""
    distance_m: float | None = None
    should_clear: bool = False
    raw: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass(frozen=True)
class HttpResponseEvent(GadgetbridgeEvent):
    request_id: str | None = None
    response: Any = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass(frozen=True)
class UnknownGBEvent(GadgetbridgeEvent):
    message_type: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass(frozen=True)
class UnknownRawEvent(GadgetbridgeEvent):
    raw_text: str


@dataclass(frozen=True)
class ParseErrorEvent(GadgetbridgeEvent):
    raw_text: str
    error: str
    normalized_text: str = ""
