"""字幕格式转换"""

from datetime import timedelta
from pathlib import Path
from typing import List

from core.bilibili.models import SubtitleItem, SubtitleResult


def format_time_srt(seconds: float) -> str:
    """将秒数转换为 SRT 时间格式 HH:MM:SS,mmm"""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_time_compact(seconds: float, with_hours: bool = False) -> str:
    """紧凑时间格式，用于 Markdown 行内。"""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0 or with_hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def build_srt(body: List[SubtitleItem]) -> str:
    """构建 SRT 格式字幕。"""
    lines = []
    for idx, item in enumerate(body, start=1):
        text = item.content.strip()
        if not text:
            continue
        lines.append(str(idx))
        lines.append(f"{format_time_srt(item.from_time)} --> {format_time_srt(item.to_time)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def build_txt(body: List[SubtitleItem]) -> str:
    """构建纯文本字幕。"""
    return "\n".join(item.content.strip() for item in body if item.content.strip())


def build_markdown(result: SubtitleResult, include_timestamp: bool = True) -> str:
    """构建 Markdown 格式字幕。"""
    lines = []

    # YAML frontmatter
    lines.append("---")
    lines.append(f'title: "{result.title}"')
    lines.append(f'bvid: "{result.bvid}"')
    lines.append(f'cid: "{result.cid}"')
    lines.append(f'author: ""')
    lines.append(f'subtitle_lang: "{result.language_doc or result.language}"')
    lines.append(f'is_ai: {str(result.is_ai).lower()}')
    lines.append("---")
    lines.append("")

    if result.page_title and result.page_title != result.title:
        lines.append(f"# {result.title} — {result.page_title}")
    else:
        lines.append(f"# {result.title}")
    lines.append("")

    with_hours = any(item.from_time >= 3600 for item in result.body)

    for item in result.body:
        text = item.content.strip()
        if not text:
            continue
        if include_timestamp:
            ts = format_time_compact(item.from_time, with_hours=with_hours)
            lines.append(f"`{ts}` {text}")
        else:
            lines.append(text)

    return "\n".join(lines)


def save_subtitle(result: SubtitleResult, output_path: Path, fmt: str = "md") -> Path:
    """保存字幕到文件。"""
    if fmt == "srt":
        content = build_srt(result.body)
        suffix = ".srt"
    elif fmt == "txt":
        content = build_txt(result.body)
        suffix = ".txt"
    else:
        content = build_markdown(result)
        suffix = ".md"

    output_path = output_path.with_suffix(suffix)
    output_path.write_text(content, encoding="utf-8")
    return output_path
