"""Convert YouTube transcript data to Markdown with timestamps."""

import datetime
from html import escape

from core.youtube.models import VideoMeta


NOISE_TAGS = {"[Music]", "[music]", "[Music Playing]", "[音乐]", "[Applause]", "[Laughter]"}


def _clean_text(text: str) -> str:
    text = str(text or "").strip().replace("\n", " ")
    if not text or text in NOISE_TAGS:
        return ""
    return text


def _format_time(seconds: float) -> str:
    total = max(0, int(seconds or 0))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def build_youtube_embed_placeholder(meta: VideoMeta) -> str:
    """Build the Obsidian media embed placeholder for YouTube videos."""
    original_url = meta.url or f"https://www.youtube.com/watch?v={meta.video_id}"
    embed_id = f"youtube-{meta.video_id.lower()}"
    return f'''<div class="media-embed-placeholder" data-embed-id="{escape(embed_id, quote=True)}" data-platform="youtube" data-video-id="{escape(meta.video_id, quote=True)}" data-start-time="" data-is-short="false" data-original-url="{escape(original_url, quote=True)}">
\t\t\t<div class="media-embed-placeholder-content">
\t\t\t\t<div class="media-embed-placeholder-icon">▶</div>
\t\t\t\t<div class="media-embed-placeholder-text">
\t\t\t\t\t<div class="media-embed-placeholder-title">YouTube 视频</div>
\t\t\t\t\t<div class="media-embed-placeholder-desc">滚动文档时将在浮窗播放</div>
\t\t\t\t</div>
\t\t\t\t<button class="media-embed-placeholder-play">▶ 播放</button>
\t\t\t</div>
\t\t</div>'''


def _build_header(meta: VideoMeta, lang_code: str) -> str:
    duration_str = ""
    if meta.duration:
        m, s = divmod(int(meta.duration), 60)
        h, m = divmod(m, 60)
        duration_str = f"**时长:** {h:02d}:{m:02d}:{s:02d}\n"

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""# {meta.title}

**频道:** {meta.channel}  
**链接:** {meta.url}  
**语言:** {lang_code}  
{duration_str}**提取时间:** {now}

{build_youtube_embed_placeholder(meta)}

---

"""


def transcript_to_md(meta: VideoMeta, transcript: list[dict], lang_code: str) -> str:
    """Render each YouTube transcript segment as a timestamped Markdown line."""
    lines = []
    for seg in transcript:
        text = _clean_text(seg.get("text", ""))
        if not text:
            continue
        start = float(seg.get("start") or 0)
        lines.append(f"`{_format_time(start)}` {text}")

    return _build_header(meta, lang_code) + "\n".join(lines)


def transcript_to_bilingual_md(
    meta: VideoMeta,
    en_transcript: list[dict],
    zh_transcript: list[dict],
    en_lang: str,
    zh_lang: str,
) -> str:
    """Render bilingual transcript pairs while keeping the source timestamp."""
    pairs = []
    min_len = min(len(en_transcript), len(zh_transcript))

    for i in range(min_len):
        en_text = _clean_text(en_transcript[i].get("text", ""))
        zh_text = _clean_text(zh_transcript[i].get("text", ""))
        if not en_text:
            continue
        if en_text in NOISE_TAGS and (not zh_text or zh_text in NOISE_TAGS):
            continue
        start = float(en_transcript[i].get("start") or zh_transcript[i].get("start") or 0)
        if zh_text:
            pairs.append(f"`{_format_time(start)}` {en_text}\n{zh_text}")
        else:
            pairs.append(f"`{_format_time(start)}` {en_text}")

    duration_str = ""
    if meta.duration:
        m, s = divmod(int(meta.duration), 60)
        h, m = divmod(m, 60)
        duration_str = f"**时长:** {h:02d}:{m:02d}:{s:02d}\n"

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    body = "\n\n".join(pairs)

    return f"""# {meta.title}

**频道:** {meta.channel}  
**链接:** {meta.url}  
**语言:** {en_lang} + {zh_lang}（双语）  
{duration_str}**提取时间:** {now}

{build_youtube_embed_placeholder(meta)}

---

{body}
"""
