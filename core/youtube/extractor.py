"""URL 解析器：从任意 YouTube 链接提取 Video ID"""
import re


YOUTUBE_PATTERNS = [
    # 标准 watch
    r"youtube\.com/watch\?v=([0-9A-Za-z_-]{11})",
    # Shorts
    r"youtube\.com/shorts/([0-9A-Za-z_-]{11})",
    # Embed
    r"youtube\.com/embed/([0-9A-Za-z_-]{11})",
    # Live
    r"youtube\.com/live/([0-9A-Za-z_-]{11})",
    # 短链 youtu.be
    r"youtu\.be/([0-9A-Za-z_-]{11})",
    # 音乐/playlist 里的视频（v= 参数）
    r"[?&]v=([0-9A-Za-z_-]{11})",
]


def extract_video_id(url: str) -> str:
    """从任意 YouTube URL 提取 11 位 Video ID"""
    url = url.strip()
    # 先尝试纯 ID（11位）
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url):
        return url

    for pattern in YOUTUBE_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    raise ValueError(f"无法解析 Video ID: {url}")


def is_playlist_url(url: str) -> bool:
    """判断是否为播放列表链接"""
    return "playlist?list=" in url or "youtube.com/playlist" in url


def is_valid_video_url(url: str) -> bool:
    """判断是否为有效的 YouTube 视频链接（排除搜索页、频道页等）"""
    url = url.strip().lower()
    # 排除搜索结果页
    if "youtube.com/results" in url or "youtube.com/search" in url:
        return False
    # 排除频道页/用户页（非视频页）
    if "/channel/" in url or "/c/" in url or "/user/" in url or "/@" in url:
        return False
    # 必须是能提取出 video_id 的链接
    try:
        extract_video_id(url)
        return True
    except ValueError:
        return False


def filter_video_urls(urls: list[str]) -> list[str]:
    """过滤掉无效链接，返回有效视频/播放列表链接"""
    valid = []
    for u in urls:
        if is_playlist_url(u) or is_valid_video_url(u):
            valid.append(u)
    return valid
