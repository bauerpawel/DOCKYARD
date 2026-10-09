"""Validation shared by app definitions, the CLI, and HTML rendering."""

from __future__ import annotations

import base64
import binascii
import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit


def is_valid_slug(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) is not None


def is_web_url(value: object) -> bool:
    """Accept absolute HTTP(S) links without credentials or ambiguous characters."""
    if not isinstance(value, str) or re.search(r"[\s\x00-\x1f\x7f\\]", value):
        return False
    try:
        parts = urlsplit(value)
        return (
            parts.scheme in {"http", "https"}
            and bool(parts.hostname)
            and parts.username is None
            and parts.password is None
            and (parts.port is None or 0 < parts.port <= 65535)
        )
    except ValueError:
        return False


def is_relative_path(value: object) -> bool:
    """Check POSIX and Windows paths consistently, even when running on Linux."""
    if not isinstance(value, str) or not value or re.search(r"[\x00-\x1f\x7f:]", value):
        return False
    path = PurePosixPath(value.replace("\\", "/"))
    return not path.is_absolute() and ".." not in path.parts


def is_image_url(value: object) -> bool:
    """Allow web links and embedded raster logos, never executable data URLs."""
    if is_web_url(value):
        return True
    if not isinstance(value, str) or len(value) > 1024 * 1024:
        return False
    match = re.fullmatch(r"data:image/(png|jpeg|gif|webp);base64,([A-Za-z0-9+/]*={0,2})", value)
    if match is None:
        return False
    try:
        body = base64.b64decode(match[2], validate=True)
    except (ValueError, binascii.Error):
        return False
    return {
        "png": body.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpeg": body.startswith(b"\xff\xd8\xff"),
        "gif": body.startswith((b"GIF87a", b"GIF89a")),
        "webp": body.startswith(b"RIFF") and body[8:12] == b"WEBP",
    }[match[1]]
