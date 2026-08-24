"""字幕下载引擎：默认下载视频原语言字幕"""
import asyncio
import json
import os
import random
from pathlib import Path
from tempfile import TemporaryDirectory

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
from tenacity import retry, stop_after_attempt, wait_exponential

from core.youtube.models import VideoMeta, DownloadResult
from core.youtube.formatter import transcript_to_md, transcript_to_bilingual_md
from core.naming import add_date_prefix
from config import (
    RETRY_ATTEMPTS,
    RETRY_BACKOFF_MIN,
    RETRY_BACKOFF_MAX,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
    FILENAME_BAD_CHARS,
)


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(min=RETRY_BACKOFF_MIN, max=RETRY_BACKOFF_MAX),
    reraise=True,
)
def _fetch_transcript(video_id: str, lang_codes: list[str]):
    """带重试的字幕获取"""
    return YouTubeTranscriptApi().fetch(video_id, languages=lang_codes).to_raw_data()


def _resolve_language(
    video_id: str,
    preferred_lang: str | None,
    original_language: str | None,
) -> tuple[str, list]:
    """
    决定下载哪种语言的字幕。
    策略：
    1. 如果用户指定了 --lang，优先用它
    2. 如果 yt-dlp 返回了原语言标记，优先找该语言的字幕
    3. 否则，优先下载第一个手动字幕
    4. fallback 到第一个自动生成的字幕
    """
    transcript_list = YouTubeTranscriptApi().list(video_id)

    # 1. 用户指定语言
    if preferred_lang:
        try:
            t = transcript_list.find_transcript([preferred_lang])
            return t.language_code, t.fetch().to_raw_data()
        except NoTranscriptFound:
            pass

    # 2. 优先原语言（如果 yt-dlp 告诉了我们）
    if original_language:
        # 2a. 找原语言的手动字幕
        for t in transcript_list._manually_created_transcripts.values():
            if t.language_code == original_language or t.language_code.startswith(original_language):
                return t.language_code, t.fetch().to_raw_data()
        # 2b. 找原语言的自动生成字幕
        for t in transcript_list._generated_transcripts.values():
            if t.language_code == original_language or t.language_code.startswith(original_language):
                return t.language_code, t.fetch().to_raw_data()

    # 3. 尝试手动字幕（上传者提供的）
    manual = list(transcript_list._manually_created_transcripts.values())
    if manual:
        t = manual[0]
        return t.language_code, t.fetch().to_raw_data()

    # 4. fallback 到第一个自动生成的字幕
    auto = list(transcript_list._generated_transcripts.values())
    if auto:
        t = auto[0]
        return t.language_code, t.fetch().to_raw_data()

    # 5. 翻译字幕（最后手段）
    trans = list(transcript_list._translation_languages)
    if trans:
        if manual:
            t = manual[0].translate(trans[0]["language_code"])
            return t.language_code, t.fetch().to_raw_data()

    raise NoTranscriptFound(video_id)


def _matching_language_keys(
    available: dict,
    language: str | None,
    *,
    prefer_original: bool = False,
) -> list[str]:
    """Return yt-dlp language keys ordered from the closest match outwards."""
    if not language:
        return []

    wanted = language.casefold()
    keys = [key for key in available if key != "live_chat"]
    exact = [key for key in keys if key.casefold() == wanted]
    original = [key for key in keys if key.casefold() == f"{wanted}-orig"]
    variants = [
        key for key in keys
        if key.casefold().startswith(f"{wanted}-") and key not in original
    ]
    return original + exact + variants if prefer_original else exact + variants + original


def _select_ytdlp_subtitle(
    info: dict,
    preferred_lang: str | None,
    original_language: str | None,
) -> tuple[str, dict]:
    """Select one JSON3 subtitle track from yt-dlp metadata."""
    manual = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}

    candidates: list[tuple[dict, str]] = []
    for language in (preferred_lang, original_language):
        candidates.extend(
            (manual, key)
            for key in _matching_language_keys(manual, language)
        )
        candidates.extend(
            (automatic, key)
            for key in _matching_language_keys(
                automatic,
                language,
                prefer_original=language == original_language,
            )
        )

    candidates.extend((manual, key) for key in manual if key != "live_chat")

    original_auto = [
        key for key in automatic
        if key != "live_chat" and key.casefold().endswith("-orig")
    ]
    remaining_auto = [
        key for key in automatic
        if key != "live_chat" and key not in original_auto
    ]
    candidates.extend((automatic, key) for key in original_auto + remaining_auto)

    seen: set[tuple[int, str]] = set()
    for source, language in candidates:
        marker = (id(source), language)
        if marker in seen:
            continue
        seen.add(marker)
        formats = source.get(language) or []
        json3 = next((item for item in formats if item.get("ext") == "json3"), None)
        if json3:
            return language, json3

    raise RuntimeError("yt-dlp 没有找到可下载的 JSON3 字幕")


