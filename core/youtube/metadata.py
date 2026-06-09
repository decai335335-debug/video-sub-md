"""用 yt-dlp 提取视频元数据（标题、频道、时长、原语言）"""
import yt_dlp
from core.youtube.models import VideoMeta
from core.youtube.extractor import extract_video_id


YDLP_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "extract_flat": False,
}


def fetch_metadata(url: str) -> VideoMeta:
    """获取视频元数据，失败时返回基础信息"""
    video_id = extract_video_id(url)
    try:
        with yt_dlp.YoutubeDL(YDLP_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            return VideoMeta(
                video_id=video_id,
                title=info.get("title", f"Video_{video_id}"),
                channel=info.get("channel", info.get("uploader", "Unknown")),
                url=f"https://www.youtube.com/watch?v={video_id}",
                duration=info.get("duration"),
                original_language=info.get("language"),  # YouTube 标记的原语言
            )
    except Exception:
        # yt-dlp 失败时回退基础信息
        return VideoMeta(
            video_id=video_id,
            title=f"Video_{video_id}",
            channel="Unknown",
            url=f"https://www.youtube.com/watch?v={video_id}",
        )
