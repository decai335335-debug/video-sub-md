"""Data models for Coursera course subtitle downloads."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CourseraSubtitleSegment:
    index: int
    start: str
    end: str
    text: str


@dataclass
class CourseraLecture:
    index: int
    course_id: str
    module_id: str
    module_name: str
    lesson_id: str
    lesson_name: str
    item_id: str
    item_slug: str
    title: str
    url: str
    duration_ms: int = 0
    subtitles: dict[str, str] = field(default_factory=dict)
    selected_lang: str = ""
    segments: list[CourseraSubtitleSegment] = field(default_factory=list)
    error: str = ""


@dataclass
class CourseraCourse:
    slug: str
    course_id: str
    title: str
    url: str
    lectures: list[CourseraLecture]


@dataclass
class CourseraDownloadResult:
    course: CourseraCourse
    output_path: Path
    success_count: int
    skipped_count: int
    failed_count: int
