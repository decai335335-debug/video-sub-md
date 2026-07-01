#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone audio-to-Markdown fallback for videos without subtitles.

This module is intentionally not wired into main.py yet.

Example:
    python asr_fallback_module.py "https://www.bilibili.com/video/BVxxxx" ^
      --model-path "E:\\Projects\\ai\\sensevoice_ime\\model\\SenseVoiceSmall" ^
      --output "E:\\Obsidian\\主仓库\\11-subtitles\\ASR"
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import typer
import requests
from rich.console import Console

import torch
from yt_dlp import YoutubeDL
from core.naming import add_date_prefix

try:
    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess
except ImportError as exc:  # pragma: no cover - setup issue
    AutoModel = None  # type: ignore[assignment]
    rich_transcription_postprocess = None  # type: ignore[assignment]
    FUNASR_IMPORT_ERROR = exc
else:
    FUNASR_IMPORT_ERROR = None


DEFAULT_MODEL_PATH = Path(r"E:\Projects\ai\sensevoice_ime\model\SenseVoiceSmall")
DEFAULT_OUTPUT_DIR = Path(r"E:\Obsidian\主仓库\11-subtitles\ASR")
WINDOWS_BAD_CHARS = '\\/:*?"<>|#'
TABBIT_PROFILE_DIR = Path.home() / "AppData" / "Local" / "Tabbit Browser" / "User Data" / "Default"

console = Console()
app = typer.Typer(add_completion=False)


@dataclass
class VideoAudio:
    url: str
    video_id: str
    title: str
    uploader: str
    webpage_url: str
    duration: int
    source_path: Path
    wav_path: Path


def safe_filename(value: str, fallback: str = "video") -> str:
    name = str(value or fallback)
    name = re.sub(r"[\u2028\u2029\r\n\t]+", " ", name)
    for char in WINDOWS_BAD_CHARS:
        name = name.replace(char, "_")
    name = re.sub(r"\s+", " ", name).strip(" ._")
    return (name or fallback)[:120]


