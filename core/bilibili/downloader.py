"""字幕下载主逻辑"""

import random
import time
from pathlib import Path
from typing import List, Optional

import requests

from config import SUBTITLE_LANG_PRIORITY, FILENAME_BAD_CHARS, FILENAME_MAX_LENGTH
from core.bilibili.models import (
    VideoMeta,
    VideoPage,
    SubtitleItem,
    SubtitleResult,
    DownloadResult,
)
from core.bilibili.metadata import fetch_video_meta, fetch_subtitle_tracks
from core.bilibili.formatter import save_subtitle
from core.bilibili.extractor import extract_page_index, extract_bvid


def _safe_filename(name: str) -> str:
    """清理文件名中的非法字符（直接删除），替换 # 为 _ 避免 Obsidian URI 解析问题。"""
    for ch in FILENAME_BAD_CHARS:
        name = name.replace(ch, "")
    # 替换 # 为 _，避免 Obsidian URI 把 #devsetup 解析为标题锚点
    name = name.replace("#", "_")
    name = name.strip(" ._")
    if len(name) > FILENAME_MAX_LENGTH:
        name = name[:FILENAME_MAX_LENGTH].rstrip(" ._")
    return name or "untitled"


def _pick_preferred_track(tracks: List[dict], preferred_lang: Optional[str] = None) -> Optional[dict]:
    """按语言优先级选择最佳字幕轨道。"""
    if not tracks:
        return None

    def priority(track: dict) -> int:
        lan = track.get("lan", "").lower()
        if preferred_lang and lan == preferred_lang.lower():
            return -1
        return SUBTITLE_LANG_PRIORITY.get(lan, 50)

    sorted_tracks = sorted(tracks, key=lambda t: (priority(t), t.get("lan_doc", "")))
    return sorted_tracks[0]


def _fetch_subtitle_body(url: str) -> List[SubtitleItem]:
    """下载字幕 JSON 并解析。"""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    body = data.get("body", [])
    return [
        SubtitleItem(
            from_time=float(item.get("from") or 0),
            to_time=float(item.get("to") or 0),
            content=str(item.get("content") or "").strip(),
        )
        for item in body
    ]


def _get_page_for_url(url: str, meta: VideoMeta) -> VideoPage:
    """根据 URL 中的 p 参数选择正确的分 P。"""
    page_index = extract_page_index(url)

    if meta.pages:
        # 尝试按索引匹配
        if 1 <= page_index <= len(meta.pages):
            return meta.pages[page_index - 1]
        # 尝试按 page 字段匹配
        for page in meta.pages:
            if page.page == page_index:
                return page

    # 回退到默认 cid
    return VideoPage(cid=meta.cid, page=1, part="", duration=meta.duration)


def download_one(
    url: str,
    output_dir: Path,
    fmt: str = "md",
    preferred_lang: Optional[str] = None,
) -> DownloadResult:
    """下载单个 URL 的字幕。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    bvid = extract_bvid(url)
    if not bvid:
        return DownloadResult(
            bvid="",
            cid="",
            status="failed",
            error=f"无法从 URL 提取 BV 号: {url}",
        )

    try:
        meta = fetch_video_meta(bvid)
        page = _get_page_for_url(url, meta)
        cid = page.cid or meta.cid

        if not cid:
            return DownloadResult(
                bvid=bvid,
                cid="",
                title=meta.title,
                status="failed",
                error="无法获取 CID",
            )

        tracks = fetch_subtitle_tracks(bvid=bvid, cid=cid, aid=meta.aid)
        if not tracks:
            return DownloadResult(
                bvid=bvid,
                cid=cid,
                title=meta.title,
                status="skipped",
                error="该视频暂无可用字幕",
            )

        track = _pick_preferred_track(tracks, preferred_lang)
        body = _fetch_subtitle_body(track["subtitle_url"])

        result = SubtitleResult(
            bvid=bvid,
            cid=cid,
            title=meta.title,
            page_title=page.part,
            language=track["lan"],
            language_doc=track["lan_doc"],
            is_ai=track["is_ai"],
            author=meta.author,
            url=url,
            duration=page.duration or meta.duration,
            body=body,
        )

        # 构建文件名
        base_name = _safe_filename(meta.title)
        if page.part and len(meta.pages) > 1:
            base_name = f"{_safe_filename(base_name)}_{_safe_filename(page.part)}"
        if track["lan_doc"]:
            base_name = f"{base_name}_{_safe_filename(track['lan_doc'])}"

        output_path = output_dir / base_name
        filepath = save_subtitle(result, output_path, fmt=fmt)

        return DownloadResult(
            bvid=bvid,
            cid=cid,
            title=meta.title,
            page_title=page.part,
            status="success",
            language=track["lan_doc"] or track["lan"],
            filepath=filepath,
        )

    except Exception as e:
        return DownloadResult(
            bvid=bvid,
            cid=cid if 'cid' in locals() else "",
            title=meta.title if 'meta' in locals() else "",
            status="failed",
            error=str(e),
        )