def _parse_ytdlp_json3(payload: dict) -> list[dict]:
    """Convert YouTube JSON3 events to youtube-transcript-api compatible rows."""
    rows: list[dict] = []
    for event in payload.get("events") or []:
        segments = event.get("segs") or []
        text = "".join(str(segment.get("utf8") or "") for segment in segments).strip()
        if not text:
            continue
        rows.append({
            "text": text,
            "start": float(event.get("tStartMs") or 0) / 1000,
            "duration": float(event.get("dDurationMs") or 0) / 1000,
        })
    if not rows:
        raise RuntimeError("yt-dlp 下载到的 JSON3 字幕没有文本片段")
    return rows


def _resolve_language_with_ytdlp(
    meta: VideoMeta,
    preferred_lang: str | None,
) -> tuple[str, list[dict]]:
    """Use yt-dlp as the second subtitle source without downloading the video."""
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "retries": 3,
    }
    proxy = os.environ.get("VIDEO_SUB_MD_YOUTUBE_PROXY", "").strip()
    if proxy:
        options["proxy"] = proxy
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(meta.url, download=False)
        meta.title = str(info.get("title") or meta.title)
        meta.channel = str(info.get("channel") or info.get("uploader") or meta.channel)
        if info.get("duration") is not None:
            meta.duration = int(info["duration"])
        meta.original_language = str(info.get("language") or meta.original_language or "") or None
        language, subtitle = _select_ytdlp_subtitle(
            info,
            preferred_lang,
            meta.original_language,
        )

        if subtitle.get("data") is not None:
            payload = json.loads(subtitle["data"])
        else:
            with TemporaryDirectory(prefix="video-sub-md-ytdlp-") as temp_dir:
                subtitle_path = Path(temp_dir) / "subtitle.json3"
                download_info = subtitle.copy()
                download_info.setdefault("http_headers", info.get("http_headers"))
                succeeded = ydl.dl(str(subtitle_path), download_info, subtitle=True)
                if succeeded is False or not subtitle_path.exists():
                    raise RuntimeError("yt-dlp 字幕下载失败")
                payload = json.loads(subtitle_path.read_text(encoding="utf-8"))

    return language, _parse_ytdlp_json3(payload)


def _resolve_language_with_fallback(
    meta: VideoMeta,
    preferred_lang: str | None,
) -> tuple[str, list[dict]]:
    """Try youtube-transcript-api first, then fall back to yt-dlp subtitles."""
    # A configured proxy is used for recovery after the transcript API has
    # already identified the direct IP as blocked.  yt-dlp can still retrieve
    # JSON3 captions through that route, while another direct API call only
    # adds delay and triggers more blocking.
    if os.environ.get("VIDEO_SUB_MD_YOUTUBE_PROXY", "").strip():
        return _resolve_language_with_ytdlp(meta, preferred_lang)
    try:
        return _resolve_language(meta.video_id, preferred_lang, meta.original_language)
    except Exception as transcript_error:
        try:
            return _resolve_language_with_ytdlp(meta, preferred_lang)
        except Exception as ytdlp_error:
            if isinstance(
                transcript_error,
                (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable),
            ):
                raise transcript_error
            raise RuntimeError(
                "youtube-transcript-api 失败；"
                f"yt-dlp 字幕兜底也失败: {ytdlp_error}；"
                f"原始错误: {transcript_error}"
            ) from transcript_error


def _safe_filename(title: str, video_id: str) -> str:
    """生成安全的文件名，删除 Windows 保留字符，替换 # 为 _ 避免 Obsidian URI 解析问题"""
    safe = title.strip()
    for ch in FILENAME_BAD_CHARS:
        safe = safe.replace(ch, "")
    # 替换 # 为 _，避免 Obsidian URI 把 #devsetup 解析为标题锚点
    safe = safe.replace("#", "_")
    # 限制长度，保留空间给 ID 后缀
    safe = safe[:80].strip("._")
    if not safe:
        safe = video_id
    return safe


def download_one(
    meta: VideoMeta,
    output_dir: Path,
    preferred_lang: str | None = None,
) -> DownloadResult:
    """下载单个视频并保存为 Markdown"""
    try:
        lang_code, raw_data = _resolve_language_with_fallback(meta, preferred_lang)

        # 转换为 Markdown
        md_content = transcript_to_md(meta, raw_data, lang_code)

        # 生成文件名：优先用标题，重名则加 ID
        base_name = add_date_prefix(_safe_filename(meta.title, meta.video_id))
        filepath = output_dir / f"{base_name}.md"
        counter = 1
        while filepath.exists():
            filepath = output_dir / f"{base_name}_{meta.video_id[:6]}_{counter}.md"
            counter += 1

        output_dir.mkdir(parents=True, exist_ok=True)
        filepath.write_text(md_content, encoding="utf-8")

        return DownloadResult(
            video_id=meta.video_id,
            title=meta.title,
            status="success",
            language=lang_code,
            filepath=filepath,
        )

    except TranscriptsDisabled:
        return DownloadResult(
            video_id=meta.video_id, title=meta.title, status="disabled",
            error="字幕被创作者禁用",
        )
    except NoTranscriptFound:
        return DownloadResult(
            video_id=meta.video_id, title=meta.title, status="no_subtitle",
            error="无可用字幕（建议用 Whisper 转录音频）",
        )
    except VideoUnavailable:
        return DownloadResult(
            video_id=meta.video_id, title=meta.title, status="unavailable",
            error="视频不可用（私有/删除/地区限制）",
        )
    except Exception as e:
        return DownloadResult(
            video_id=meta.video_id, title=meta.title, status="error",
            error=str(e),
        )


