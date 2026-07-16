"""Outgoing Gadgetbridge message builders."""

from __future__ import annotations

import json
from typing import Any


def build_gps_power_message(enabled: bool) -> str:
    return f'{{t:"gps_power", status:{str(bool(enabled)).lower()}}}'


def build_intent_message(
    action: str,
    target: str = "activity",
    flags: list[str] | None = None,
    package: str | None = None,
    class_name: str | None = None,
    extra: dict[str, Any] | None = None,
    **kwargs: Any,
) -> str:
    message: dict[str, Any] = {
        "t": "intent",
        "target": target,
        "action": action,
    }
    if flags:
        message["flags"] = flags
    if package:
        message["package"] = package
    if class_name:
        message["class"] = class_name
    if extra:
        message["extra"] = extra
    message.update(kwargs)
    return json.dumps(message, separators=(",", ":"))


def build_http_request_message(
    request_id: str,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | dict[str, Any] | list[Any] | None = None,
    insecure: bool = False,
    xpath: str | None = None,
    return_type: str | None = None,
) -> str:
    message: dict[str, Any] = {
        "t": "http",
        "id": str(request_id),
        "url": url,
    }
    method = method.upper()
    if method != "GET":
        message["method"] = method
    if headers:
        message["headers"] = {str(key): str(value) for key, value in headers.items()}
    if body is not None:
        if not isinstance(body, str):
            body = json.dumps(body, separators=(",", ":"))
        message["body"] = body
    if insecure:
        message["insecure"] = True
    if xpath:
        message["xpath"] = xpath
    if return_type:
        message["return"] = return_type
    return json.dumps(message, separators=(",", ":"))
