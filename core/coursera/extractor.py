"""URL and slug helpers for Coursera."""

from __future__ import annotations

import re
from urllib.parse import urlparse


def extract_course_slug(url_or_slug: str) -> str:
    """Extract the Coursera course slug from a course URL or raw slug."""
    value = (url_or_slug or "").strip()
    if not value:
        raise ValueError("Coursera URL or course slug is empty")

    if "://" not in value and "/" not in value:
        return value

    parsed = urlparse(value)
    match = re.search(r"/learn/([^/?#]+)", parsed.path)
    if match:
        return match.group(1)

    raise ValueError(f"Cannot extract Coursera course slug from: {url_or_slug}")


def build_lecture_url(course_slug: str, item_id: str, item_slug: str) -> str:
    slug = item_slug or item_id
    return f"https://www.coursera.org/learn/{course_slug}/lecture/{item_id}/{slug}"
