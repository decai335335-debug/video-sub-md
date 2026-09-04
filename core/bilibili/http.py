"""HTTP helpers for Bilibili requests."""

from __future__ import annotations

import os
import socket
import time
from typing import Any

import requests
import urllib3.util.connection as urllib3_connection


_IPV4_PATCHED = False
TRANSIENT_ERRORS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.SSLError,
)


def _prefer_ipv4() -> None:
    """Avoid long stalls on networks where Bilibili IPv6 resolves but cannot connect."""
    global _IPV4_PATCHED
    if _IPV4_PATCHED:
        return
    if os.environ.get("VIDEO_SUB_MD_BILI_FORCE_IPV4", "1").strip() == "0":
        return
    urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
    _IPV4_PATCHED = True


class BilibiliSession(requests.Session):
    """Requests session with Bilibili-specific proxy and retry defaults."""

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        attempts = int(os.environ.get("VIDEO_SUB_MD_BILI_RETRIES", "3") or "3")
        attempts = max(1, attempts)
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                return super().request(method, url, **kwargs)
            except TRANSIENT_ERRORS as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                time.sleep(min(0.5 * attempt, 2.0))

        assert last_error is not None
        raise last_error


def create_bilibili_session() -> requests.Session:
    """Create a Bilibili session that defaults to direct connections."""
    _prefer_ipv4()
    session = BilibiliSession()
    if os.environ.get("VIDEO_SUB_MD_BILI_USE_PROXY", "").strip() != "1":
        session.trust_env = False
    return session
