"""HTTP helpers for the Gadgetbridge HTTP bridge."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BINARY_SUFFIXES = {
    ".bin",
    ".bmp",
    ".dat",
    ".fit",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".mbtiles",
    ".png",
    ".webp",
    ".zip",
}


def encode_http_download_payload(
    payload: Any,
    *,
    binary: bool | None = None,
    encoding: str = "utf-8",
    path: str | Path | None = None,
) -> bytes:
    if isinstance(payload, bytes | bytearray):
        return bytes(payload)
    if isinstance(payload, str):
        if should_write_download_as_binary(path=path, binary=binary):
            return encode_legacy_binary_string(payload, fallback_encoding=encoding)
        return payload.encode(encoding)
    return json.dumps(payload, separators=(",", ":")).encode(encoding)


def should_write_download_as_binary(
    *,
    path: str | Path | None = None,
    binary: bool | None = None,
) -> bool:
    """Choose binary write mode from an explicit override or output suffix."""

    if binary is not None:
        return binary
    if path is None:
        return False
    return Path(path).suffix.lower() in BINARY_SUFFIXES


def encode_legacy_binary_string(
    payload: str,
    *,
    fallback_encoding: str = "utf-8",
) -> bytes:
    if _is_latin1_round_trippable(payload):
        return payload.encode("latin-1")
    return payload.encode(fallback_encoding)


def write_http_download(
    path: str | Path,
    payload: Any,
    *,
    binary: bool | None = None,
    encoding: str = "utf-8",
) -> None:
    data = encode_http_download_payload(
        payload,
        binary=binary,
        encoding=encoding,
        path=path,
    )
    Path(path).write_bytes(data)


def _is_latin1_round_trippable(value: str) -> bool:
    try:
        value.encode("latin-1")
    except UnicodeEncodeError:
        return False
    return True
