"""Pydantic 数据模型"""

from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class SubtitleTrack(BaseModel):
    """字幕轨道"""
    id: str = ""
    lan: str = ""
    lan_doc: str = ""
    subtitle_url: str = ""
    is_ai: bool = False


class VideoPage(BaseModel):
    """视频分 P"""
    cid: str
    page: int = 1
    part: str = ""
    duration: float = 0.0


class VideoMeta(BaseModel):
    """Bilibili 视频元数据"""
    bvid: str
    aid: str = ""
    cid: str = ""  # 默认 cid（第一 P）
    title: str = ""
    author: str = ""
    description: str = ""
    upload_date: str = ""
    duration: float = 0.0
    pages: List[VideoPage] = Field(default_factory=list)


class SubtitleItem(BaseModel):
    """单条字幕"""
    from_time: float = Field(0.0, alias="from")
    to_time: float = Field(0.0, alias="to")
    content: str = ""

    class Config:
        populate_by_name = True


class SubtitleResult(BaseModel):
    """字幕下载结果"""
    bvid: str
    cid: str
    title: str
    page_title: str = ""
    language: str = ""
    language_doc: str = ""
    is_ai: bool = False
    body: List[SubtitleItem]


class DownloadTask(BaseModel):
    """下载任务"""
    url: str
    output_dir: Path


class DownloadResult(BaseModel):
    """单次下载结果"""
    bvid: str
    cid: str
    title: str = ""
    status: str  # success / skipped / failed
    language: str = ""
    filepath: Optional[Path] = None
    error: str = ""


class BatchReport(BaseModel):
    """批量报告"""
    total: int = 0
    success: int = 0
    skipped: int = 0
    failed: int = 0
    results: List[DownloadResult] = Field(default_factory=list)
