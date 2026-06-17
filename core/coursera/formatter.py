"""Markdown and SRT formatting helpers for Coursera subtitles."""

from __future__ import annotations

import datetime as dt
import html
import re

from core.coursera.models import CourseraCourse, CourseraLecture, CourseraSubtitleSegment


def parse_srt(text: str) -> list[CourseraSubtitleSegment]:
    """Parse SRT text into subtitle segments."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    blocks = re.split(r"\n{2,}", normalized)
    segments: list[CourseraSubtitleSegment] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue

        index = 0
        if lines[0].isdigit():
            index = int(lines.pop(0))

        if not lines or "-->" not in lines[0]:
            continue

        start, end = [part.strip() for part in lines.pop(0).split("-->", 1)]
        body = clean_text(" ".join(lines))
        if not body:
            continue
        segments.append(CourseraSubtitleSegment(index=index, start=start, end=end, text=body))
    return segments


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    if value.lower() in {"[music]", "[applause]", "[laughter]"}:
        return ""
    return value


def lecture_segments_to_paragraphs(segments: list[CourseraSubtitleSegment]) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    for segment in segments:
        text = clean_text(segment.text)
        if not text:
            continue
        current.append(text)
        if text.endswith((".", "?", "!", "。", "？", "！", "”", '"')):
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return merge_short_paragraphs(paragraphs)


def merge_short_paragraphs(paragraphs: list[str], min_chars: int = 80) -> list[str]:
    merged: list[str] = []
    for paragraph in paragraphs:
        if merged and len(merged[-1]) < min_chars:
            merged[-1] = f"{merged[-1]} {paragraph}"
        else:
            merged.append(paragraph)
    return merged


def format_duration_ms(duration_ms: int) -> str:
    total = max(0, int(duration_ms / 1000))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def course_to_markdown(course: CourseraCourse, language: str) -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "---",
        f"title: {escape_frontmatter(course.title)}",
        f"platform: Coursera",
        f"course_slug: {course.slug}",
        f"course_id: {course.course_id}",
        f"url: {course.url}",
        f"subtitle_lang: {language or 'auto'}",
        f"lecture_count: {len(course.lectures)}",
        f"created: {now}",
        "---",
        "",
        f"# {course.title}",
        "",
        f"- Platform: Coursera",
        f"- URL: {course.url}",
        f"- Subtitle language: {language or 'auto'}",
        "",
        "## Table of Contents",
        "",
    ]

    for lecture in course.lectures:
        lines.append(f"{lecture.index}. {lecture.module_name} - {lecture.title}")
    lines.append("")

    current_module = ""
    for lecture in course.lectures:
        if lecture.module_name != current_module:
            current_module = lecture.module_name
            lines.extend(["", f"## {current_module}", ""])

        lines.extend([
            f"### {lecture.index}. {lecture.title}",
            "",
            f"- URL: {lecture.url}",
            f"- Duration: {format_duration_ms(lecture.duration_ms)}",
            f"- Subtitle language: {lecture.selected_lang or '-'}",
            "",
        ])

        if lecture.error:
            lines.extend([f"> Download failed: {lecture.error}", ""])
            continue

        paragraphs = lecture_segments_to_paragraphs(lecture.segments)
        if not paragraphs:
            lines.extend(["> No subtitle text found.", ""])
            continue

        lines.extend(paragraphs)
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def escape_frontmatter(value: str) -> str:
    return str(value or "").replace("\n", " ").replace(":", "：")