def format_time(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def extract_bvid(url: str) -> str | None:
    match = re.search(r"\b(BV[0-9A-Za-z]+)", url)
    return match.group(1) if match else None


def is_bilibili_url(url: str) -> bool:
    return "bilibili.com" in url.lower() or bool(extract_bvid(url))


def extract_douyin_video_id(url: str) -> str | None:
    """Extract Douyin video id from /video/{id} or jingxuan?modal_id={id} URLs."""
    if not url:
        return None
    patterns = [
        r"douyin\.com/video/(\d+)",
        r"[?&]modal_id=(\d+)",
        r"[?&]aweme_id=(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    for key in ("modal_id", "aweme_id"):
        values = query.get(key)
        if values and values[0].isdigit():
            return values[0]
    return None


def is_douyin_url(url: str) -> bool:
    return "douyin.com" in (url or "").lower()


def normalize_douyin_url(url: str) -> str:
    """Convert Douyin modal URLs to the direct video URL that yt-dlp can handle."""
    if not is_douyin_url(url):
        return url
    video_id = extract_douyin_video_id(url)
    if video_id:
        return f"https://www.douyin.com/video/{video_id}"
    return url


def normalize_cookies_from_browser(value: Any) -> tuple[Any, ...] | None:
    """Convert browser cookie config to yt-dlp's cookiesfrombrowser tuple."""
    if not value:
        return None
    if isinstance(value, (tuple, list)):
        return tuple(value)

    text = str(value).strip()
    if not text:
        return None

    browser, sep, profile = text.partition(":")
    browser = browser.strip().lower()
    profile = profile.strip() if sep else ""

    if browser == "tabbit":
        tabbit_profile = profile or str(TABBIT_PROFILE_DIR)
        if Path(tabbit_profile).exists():
            return ("chrome", tabbit_profile)
        return ("chrome",)

    if profile:
        return (browser, profile)
    return (browser,)


def _parse_cookie_header(cookie_header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in (cookie_header or "").split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if name:
            cookies[name] = value
    return cookies


def _write_netscape_cookie_file(cookie_header: str, cookie_path: Path, url: str = "") -> None:
    cookies = _parse_cookie_header(cookie_header)
    if "s_v_web_id" not in cookies:
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        web_id = (query.get("verifyFp") or query.get("fp") or [""])[0]
        if web_id:
            cookies["s_v_web_id"] = web_id

    expires = int(time.time()) + 60 * 60 * 24 * 30
    lines = [
        "# Netscape HTTP Cookie File",
        "# Generated by video-sub-md from a raw Douyin Cookie header.",
    ]
    for domain in (".douyin.com", "www.douyin.com", "www-hj.douyin.com"):
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        for name, value in cookies.items():
            lines.append(f"{domain}\t{include_subdomains}\t/\tFALSE\t{expires}\t{name}\t{value}")
    cookie_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _format_filesize(fmt: dict[str, Any]) -> int:
    size = fmt.get("filesize") or fmt.get("filesize_approx") or 0
    try:
        return int(size)
    except (TypeError, ValueError):
        return 0


def select_douyin_format(info: dict[str, Any]) -> str | None:
    """Pick a small audio-capable Douyin format to avoid downloading huge originals."""
    formats = info.get("formats") or []
    candidates: list[dict[str, Any]] = []
    for fmt in formats:
        format_id = str(fmt.get("format_id") or "")
        if not format_id or str(fmt.get("acodec") or "none") == "none":
            continue
        if fmt.get("protocol") in {"mhtml"}:
            continue
        candidates.append(fmt)

    if not candidates:
        return None

    def sort_key(fmt: dict[str, Any]) -> tuple[int, int, int]:
        size = _format_filesize(fmt)
        height = int(fmt.get("height") or 0)
        tbr = int(fmt.get("tbr") or 0)
        return (size if size > 0 else 10**12, height, tbr)

    return str(min(candidates, key=sort_key).get("format_id") or "")


async def _capture_douyin_media_url(url: str, cookie_header: str, timeout_ms: int = 30000) -> tuple[str, str]:
    """Open Douyin in Chromium and capture the signed media URL generated by the page."""
    from playwright.async_api import async_playwright

    cookies = []
    for name, value in _parse_cookie_header(cookie_header).items():
        cookies.append({"name": name, "value": value, "domain": ".douyin.com", "path": "/"})

    media_urls: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            viewport={"width": 1280, "height": 720},
        )
        if cookies:
            await context.add_cookies(cookies)
        page = await context.new_page()

        def on_response(resp: Any) -> None:
            response_url = resp.url
            content_type = resp.headers.get("content-type", "")
            if "video/mp4" not in content_type:
                return
            if "douyinvod.com" not in response_url:
                return
            if response_url not in media_urls:
                media_urls.append(response_url)

        page.on("response", on_response)
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        await page.wait_for_timeout(12000)
        title = await page.title()
        await browser.close()

    if not media_urls:
        raise RuntimeError("Douyin browser fallback did not capture a playable media URL")
    return media_urls[0], title


def download_douyin_audio_via_browser(url: str, work_dir: Path, cookie_header: str) -> VideoAudio:
    """Download Douyin media by letting Chromium generate signed playback URLs."""
    import asyncio

    normalized_url = normalize_douyin_url(url)
    video_id = extract_douyin_video_id(normalized_url) or "douyin"
    media_url, page_title = asyncio.run(_capture_douyin_media_url(normalized_url, cookie_header))
    title = re.sub(r"\s*-\s*抖音\s*$", "", page_title).strip() or video_id

    source_path = work_dir / f"{video_id}.mp4"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.douyin.com/",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    download_stream(media_url, source_path, headers=headers)

    wav_path = work_dir / f"{video_id}.16k.wav"
    convert_to_wav16k(source_path, wav_path)
    duration = probe_media_duration(source_path)

    return VideoAudio(
        url=url,
        video_id=video_id,
        title=title,
        uploader="",
        webpage_url=normalized_url,
        duration=duration,
        source_path=source_path,
        wav_path=wav_path,
    )


def download_bilibili_audio(url: str, work_dir: Path) -> VideoAudio:
    bvid = extract_bvid(url)
    if not bvid:
        raise RuntimeError("Could not find Bilibili BV id in URL")

    page_url = f"https://www.bilibili.com/video/{bvid}/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Referer": page_url,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    view_resp = requests.get(
        "https://api.bilibili.com/x/web-interface/view",
        params={"bvid": bvid},
        headers=headers,
        timeout=30,
    )
    view_resp.raise_for_status()
    view_data = view_resp.json()
    if view_data.get("code") != 0:
        raise RuntimeError(f"Bilibili view API failed: {view_data.get('message') or view_data}")
    data = view_data["data"]
    cid = data["cid"]

    play_resp = requests.get(
        "https://api.bilibili.com/x/player/playurl",
        params={"bvid": bvid, "cid": cid, "fnval": 16, "fourk": 1},
        headers=headers,
        timeout=30,
    )
    play_resp.raise_for_status()
    play_data = play_resp.json()
    if play_data.get("code") != 0:
        raise RuntimeError(f"Bilibili playurl API failed: {play_data.get('message') or play_data}")

    audios = ((play_data.get("data") or {}).get("dash") or {}).get("audio") or []
    if not audios:
        raise RuntimeError("Bilibili playurl API returned no audio stream")
    audio = max(audios, key=lambda item: int(item.get("bandwidth") or 0))
    audio_url = audio.get("baseUrl") or audio.get("base_url")
    if not audio_url:
        raise RuntimeError("Bilibili audio stream has no URL")

    work_dir.mkdir(parents=True, exist_ok=True)
    source_path = work_dir / f"{bvid}.m4s"
    download_stream(audio_url, source_path, headers=headers)
    wav_path = work_dir / f"{bvid}.16k.wav"
    convert_to_wav16k(source_path, wav_path)

    return VideoAudio(
        url=url,
        video_id=bvid,
        title=str(data.get("title") or bvid),
        uploader=str((data.get("owner") or {}).get("name") or ""),
        webpage_url=page_url,
        duration=int(data.get("duration") or 0),
        source_path=source_path,
        wav_path=wav_path,
    )


def download_stream(url: str, output_path: Path, headers: dict[str, str]) -> None:
    with requests.get(url, headers=headers, timeout=60, stream=True) as resp:
        resp.raise_for_status()
        with output_path.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)
    if output_path.stat().st_size == 0:
        raise RuntimeError(f"Downloaded empty audio file: {output_path}")


def download_audio(
    url: str,
    work_dir: Path,
    cookie_file: Path | None = None,
    cookies_from_browser: str = "",
    cookie_header: str = "",
) -> VideoAudio:
    if is_bilibili_url(url):
        return download_bilibili_audio(url, work_dir)

    normalized_url = normalize_douyin_url(url)
    is_douyin = is_douyin_url(normalized_url)
    work_dir.mkdir(parents=True, exist_ok=True)
    ydl_opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": str(work_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.douyin.com/" if is_douyin else "https://www.bilibili.com/",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    }
    if cookie_header and not cookie_file:
        cookie_file = work_dir / "douyin_manual_cookies.txt"
        _write_netscape_cookie_file(cookie_header, cookie_file, url=url)

    if cookie_file:
        ydl_opts["cookiefile"] = str(cookie_file)
    browser_cookies = normalize_cookies_from_browser(cookies_from_browser)
    if browser_cookies:
        ydl_opts["cookiesfrombrowser"] = browser_cookies

    if is_douyin and cookie_header:
        console.print("[yellow]Douyin 使用浏览器抓流模式...[/yellow]")
        return download_douyin_audio_via_browser(normalized_url, work_dir, cookie_header)

    if is_douyin:
        probe_opts = dict(ydl_opts)
        probe_opts["skip_download"] = True
        with YoutubeDL(probe_opts) as ydl:
            probe_info = ydl.extract_info(normalized_url, download=False)
        format_id = select_douyin_format(probe_info)
        if format_id:
            ydl_opts["format"] = format_id

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(normalized_url, download=True)
    except Exception:
        if is_douyin and cookie_header:
            console.print("[yellow]yt-dlp Douyin 提取失败，切换到浏览器抓流模式...[/yellow]")
            return download_douyin_audio_via_browser(normalized_url, work_dir, cookie_header)
        raise

    source_path = find_downloaded_media(info, work_dir)
    video_id = str(info.get("id") or source_path.stem)
    title = str(info.get("title") or video_id)
    wav_path = work_dir / f"{video_id}.16k.wav"
    convert_to_wav16k(source_path, wav_path)

    return VideoAudio(
        url=url,
        video_id=video_id,
        title=title,
        uploader=str(info.get("uploader") or info.get("channel") or ""),
        webpage_url=str(info.get("webpage_url") or url),
        duration=int(info.get("duration") or 0),
        source_path=source_path,
        wav_path=wav_path,
    )


