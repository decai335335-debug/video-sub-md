"""将字幕 JSON 转为 Markdown（无时间轴）"""
import datetime
from core.youtube.models import VideoMeta


# 自动生成的噪音标签，直接丢弃
NOISE_TAGS = {"[Music]", "[music]", "[Music Playing]", "[音楽]", "[Music]"}


def _clean_text(text: str) -> str:
    """清理并返回有效文本，噪音标签返回空字符串"""
    text = text.strip()
    if not text or text in NOISE_TAGS:
        return ""
    return text


def _merge_paragraphs(paragraphs: list[str]) -> list[str]:
    """合并过短的段落（小于 40 字符的并入上一段）"""
    merged = []
    for para in paragraphs:
        if merged and len(merged[-1]) < 40:
            merged[-1] += " " + para
        else:
            merged.append(para)
    return merged


def _build_header(meta: VideoMeta, lang_code: str) -> str:
    """构建 Markdown 头部元数据"""
    duration_str = ""
    if meta.duration:
        m, s = divmod(meta.duration, 60)
        h, m = divmod(m, 60)
        duration_str = f"**时长:** {h:02d}:{m:02d}:{s:02d}\n"

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""# {meta.title}

**频道:** {meta.channel}  
**链接:** {meta.url}  
**语言:** {lang_code}  
{duration_str}**提取时间:** {now}

---

"""


def transcript_to_md(meta: VideoMeta, transcript: list[dict], lang_code: str) -> str:
    """
    将 youtube-transcript-api 返回的 JSON 数组转为 Markdown。
    无时间轴，按语义分段。
    """
    paragraphs = []
    current_sentences = []

    for seg in transcript:
        text = _clean_text(seg.get("text", ""))
        if not text:
            continue

        current_sentences.append(text)

        # 遇到句子结束符，尝试分段
        if text.endswith((".", "?", "!", "。", "？", "！", '"', "'")):
            paragraphs.append(" ".join(current_sentences))
            current_sentences = []

    if current_sentences:
        paragraphs.append(" ".join(current_sentences))

    merged = _merge_paragraphs(paragraphs)
    body = "\n\n".join(merged)

    return _build_header(meta, lang_code) + body


def transcript_to_bilingual_md(
    meta: VideoMeta,
    en_transcript: list[dict],
    zh_transcript: list[dict],
    en_lang: str,
    zh_lang: str,
) -> str:
    """
    将英中双语字幕转为 Markdown。
    每句英文下面紧跟中文翻译，无时间轴。
    如果两句字幕数量不一致，以较短的为准。
    """
    pairs = []
    min_len = min(len(en_transcript), len(zh_transcript))

    for i in range(min_len):
        en_text = _clean_text(en_transcript[i].get("text", ""))
        zh_text = _clean_text(zh_transcript[i].get("text", ""))

        if not en_text:
            continue

        # 跳过纯噪音片段
        if en_text in NOISE_TAGS and (not zh_text or zh_text in NOISE_TAGS):
            continue

        # 合并连续短句（如果上一段很短，合并到同一段）
        if pairs and len(pairs[-1][0]) < 60:
            pairs[-1] = (pairs[-1][0] + " " + en_text, pairs[-1][1] + " " + zh_text)
        else:
            pairs.append((en_text, zh_text))

    # 构建 body：每段英文 + 空行 + 中文
    paragraphs = []
    for en, zh in pairs:
        paragraphs.append(f"{en}\n\n{zh}")

    body = "\n\n".join(paragraphs)

    duration_str = ""
    if meta.duration:
        m, s = divmod(meta.duration, 60)
        h, m = divmod(m, 60)
        duration_str = f"**时长:** {h:02d}:{m:02d}:{s:02d}\n"

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""# {meta.title}

**频道:** {meta.channel}  
**链接:** {meta.url}  
**语言:** {en_lang} + {zh_lang}（双语）  
{duration_str}**提取时间:** {now}

---

{body}
"""
