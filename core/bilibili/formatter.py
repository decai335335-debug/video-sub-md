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
    """构建 Markdown 格式字幕。
    
    头部格式与 YouTube 保持一致：
    # 标题
    **频道:** ...
    **链接:** ...
    **语言:** ...
    **时长:** ...
    **提取时间:** ...
    ---
    """
    import datetime
    
    lines = []
    
    # 标题
    if result.page_title and result.page_title != result.title:
        lines.append(f"# {result.title} — {result.page_title}")
    else:
        lines.append(f"# {result.title}")
    lines.append("")
    
    # 元数据（与 YouTube 格式保持一致）
    lines.append(f"**频道:** {result.author or '未知'}  ")
    lines.append(f"**链接:** {result.url or f'https://www.bilibili.com/video/{result.bvid}'}  ")
    lines.append(f"**语言:** {result.language_doc or result.language}  ")
    
    if result.duration:
        m, s = divmod(int(result.duration), 60)
        h, m = divmod(m, 60)
        if h > 0:
            lines.append(f"**时长:** {h:02d}:{m:02d}:{s:02d}")
        else:
            lines.append(f"**时长:** {m:02d}:{s:02d}")
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"**提取时间:** {now}")
    lines.append("")
    
    # 分隔线
    lines.append("---")
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

    # 直接拼接后缀，不使用 with_suffix（避免中文路径下的 bug）
    output_path = Path(str(output_path) + suffix)
    output_path.write_text(content, encoding="utf-8")
    return output_path