def download_audio_with_browser_cookies(
    url: str,
    work_dir: Path,
    cookie_file: Path | None = None,
    cookies_from_browser: str = "",
    cookie_header: str = "",
) -> VideoAudio:
    return download_audio(
        url=url,
        work_dir=work_dir,
        cookie_file=cookie_file,
        cookies_from_browser=cookies_from_browser,
        cookie_header=cookie_header,
    )


def find_downloaded_media(info: dict[str, Any], work_dir: Path) -> Path:
    candidates: list[Path] = []
    for item in info.get("requested_downloads") or []:
        filepath = item.get("filepath")
        if filepath:
            candidates.append(Path(filepath))
    if info.get("_filename"):
        candidates.append(Path(info["_filename"]))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    media_files = [
        path for path in work_dir.iterdir()
        if path.is_file() and not path.name.endswith(".16k.wav")
    ]
    if not media_files:
        raise RuntimeError("Audio download finished, but no media file was found")
    return max(media_files, key=lambda path: path.stat().st_mtime)


def convert_to_wav16k(source_path: Path, wav_path: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-sample_fmt",
        "s16",
        str(wav_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-1000:]}")


def probe_media_duration(path: Path) -> int:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(float(result.stdout.strip()))
    except Exception:
        pass
    return 0


class SenseVoiceTranscriber:
    def __init__(self, model_path: Path, device: str = "auto") -> None:
        if FUNASR_IMPORT_ERROR is not None or AutoModel is None:
            raise RuntimeError("funasr is not installed. Run: pip install -U funasr modelscope") from FUNASR_IMPORT_ERROR
        self.model_path = Path(model_path)
        self.device = resolve_device(device)
        console.print(f"[dim]Loading SenseVoice model: {self.model_path} ({self.device})[/dim]")
        self.model = AutoModel(
            model=str(self.model_path),
            trust_remote_code=True,
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device=self.device,
        )

    def transcribe(self, wav_path: Path, language: str = "auto") -> tuple[str, list[dict[str, Any]]]:
        res = self.model.generate(
            input=str(wav_path),
            cache={},
            language=language,
            use_itn=True,
            batch_size_s=60,
            merge_vad=True,
            merge_length_s=15,
        )
        if not res:
            return "", []
        text = str(res[0].get("text") or "")
        if rich_transcription_postprocess is not None:
            text = rich_transcription_postprocess(text)
        return clean_sensevoice_text(text), res


