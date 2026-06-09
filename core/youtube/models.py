"""Pydantic 数据模型"""
from pathlib import Path
from typing import Optional, Literal
from pydantic import BaseModel, Field


class DownloadTask(BaseModel):
    """单个下载任务：视频链接 + 目标输出目录"""
    url: str
    output_dir: Path


class VideoMeta(BaseModel):
    """视频元数据"""
    video_id: str
    title: str
    channel: str
    url: str
    duration: Optional[int] = None  # 秒
    original_language: Optional[str] = None  # 视频原语言，如 'en', 'zh'


class SubtitleSegment(BaseModel):
    """单条字幕片段"""
    text: str
    start: float
    duration: float


class DownloadResult(BaseModel):
    """单个视频的下载结果"""
    video_id: str
    title: str
    status: Literal["success", "no_subtitle", "disabled", "unavailable", "error"]
    language: Optional[str] = None
    filepath: Optional[Path] = None
    error: Optional[str] = None


class BatchReport(BaseModel):
    """批次报告"""
    total: int
    success: int
    failed: int
    results: list[DownloadResult]
