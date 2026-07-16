"""Parser for Gadgetbridge UART messages."""

from __future__ import annotations

import ast
import base64
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .constants import (
    F_BYTE_MARKER,
    HDOP_CUTOFF_FAIR,
    HDOP_CUTOFF_MODERATE,
    HDOP_UEAE_FACTOR,
    L_BYTE_MARKER,
    NMEA_MODE_2D,
    NMEA_MODE_3D,
    NMEA_MODE_NO_FIX,
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
from .navigation import build_navigation_event


class GadgetbridgeParser:
    """Parse raw Gadgetbridge messages into typed events."""

    _ATOB_SENTINEL_KEY = "__gb_atob__"
    _SET_TIME_RE = re.compile(r"^setTime\((\d+)\);E\.setTimeZone\((\S+)\);")
    _KEY_RE = re.compile(r"([A-Za-z_][\w-]*)\s*:")
    _ATOB_RE = re.compile(r'atob\("([^"]+)"\)')
    _HTTP_RESP_PREFIX_RE = re.compile(
        r'^\s*\{\s*"t"\s*:\s*"http"\s*,\s*'
        r'(?:"id"\s*:\s*"(?P<id>[^"]*)"\s*,\s*)?'
        r'"resp"\s*:\s*"'
    )
    _HTTP_ERR_PREFIX_RE = re.compile(
        r'^\s*\{\s*"t"\s*:\s*"http"\s*,\s*'
        r'(?:"id"\s*:\s*"(?P<id>[^"]*)"\s*,\s*)?'
        r'"err"\s*:\s*"'
    )

    def __init__(self) -> None:
        self.time_offset = timedelta()

    def parse_text(self, raw_message: str) -> list[GadgetbridgeEvent]:
        message = strip_message_markers(raw_message)
        if message.startswith("setTime"):
            return [self._parse_set_time(message, raw_message)]
        if message.startswith("GB("):
            return [self._parse_gb_message(message, raw_message)]
        return [UnknownRawEvent(raw_text=raw_message)]

    def _parse_set_time(self, message: str, raw_message: str) -> GadgetbridgeEvent:
        match = self._SET_TIME_RE.match(message)
        if match is None:
            return ParseErrorEvent(
                raw_text=raw_message,
                error="invalid setTime message",
                normalized_text=message,
            )

        timestamp_sec = int(match.group(1))
        offset_hours = float(match.group(2))
        self.time_offset = timedelta(hours=offset_hours)
        utc_time = datetime.fromtimestamp(timestamp_sec, timezone.utc)
        return SetTimeEvent(
            timestamp_sec=timestamp_sec,
            timezone_offset_hours=offset_hours,
            utc_time=utc_time,
            raw_text=raw_message,
        )

    def _parse_gb_message(self, message: str, raw_message: str) -> GadgetbridgeEvent:
        inner = message[len("GB(") :]
        if inner.endswith(")"):
            inner = inner[:-1]

        try:
            payload = self._parse_jsonish(inner)
        except Exception as exc:
            http_event = self._parse_http_message_fallback(inner, raw_message)
            if http_event is not None:
                return http_event
            return ParseErrorEvent(
                raw_text=raw_message,
                error=f"{type(exc).__name__}: {exc}",
                normalized_text=inner,
            )

        if not isinstance(payload, dict):
            return UnknownGBEvent(raw={}, raw_text=raw_message)

        message_type = payload.get("t")
        if message_type == "notify":
            return self._notification_add(payload, raw_message)
        if message_type == "notify~":
            return self._notification_update(payload, raw_message)
        if message_type == "notify-":
            return NotificationRemoveEvent(
                id=payload.get("id"),
                raw=payload,
                raw_text=raw_message,
            )
        if isinstance(message_type, str) and message_type.startswith("find"):
            return FindDeviceEvent(
                active=bool(payload.get("n", False)),
                raw=payload,
                raw_text=raw_message,
            )
        if message_type == "gps":
            return self._gps_fix(payload, raw_message)
        if message_type == "is_gps_active":
            return GpsActiveQueryEvent(raw=payload, raw_text=raw_message)
        if message_type == "http":
            return self._http_response_or_unknown(payload, raw_message)
        if message_type == "nav":
            return self._navigation(payload, raw_message)

        return UnknownGBEvent(
            message_type=str(message_type) if message_type is not None else None,
            raw=payload,
            raw_text=raw_message,
        )

    def _http_response_or_unknown(
        self,
        payload: dict[str, Any],
        raw_message: str,
    ) -> GadgetbridgeEvent:
        if not any(key in payload for key in ("id", "resp", "err")):
            return UnknownGBEvent(
                message_type="http",
                raw=payload,
                raw_text=raw_message,
            )
        return HttpResponseEvent(
            request_id=str(payload["id"]) if payload.get("id") is not None else None,
            response=payload.get("resp"),
            error=str(payload["err"]) if payload.get("err") else None,
            raw=payload,
            raw_text=raw_message,
        )

    def _parse_jsonish(self, message: str) -> Any:
        normalized = self._normalize_jsonish(message)
        payload = json.loads(normalized, strict=False)
        return self._decode_atob_values(payload)

    def _normalize_jsonish(self, message: str) -> str:
        message = self._quote_unquoted_keys(message)
        return self._replace_atob_expressions(message)

    @classmethod
    def _quote_unquoted_keys(cls, message: str) -> str:
        result: list[str] = []
        index = 0
        in_string = False
        escaped = False

        while index < len(message):
            char = message[index]
            if in_string:
                result.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                index += 1
                continue

            if char == '"':
                in_string = True
                result.append(char)
                index += 1
                continue

            if char in "{,":
                result.append(char)
                index += 1
                while index < len(message) and message[index].isspace():
                    result.append(message[index])
                    index += 1
                match = cls._KEY_RE.match(message, index)
                if match is not None:
                    result.append(f'"{match.group(1)}":')
                    index = match.end()
                continue

            result.append(char)
            index += 1

        return "".join(result)

    @classmethod
    def _replace_atob_expressions(cls, message: str) -> str:
        result: list[str] = []
        index = 0
        in_string = False
        escaped = False

        while index < len(message):
            char = message[index]
            if in_string:
                result.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                index += 1
                continue

            if char == '"':
                in_string = True
                result.append(char)
                index += 1
                continue

            match = cls._ATOB_RE.match(message, index)
            if match is not None:
                result.append(cls._replace_atob_expression(match))
                index = match.end()
                continue

            result.append(char)
            index += 1

        return "".join(result)

    @classmethod
    def _replace_atob_expression(cls, match: re.Match[str]) -> str:
        encoded = match.group(1)
        return f'{{"{cls._ATOB_SENTINEL_KEY}":"{encoded}"}}'

    @classmethod
    def _decode_atob_payload(cls, payload: str) -> str | bytes:
        data = base64.b64decode(payload)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data

    @classmethod
    def _decode_atob_values(cls, payload: Any) -> Any:
        if isinstance(payload, list):
            return [cls._decode_atob_values(value) for value in payload]
        if isinstance(payload, dict):
            if set(payload.keys()) == {cls._ATOB_SENTINEL_KEY}:
                return cls._decode_atob_payload(payload[cls._ATOB_SENTINEL_KEY])
            return {
                key: cls._decode_atob_values(value) for key, value in payload.items()
            }
        return payload

    def _parse_http_message_fallback(
        self,
        message: str,
        raw_message: str,
    ) -> HttpResponseEvent | None:
        normalized = message.strip()
        if not normalized.endswith('"}'):
            return None

        response_match = self._HTTP_RESP_PREFIX_RE.match(normalized)
        error_match = (
            None
            if response_match is not None
            else self._HTTP_ERR_PREFIX_RE.match(normalized)
        )
        match = response_match or error_match
        if match is None:
            return None

        try:
            value = ast.literal_eval('"' + normalized[match.end() : -2] + '"')
        except (SyntaxError, ValueError):
            return None

        request_id = match.group("id")
        response = value if response_match is not None else None
        error = value if error_match is not None else None
        payload = {
            "t": "http",
            "id": str(request_id) if request_id is not None else None,
            "resp": response,
        }
        if error:
            payload["err"] = str(error)
        return HttpResponseEvent(
            request_id=str(request_id) if request_id is not None else None,
            response=response,
            error=str(error) if error else None,
            raw=payload,
            raw_text=raw_message,
        )

    def _notification_add(
        self,
        payload: dict[str, Any],
        raw_message: str,
    ) -> NotificationAddEvent:
        return NotificationAddEvent(
            id=payload.get("id"),
            source=str(payload.get("src", "")),
            title=str(payload.get("title", "")),
            subject=str(payload.get("subject", "")),
            body=str(payload.get("body", "")),
            sender=str(payload.get("sender", "")),
            reply=bool(payload.get("reply", False)),
            raw=payload,
            raw_text=raw_message,
        )

    def _notification_update(
        self,
        payload: dict[str, Any],
        raw_message: str,
    ) -> NotificationUpdateEvent:
        return NotificationUpdateEvent(
            id=payload.get("id"),
            source=str(payload.get("src", "")),
            title=str(payload.get("title", "")),
            subject=str(payload.get("subject", "")),
            body=str(payload.get("body", "")),
            sender=str(payload.get("sender", "")),
            reply=bool(payload.get("reply", False)),
            raw=payload,
            raw_text=raw_message,
        )

    def _gps_fix(self, payload: dict[str, Any], raw_message: str) -> GpsFixEvent:
        hdop = _optional_float(payload.get("hdop"))
        if hdop is not None:
            hdop = hdop / HDOP_UEAE_FACTOR

        fix_mode: int | None = None
        if hdop is not None:
            if hdop < HDOP_CUTOFF_MODERATE:
                fix_mode = NMEA_MODE_3D
            elif hdop < HDOP_CUTOFF_FAIR:
                fix_mode = NMEA_MODE_2D
            else:
                fix_mode = NMEA_MODE_NO_FIX

        speed_mps = _optional_float(payload.get("speed"))
        if speed_mps is not None and speed_mps != 0.0:
            speed_mps = speed_mps / 3.6

        timestamp_utc = None
        time_ms = _optional_int(payload.get("time"))
        if time_ms is not None:
            timestamp_utc = datetime.fromtimestamp(time_ms / 1000, timezone.utc)

        return GpsFixEvent(
            lat=_optional_float(payload.get("lat")),
            lon=_optional_float(payload.get("lon")),
            alt_m=_optional_float(payload.get("alt")),
            speed_mps=speed_mps,
            course_deg=_optional_float(payload.get("course")),
            hdop=hdop,
            fix_mode=fix_mode,
            satellites=_optional_int(payload.get("satellites")),
            timestamp_utc=timestamp_utc,
            raw=payload,
            raw_text=raw_message,
        )

    def _navigation(self, payload: dict[str, Any], raw_message: str) -> NavigationEvent:
        return build_navigation_event(payload, raw_message)


def strip_message_markers(message: str) -> str:
    return message.lstrip(chr(F_BYTE_MARKER)).rstrip(chr(L_BYTE_MARKER))


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
