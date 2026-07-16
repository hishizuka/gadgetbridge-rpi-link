"""Gadgetbridge UART protocol helpers for Raspberry Pi and small Linux devices."""

from .constants import (
    F_BYTE_MARKER,
    L_BYTE_MARKER,
    RX_CHARACTERISTIC_UUID,
    SERVICE_UUID,
    TX_CHARACTERISTIC_UUID,
)
from .events import (
    FindDeviceEvent,
    GadgetbridgeEvent,
    GpsActiveQueryEvent,
    GpsFixEvent,
    HttpResponseEvent,
    NavigationEvent,
    NotificationAddEvent,
    NotificationRemoveEvent,
    NotificationUpdateEvent,
    ParseErrorEvent,
    SetTimeEvent,
    UnknownGBEvent,
    UnknownRawEvent,
)
from .frames import FrameDecoder, FrameEncoder
from .navigation import build_navigation_event
from .parser import GadgetbridgeParser
from .protocol import GadgetbridgeProtocol
from .session import (
    DEFAULT_HTTP_TEXT_URL,
    DEFAULT_SENT_MESSAGE_LIMIT,
    GadgetbridgeSession,
)

__all__ = [
    "DEFAULT_HTTP_TEXT_URL",
    "DEFAULT_SENT_MESSAGE_LIMIT",
    "F_BYTE_MARKER",
    "L_BYTE_MARKER",
    "SERVICE_UUID",
    "RX_CHARACTERISTIC_UUID",
    "TX_CHARACTERISTIC_UUID",
    "FindDeviceEvent",
    "GadgetbridgeEvent",
    "GpsActiveQueryEvent",
    "GpsFixEvent",
    "HttpResponseEvent",
    "NavigationEvent",
    "NotificationAddEvent",
    "NotificationRemoveEvent",
    "NotificationUpdateEvent",
    "ParseErrorEvent",
    "SetTimeEvent",
    "UnknownGBEvent",
    "UnknownRawEvent",
    "FrameDecoder",
    "FrameEncoder",
    "GadgetbridgeParser",
    "GadgetbridgeProtocol",
    "GadgetbridgeSession",
    "build_navigation_event",
]
