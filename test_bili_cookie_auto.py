#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test automatic Bilibili SESSDATA discovery without touching main.py.

Order:
1. E:/Projects/ai/video-sub-md/cookies/bilibili.txt
2. Tabbit Browser cookie database
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import ctypes.wintypes
import json
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Iterable

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.bilibili.http import create_bilibili_session


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_COOKIE_FILE = PROJECT_DIR / "cookies" / "bilibili.txt"
DEFAULT_TABBIT_USER_DATA = Path.home() / "AppData" / "Local" / "Tabbit Browser" / "User Data"
DEFAULT_TABBIT_PROFILE = "Default"


@dataclass
class CookieCandidate:
    source: str
    sessdata: str


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _dpapi_decrypt(encrypted: bytes) -> bytes:
    blob_in = DATA_BLOB(len(encrypted), ctypes.cast(ctypes.create_string_buffer(encrypted), ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _load_chromium_key(local_state_path: Path) -> bytes:
    data = json.loads(local_state_path.read_text(encoding="utf-8"))
    encrypted_key = base64.b64decode(data["os_crypt"]["encrypted_key"])
    if encrypted_key.startswith(b"DPAPI"):
        encrypted_key = encrypted_key[5:]
    return _dpapi_decrypt(encrypted_key)


def _decrypt_chromium_cookie(encrypted_value: bytes, key: bytes) -> str:
    if not encrypted_value:
        return ""
    if encrypted_value.startswith((b"v10", b"v11", b"v20")):
        nonce = encrypted_value[3:15]
        ciphertext = encrypted_value[15:]
        return AESGCM(key).decrypt(nonce, ciphertext, None).decode("utf-8", errors="replace")
    return _dpapi_decrypt(encrypted_value).decode("utf-8", errors="replace")


def _extract_sessdata_from_text(text: str) -> str:
    for raw_part in text.replace("\n", ";").split(";"):
        part = raw_part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        if name.strip().lower() == "sessdata":
            return value.strip().replace("\\_", "_")
    return ""


def _read_cookie_file(path: Path) -> CookieCandidate | None:
    if not path.is_file():
        return None

    raw = path.read_text(encoding="utf-8", errors="ignore")
    sessdata = _extract_sessdata_from_text(raw)
    if sessdata:
        return CookieCandidate(str(path), sessdata)

    jar = MozillaCookieJar()
    try:
        jar.load(str(path), ignore_discard=True, ignore_expires=True)
    except Exception:
        return None
    for cookie in jar:
        if cookie.name.lower() == "sessdata" and "bilibili.com" in cookie.domain:
            return CookieCandidate(str(path), str(cookie.value).replace("\\_", "_"))
    return None


def _tabbit_cookie_paths(user_data: Path, profile: str) -> tuple[Path, Path]:
    return (
        user_data / "Local State",
        user_data / profile / "Network" / "Cookies",
    )


def _read_tabbit_cookie_db(user_data: Path, profile: str) -> CookieCandidate | None:
    local_state, cookie_db = _tabbit_cookie_paths(user_data, profile)
    if not local_state.is_file():
        raise FileNotFoundError(f"Tabbit Local State not found: {local_state}")
    if not cookie_db.is_file():
        raise FileNotFoundError(f"Tabbit Cookies DB not found: {cookie_db}")

    key = _load_chromium_key(local_state)
    with tempfile.TemporaryDirectory(prefix="video_sub_md_bili_cookie_") as tmp:
        copied_db = Path(tmp) / "Cookies"
        shutil.copy2(cookie_db, copied_db)
        conn = sqlite3.connect(str(copied_db))
        try:
            rows = conn.execute(
                """
                SELECT host_key, name, value, encrypted_value
                FROM cookies
                WHERE host_key LIKE '%bilibili.com' AND lower(name) = 'sessdata'
                ORDER BY expires_utc DESC
                """
            ).fetchall()
        finally:
            conn.close()

    for host_key, name, value, encrypted_value in rows:
        sessdata = value or _decrypt_chromium_cookie(encrypted_value, key)
        sessdata = str(sessdata or "").strip().replace("\\_", "_")
        if sessdata:
            return CookieCandidate(f"Tabbit:{cookie_db} ({host_key}/{name})", sessdata)
    return None


def discover_candidates(cookie_file: Path, tabbit_user_data: Path, tabbit_profile: str) -> tuple[list[CookieCandidate], list[str]]:
    candidates: list[CookieCandidate] = []
    errors: list[str] = []

    from_file = _read_cookie_file(cookie_file)
    if from_file:
        candidates.append(from_file)

    try:
        from_tabbit = _read_tabbit_cookie_db(tabbit_user_data, tabbit_profile)
        if from_tabbit:
            candidates.append(from_tabbit)
    except PermissionError as exc:
        errors.append(
            "Tabbit Cookie 数据库被系统占用或拒绝读取。"
            f"请完全退出 Tabbit 后再测，或使用 cookies/bilibili.txt。原始错误: {exc}"
        )
    except Exception as exc:
        errors.append(f"Tabbit Cookie 读取失败: {type(exc).__name__}: {exc}")

    return candidates, errors


def mask(value: str) -> str:
    if len(value) <= 12:
        return "*" * len(value)
    return f"{value[:6]}...{value[-6:]}"


def check_sessdata(sessdata: str) -> tuple[bool, str]:
    session = create_bilibili_session()
    resp = session.get(
        "https://api.bilibili.com/x/web-interface/nav",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.bilibili.com/",
            "Cookie": f"SESSDATA={sessdata}",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        return False, str(data.get("message") or data)
    nav = data.get("data") or {}
    uname = nav.get("uname") or nav.get("mid") or "unknown"
    return bool(nav.get("isLogin")), str(uname)


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Bilibili SESSDATA auto discovery.")
    parser.add_argument("--cookie-file", type=Path, default=DEFAULT_COOKIE_FILE)
    parser.add_argument("--tabbit-user-data", type=Path, default=DEFAULT_TABBIT_USER_DATA)
    parser.add_argument("--tabbit-profile", default=DEFAULT_TABBIT_PROFILE)
    args = parser.parse_args()

    print("Bilibili SESSDATA auto-discovery test")
    print(f"cookie file: {args.cookie_file}")
    print(f"tabbit profile: {args.tabbit_user_data / args.tabbit_profile}")
    print()

    candidates, errors = discover_candidates(args.cookie_file, args.tabbit_user_data, args.tabbit_profile)
    for error in errors:
        print(f"[WARN] {error}")

    if not candidates:
        print("[FAIL] 没找到 SESSDATA。请确认 Tabbit 已登录 bilibili.com，或导出 cookies/bilibili.txt。")
        return 1

    for idx, candidate in enumerate(candidates, 1):
        print(f"[{idx}] 来源: {candidate.source}")
        print(f"    SESSDATA: {mask(candidate.sessdata)} ({len(candidate.sessdata)} chars)")
        try:
            ok, message = check_sessdata(candidate.sessdata)
        except Exception as exc:
            print(f"    校验失败: {type(exc).__name__}: {exc}")
            continue
        if ok:
            print(f"    [OK] B站登录有效: {message}")
            return 0
        print(f"    [FAIL] B站未登录/失效: {message}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