async def download_with_delay(
    meta: VideoMeta,
    output_dir: Path,
    preferred_lang: str | None = None,
) -> DownloadResult:
    """带随机延迟的异步下载包装（不阻塞事件循环）"""
    await asyncio.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
    # download_one 内部有同步网络请求，放到线程池执行
    return await asyncio.to_thread(download_one, meta, output_dir, preferred_lang)


def download_bilingual_one(
    meta: VideoMeta,
    output_dir: Path,
) -> DownloadResult:
    """下载中英双语字幕并保存为 Markdown（每句英文下跟中文）"""
    try:
        transcript_list = YouTubeTranscriptApi().list(meta.video_id)

        # 1. 找英文原字幕（优先手动，其次自动生成）
        en_transcript = None
        for t in transcript_list._manually_created_transcripts.values():
            if t.language_code == "en" or t.language_code.startswith("en"):
                en_transcript = t
                break
        if not en_transcript:
            for t in transcript_list._generated_transcripts.values():
                if t.language_code == "en" or t.language_code.startswith("en"):
                    en_transcript = t
                    break
        if not en_transcript:
            raise NoTranscriptFound(f"{meta.video_id}: 无可用英文字幕")

        en_data = en_transcript.fetch().to_raw_data()
        en_lang = en_transcript.language_code

        # 2. 获取中文翻译
        zh_data = None
        zh_lang = None

        # 2a. 直接找中文字幕
        for code in ["zh-Hans", "zh-CN", "zh"]:
            for t in transcript_list._manually_created_transcripts.values():
                if t.language_code == code:
                    zh_data = t.fetch().to_raw_data()
                    zh_lang = t.language_code
                    break
            if zh_data:
                break
            for t in transcript_list._generated_transcripts.values():
                if t.language_code == code:
                    zh_data = t.fetch().to_raw_data()
                    zh_lang = t.language_code
                    break
            if zh_data:
                break

        # 2b. 通过翻译获取
        if not zh_data and en_transcript.is_translatable:
            for code in ["zh-Hans", "zh-CN", "zh"]:
                try:
                    zh_trans = en_transcript.translate(code)
                    zh_data = zh_trans.fetch().to_raw_data()
                    zh_lang = zh_trans.language_code
                    break
                except Exception:
                    continue

        if not zh_data:
            raise NoTranscriptFound(f"{meta.video_id}: 无可用中文字幕")

        # 3. 格式化为双语 Markdown
        md_content = transcript_to_bilingual_md(meta, en_data, zh_data, en_lang, zh_lang)

        # 4. 保存
        base_name = add_date_prefix(_safe_filename(meta.title, meta.video_id) + "_双语")
        filepath = output_dir / f"{base_name}.md"
        counter = 1
        while filepath.exists():
            filepath = output_dir / f"{base_name}_{meta.video_id[:6]}_{counter}.md"
            counter += 1

        output_dir.mkdir(parents=True, exist_ok=True)
        filepath.write_text(md_content, encoding="utf-8")

        return DownloadResult(
            video_id=meta.video_id,
            title=meta.title,
            status="success",
            language=f"{en_lang}+{zh_lang}",
            filepath=filepath,
        )

    except TranscriptsDisabled:
        return DownloadResult(
            video_id=meta.video_id, title=meta.title, status="disabled",
            error="字幕被创作者禁用",
        )
    except NoTranscriptFound:
        return DownloadResult(
            video_id=meta.video_id, title=meta.title, status="no_subtitle",
            error="无可用中英双语字幕",
        )
    except VideoUnavailable:
        return DownloadResult(
            video_id=meta.video_id, title=meta.title, status="unavailable",
            error="视频不可用（私有/删除/地区限制）",
        )
    except Exception as e:
        return DownloadResult(
            video_id=meta.video_id, title=meta.title, status="error",
            error=str(e),
        )


async def download_bilingual_with_delay(
    meta: VideoMeta,
    output_dir: Path,
) -> DownloadResult:
    """带随机延迟的异步双语下载包装"""
    await asyncio.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
    return await asyncio.to_thread(download_bilingual_one, meta, output_dir)
