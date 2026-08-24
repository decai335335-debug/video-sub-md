"""HTTP helpers for Bilibili requests."""

from __future__ import annotations

import os
import socket
import urllib.parse

import requests


def _proxy_url_from_env() -> str:
    for name in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _localhost_proxy_is_alive(proxy_url: str) -> bool:
    parsed = urllib.parse.urlparse(proxy_url)
    host = parsed.hostname or ""
    port = parsed.port
    if host not in {"127.0.0.1", "localhost", "::1"} or not port:
        return True
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


def create_bilibili_session() -> requests.Session:
    """Create a session that uses a live proxy, but bypasses dead local proxies."""
    session = requests.Session()
    proxy_url = _proxy_url_from_env()
    if proxy_url and not _localhost_proxy_is_alive(proxy_url):
        session.trust_env = False
    return session

