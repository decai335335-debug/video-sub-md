"""Bilibili URL 解析器"""

import re
from typing import List, Optional, Tuple
from urllib.parse import urlparse, parse_qs


def extract_bvid(url: str) -> Optional[str]:
    """从 URL 中提取 BV 号。"""
    # https://www.bilibili.com/video/BV1xx411c7mD
    match = re.search(r"/video/(BV[0-9A-Za-z]+)", url)
    if match:
        return match.group(1)

    # 从 ?bvid=BVxxx 中提取
    try:
        parsed = urlparse(url)
        bvid = parse_qs(parsed.query).get("bvid", [""])[0]
        if re.match(r"^BV[0-9A-Za-z]+$", bvid):
            return bvid
    except Exception:
        pass

    return None


def extract_page_index(url: str) -> int:
    """从 URL 中提取分 P 索引。"""
    try:
        parsed = urlparse(url)
        p = parse_qs(parsed.query).get("p", ["1"])[0]
        page = int(p)
        return page if page > 0 else 1
    except Exception:
        return 1


def has_explicit_page_param(url: str) -> bool:
    """判断 URL 是否显式指定了分 P 参数 ?p=N。"""
    try:
        return urlparse(url).query and "p=" in urlparse(url).query
    except Exception:
        return False


def is_collection_url(url: str) -> bool:
    """判断是否为合集/系列/收藏夹等播放列表 URL。"""
    patterns = [
        r"/channel/collectiondetail",
        r"/channel/seriesdetail",
        r"/list/ml",
        r"/list/watchlater",
        r"/list/\d+",
        r"/space\.bilibili\.com/\d+/favlist",
    ]
    return any(re.search(p, url) for p in patterns)


def extract_collection_info(url: str) -> Tuple[str, dict]:
    """
    从播放列表 URL 中提取类型和参数。
    返回: (type, params)
    """
    # UP 主合集 / 系列
    match = re.search(r"channel/(collectiondetail|seriesdetail)\?sid=(\d+)", url)
    if match:
        ctype = match.group(1)
        sid = match.group(2)
        # 尝试提取 mid
        mid_match = re.search(r"space\.bilibili\.com/(\d+)", url)
        mid = mid_match.group(1) if mid_match else ""
        return ("series" if ctype == "seriesdetail" else "collection", {"sid": sid, "mid": mid})

    # 收藏夹 list/ml{mlid}
    match = re.search(r"/list/ml(\d+)", url)
    if match:
        return ("favlist", {"mlid": match.group(1)})

    # 稍后再看
    if "/list/watchlater" in url:
        return ("watchlater", {})

    # 普通 list/{id}
    match = re.search(r"/list/(\d+)", url)
    if match:
        return ("favlist", {"mlid": match.group(1)})

    return ("unknown", {})
