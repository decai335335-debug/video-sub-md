"""Douyin URL helpers."""

from __future__ import annotations

import re
import urllib.parse


def is_douyin_url(url: str) -> bool:
    return "douyin.com" in (url or "").lower()


def extract_video_id(url: str) -> str:
    if not url:
        return ""

    for pattern in (
        r"douyin\.com/video/(\d+)",
        r"[?&]modal_id=(\d+)",
        r"[?&]aweme_id=(\d+)",
    ):
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    for key in ("modal_id", "aweme_id"):
        values = query.get(key)
        if values and values[0].isdigit():
            return values[0]
    return ""


def normalize_url(url: str) -> str:
    video_id = extract_video_id(url)
    if video_id:
        return f"https://www.douyin.com/video/{video_id}"
    return url
