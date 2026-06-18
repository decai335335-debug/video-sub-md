"""通用数据模型"""
from pathlib import Path
from typing import Optional
from pydantic import BaseModel


class DownloadResult(BaseModel):
    """通用下载结果"""
    platform: str = ""  # "bilibili" | "youtube"
    source_url: str = ""
    video_id: str = ""
    title: str = ""
    status: str = ""  # success / skipped / failed / error
    language: Optional[str] = None
    filepath: Optional[Path] = None
    error: Optional[str] = None


class BatchReport(BaseModel):
    """批次报告"""
    total: int = 0
    success: int = 0
    failed: int = 0
    results: list[DownloadResult] = []