def clean_sensevoice_text(text: str) -> str:
    cleaned = re.sub(r"<\|[^|]+?\|>", "", text or "")
    cleaned = re.sub(r"[\U0001F300-\U0001FAFF]", "", cleaned)
    cleaned = cleaned.replace("\u200b", "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def resolve_device(device: str) -> str:
    normalized = (device or "auto").lower()
    if normalized == "auto":
        return "cuda:0" if torch.cuda.is_available() else "cpu"
    return device


def build_markdown(video: VideoAudio, text: str, raw_result: list[dict[str, Any]], model_path: Path, language: str) -> str:
    lines = [
        f"# {video.title}",
        "",
    ]

    timestamped_lines = build_timestamped_asr_lines(video, text, raw_result)
    if timestamped_lines:
        lines.extend(timestamped_lines)
    else:
        lines.append("> ASR returned empty text.")

    return "\n".join(lines)


def timestamp_line(seconds: float, text: str) -> str:
    return f"`{format_time_compact(seconds)}` {text}"


def format_time_compact(seconds: float) -> str:
    total = max(0, int(seconds or 0))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _timestamp_value_to_seconds(value: Any) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return number / 1000.0 if number > 1000 else number


def build_timestamped_asr_lines(video: VideoAudio, text: str, raw_result: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in raw_result or []:
        for sentence in item.get("sentence_info") or []:
            sentence_text = clean_sensevoice_text(str(sentence.get("text") or ""))
            if not sentence_text:
                continue
            start = sentence.get("start")
            if start is None and isinstance(sentence.get("timestamp"), (list, tuple)):
                timestamp = sentence.get("timestamp") or [0]
                start = timestamp[0] if timestamp else 0
            lines.append(timestamp_line(_timestamp_value_to_seconds(start), sentence_text))
    if lines:
        return lines

    paragraphs = split_transcript_text(text)
    if not paragraphs:
        return []
    if video.duration > 0:
        step = max(1.0, video.duration / max(1, len(paragraphs)))
    else:
        step = 5.0
    return [timestamp_line(index * step, paragraph) for index, paragraph in enumerate(paragraphs)]


def split_transcript_text(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[。！？!?\.])\s+", cleaned)
    paragraphs: list[str] = []
    current = ""
    for part in parts:
        if not part:
            continue
        if len(current) + len(part) < 220:
            current = f"{current} {part}".strip()
        else:
            if current:
                paragraphs.append(current)
            current = part
    if current:
        paragraphs.append(current)
    return paragraphs


def write_markdown(output_dir: Path, video: VideoAudio, content: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = add_date_prefix(f"{safe_filename(video.title, video.video_id)}_ASR")
    path = output_dir / f"{base_name}.md"
    counter = 1
    while path.exists():
        path = output_dir / f"{base_name}_{counter}.md"
        counter += 1
    path.write_text(content, encoding="utf-8")
    return path


def cleanup_audio(video: VideoAudio, keep_audio: bool) -> None:
    if keep_audio:
        return
    for path in [video.source_path, video.wav_path]:
        try:
            if path.exists():
                path.unlink()
        except OSError as exc:
            console.print(f"[yellow]Failed to delete temp audio {path}: {exc}[/yellow]")


def process_url(
    url: str,
    transcriber: SenseVoiceTranscriber,
    output_dir: Path,
    language: str,
    keep_audio: bool,
    cookie_file: Path | None,
    cookies_from_browser: str,
    cookie_header: str = "",
) -> Path:
    with tempfile.TemporaryDirectory(prefix="video-sub-md-asr-") as tmp:
        work_dir = Path(tmp)
        console.print(f"[cyan]Downloading audio:[/cyan] {url}")
        video = download_audio_with_browser_cookies(
            url,
            work_dir,
            cookie_file=cookie_file,
            cookies_from_browser=cookies_from_browser,
            cookie_header=cookie_header,
        )
        console.print(f"[cyan]Transcribing:[/cyan] {video.title}")
        text, raw_result = transcriber.transcribe(video.wav_path, language=language)
        md = build_markdown(video, text, raw_result, transcriber.model_path, language)
        output_path = write_markdown(output_dir, video, md)
        cleanup_audio(video, keep_audio=keep_audio)
        if keep_audio:
            preserved_dir = output_dir / "_audio"
            preserved_dir.mkdir(parents=True, exist_ok=True)
            for path in [video.source_path, video.wav_path]:
                if path.exists():
                    shutil.copy2(path, preserved_dir / path.name)
        return output_path


@app.command()
def transcribe(
    urls: list[str] = typer.Argument(..., help="Video URL(s) to transcribe from downloaded audio"),
    model_path: Path = typer.Option(DEFAULT_MODEL_PATH, "--model-path", help="Local SenseVoiceSmall model path"),
    output: Path = typer.Option(DEFAULT_OUTPUT_DIR, "--output", "-o", help="Output directory for Markdown files"),
    language: str = typer.Option("auto", "--lang", "-l", help='SenseVoice language: auto, zh, en, yue, ja, ko, nospeech'),
    device: str = typer.Option("auto", "--device", help="auto, cpu, cuda:0"),
    keep_audio: bool = typer.Option(False, "--keep-audio", help="Keep downloaded and converted audio files"),
    cookie_file: Path | None = typer.Option(None, "--cookies", help="Optional yt-dlp cookies.txt file"),
    cookies_from_browser: str = typer.Option("", "--cookies-from-browser", help="Optional browser cookies for yt-dlp, e.g. chrome, edge"),
) -> None:
    """Download audio, transcribe it with local SenseVoiceSmall, write Markdown, then delete audio."""
    transcriber = SenseVoiceTranscriber(model_path=model_path, device=device)
    success = 0
    failed = 0
    for url in urls:
        try:
            output_path = process_url(
                url=url,
                transcriber=transcriber,
                output_dir=output,
                language=language,
                keep_audio=keep_audio,
                cookie_file=cookie_file,
                cookies_from_browser=cookies_from_browser,
            )
            success += 1
            console.print(f"[green]Saved:[/green] {output_path}")
        except Exception as exc:
            failed += 1
            console.print(f"[red]Failed:[/red] {url}\n{exc}")
    console.print(f"[bold]Done.[/bold] success {success} | failed {failed}")
    if failed:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
