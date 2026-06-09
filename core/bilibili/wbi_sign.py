"""B站 WBI 签名生成器

B站于2023年底全面启用 WBI (Web Interface) 签名机制，
所有 player/web-interface 等核心接口都需要在请求参数中附加 w_rid 和 wts。

算法来源：B站官方 JS + 社区逆向分析
"""

import hashlib
import time
import urllib.parse
from typing import Dict

import requests


def _get_wbi_keys() -> tuple:
    """获取最新的 WBI  img_key 和 sub_key。"""
    resp = requests.get(
        "https://api.bilibili.com/x/web-interface/nav",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0"
            ),
            "Referer": "https://www.bilibili.com",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json().get("data", {})
    wbi_img = data.get("wbi_img", {})

    img_url = wbi_img.get("img_url", "")
    sub_url = wbi_img.get("sub_url", "")

    # 从 URL 中提取 key，例如：
    # https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b8402c2.png
    # key = "7cd084941338484aae1ad9425b8402c2"
    img_key = img_url.rsplit("/", 1)[-1].split(".")[0] if img_url else ""
    sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0] if sub_url else ""

    return img_key, sub_key


# B站 JS 中的 mixinKey 字符表（固定常量）
_MixinKeyEncTab = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
]


def _get_mixin_key(img_key: str, sub_key: str) -> str:
    """根据 img_key 和 sub_key 生成 mixin_key。"""
    raw = img_key + sub_key
    # 按固定顺序取字符
    mixin_key = "".join(raw[i] for i in _MixinKeyEncTab if i < len(raw))
    return mixin_key[:32]


def sign_params(params: Dict[str, str]) -> Dict[str, str]:
    """为请求参数生成 WBI 签名，返回附加了 w_rid 和 wts 的新参数字典。

    用法：
        params = {"bvid": "BVxxx", "cid": "123"}
        signed = sign_params(params)
        # signed 现在包含 {"bvid": "BVxxx", "cid": "123", "wts": "...", "w_rid": "..."}
    """
    img_key, sub_key = _get_wbi_keys()
    if not img_key or not sub_key:
        raise RuntimeError("无法获取 WBI keys")

    mixin_key = _get_mixin_key(img_key, sub_key)

    # 复制参数并添加 wts（当前时间戳，秒级）
    new_params = dict(params)
    new_params["wts"] = str(int(time.time()))

    # 按 key 排序并 URL 编码，构建查询字符串
    # B站要求对特定字符不做编码（与 urllib.parse.quote 默认行为一致即可）
    sorted_items = sorted(new_params.items(), key=lambda x: x[0])
    query_parts = []
    for k, v in sorted_items:
        # 值需要 URL 编码，但空格转为 %20 而非 +
        encoded_v = urllib.parse.quote(str(v), safe="")
        query_parts.append(f"{k}={encoded_v}")
    query_str = "&".join(query_parts)

    # 拼接 mixin_key 并 MD5
    to_hash = query_str + mixin_key
    w_rid = hashlib.md5(to_hash.encode("utf-8")).hexdigest()

    new_params["w_rid"] = w_rid
    return new_params
