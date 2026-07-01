"""Shared file and folder naming helpers."""

from __future__ import annotations

import re
from datetime import datetime


DATE_PREFIX_RE = re.compile(r"^\d{6}_")


def current_date_prefix() -> str:
    """Return the YYMMDD_ prefix used for downloaded artifacts."""
    return datetime.now().strftime("%y%m%d_")


def add_date_prefix(name: str, prefix: str | None = None) -> str:
    """Prefix a file or folder basename with YYMMDD_, unless already prefixed."""
    value = str(name or "").strip()
    if not value:
        value = "untitled"
    if DATE_PREFIX_RE.match(value):
        return value
    return f"{prefix or current_date_prefix()}{value}"
