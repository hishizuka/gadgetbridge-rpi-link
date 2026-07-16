"""Navigation helpers shared by Gadgetbridge parser and host adapters."""

from __future__ import annotations

import re
from typing import Any

from .events import NavigationEvent
from .constants import (
    GADGETBRIDGE_ACTION_TURN_TYPE,
    GADGETBRIDGE_DISTANCE_FACTORS,
    GADGETBRIDGE_HIDDEN_ACTIONS,
)

_DISTANCE_PATTERN = re.compile(
    r"^\s*([+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+))\s*([A-Za-z]+)?\s*$"
)


def gadgetbridge_action_to_turn_type(action: object) -> str:
    if action is None:
        return ""

    normalized = str(action).strip().lower()
    if normalized in GADGETBRIDGE_HIDDEN_ACTIONS:
        return ""

    return GADGETBRIDGE_ACTION_TURN_TYPE.get(normalized, "")


def parse_gadgetbridge_distance(distance: object) -> float | None:
    if distance is None:
        return None

    normalized = str(distance).replace("\u00a0", " ").strip().lower()
    if not normalized:
        return None

    match = _DISTANCE_PATTERN.match(normalized)
    if match is None:
        return None

    try:
        value = float(match.group(1).replace(",", "."))
    except ValueError:
        return None

    if value < 0:
        return None

    unit = match.group(2) or "m"
    factor = GADGETBRIDGE_DISTANCE_FACTORS.get(unit)
    if factor is None:
        return None
    return value * factor


def build_navigation_event(
    payload: dict[str, Any],
    raw_text: str = "",
) -> NavigationEvent:
    """Build a typed navigation event from a raw Gadgetbridge nav payload."""

    action = str(payload.get("action", "")).strip().lower()
    distance_text = str(payload.get("distance", "")).replace("\u00a0", " ").strip()
    instruction = str(payload.get("instr", "")).strip()
    turn_type = gadgetbridge_action_to_turn_type(action)
    distance_m = parse_gadgetbridge_distance(distance_text)
    return NavigationEvent(
        action=action,
        instruction=instruction,
        distance_text=distance_text,
        turn_type=turn_type,
        distance_m=distance_m,
        should_clear=not turn_type or distance_m is None,
        raw=payload,
        raw_text=raw_text,
    )
