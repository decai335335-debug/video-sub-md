"""全局配置"""
import os
from pathlib import Path

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-pro"

# Bilibili SESSDATA（锁定登录状态，无需每次手动输入）
# 留空则每次启动时手动输入，或从环境变量读取
DEFAULT_SESSDATA = os.environ.get("BILIBILI_SESSDATA", "")

# 默认输出目录
DEFAULT_OUTPUT_DIR = Path("E:/Obsidian/主仓库/11-subtitles")

# 平台子目录
BILIBILI_OUTPUT_DIR = DEFAULT_OUTPUT_DIR / "bilibili"
YOUTUBE_OUTPUT_DIR = DEFAULT_OUTPUT_DIR / "Youtube"

# Obsidian Vault 配置（用于生成 obsidian:// 可点击链接）
OBSIDIAN_VAULT_ROOT = Path("E:/Obsidian/主仓库")
OBSIDIAN_VAULT_NAME = "主仓库"

# 并发与限速
MAX_CONCURRENT = 5
REQUEST_DELAY_MIN = 1.0
REQUEST_DELAY_MAX = 3.0

# 请求超时
REQUEST_TIMEOUT = 30

# 重试
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_MIN = 2
RETRY_BACKOFF_MAX = 10

# Bilibili 专用重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1.0

# 文件名安全映射（Windows 保留字符）
FILENAME_BAD_CHARS = '\\/:*?"<>|'
FILENAME_MAX_LENGTH = 150

# Bilibili API
BILI_VIEW_API = "https://api.bilibili.com/x/web-interface/view"
BILI_PLAYER_WBI_API = "https://api.bilibili.com/x/player/wbi/v2"
BILI_PLAYER_V2_API = "https://api.bilibili.com/x/player/v2"
BILI_SERIES_API = "https://api.bilibili.com/x/series/archives"
BILI_COLLECTION_API = "https://api.bilibili.com/x/series/archives"
BILI_FAVLIST_API = "https://api.bilibili.com/x/v3/fav/resource/list"

# 字幕语言优先级（数值越小越优先）
SUBTITLE_LANG_PRIORITY = {
    "zh-cn": 0,
    "zh-hans": 0,
    "zh": 1,
    "ai-zh": 2,
    "ai-zh-cn": 2,
    "en": 10,
    "en-us": 10,
    "en-gb": 10,
    "ai-en": 11,
}

# 默认请求头
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.0 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0"
    ),
    "Referer": "https://www.bilibili.com",
}


def build_headers(cookie: str = "") -> dict:
    """根据是否提供 Cookie 构建请求头。"""
    headers = dict(DEFAULT_HEADERS)
    if cookie:
        safe_cookie = "".join(ch for ch in cookie if ord(ch) < 256)
        headers["Cookie"] = safe_cookie if safe_cookie.lower().startswith("sessdata=") else f"SESSDATA={safe_cookie}"
    return headers
