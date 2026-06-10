"""
字幕翻译模块 - 单独调试用
"""
import re
import requests
from pathlib import Path
from typing import Optional

# 默认配置
_DEFAULT_API_KEY = None
_DEFAULT_API_URL = "https://api.deepseek.com/chat/completions"
_DEFAULT_MODEL = "deepseek-v4-flash"


def _force_line_alignment(translated_lines: list, expected_count: int) -> list:
    """强制将 M 行译文对齐为 N 行（处理AI换行拆分或合并的问题）
    
    策略：
    - M > N: 按比例将多余行合并到前面的行中
    - M < N: 用空字符串补齐
    - M == N: 原样返回
    """
    m = len(translated_lines)
    n = expected_count
    
    if m == n:
        return translated_lines
    
    if m > n:
        # 行数过多：AI把一行拆成了多行，需要合并
        result = []
        ratio = m / n
        for i in range(n):
            start = int(i * ratio)
            end = int((i + 1) * ratio) if i < n - 1 else m
            merged = ' '.join(translated_lines[start:end]).strip()
            result.append(merged)
        return result
    else:
        # 行数过少：AI合并了多行，补齐空行（这种情况较少）
        result = translated_lines[:]
        while len(result) < n:
            result.append("")
        return result


def translate_subtitle_with_deepseek(
    subtitle_content: str,
    video_title: str = "",
    api_key: str = None,
    api_url: str = None,
    model: str = None,
    target_chars_per_chunk: int = 1500,
    lines_per_chunk: int = 40,
    max_retries: int = 3,
) -> Optional[str]:
    """调用 DeepSeek Flash API 将字幕翻译为纯中文，支持分段翻译
    
    参数:
        subtitle_content: 字幕内容
        video_title: 视频标题（可选）
        api_key: DeepSeek API 密钥（默认为 None，从环境变量读取）
        api_url: DeepSeek API 地址（默认使用配置值）
        model: 使用的模型（默认使用配置值）
        target_chars_per_chunk: 每段目标字符数
        lines_per_chunk: 每段最大行数
        max_retries: 每段最大重试次数
    
    返回:
        翻译后的中文字幕（按行对应）
    """
    # 使用传入参数或默认配置
    api_key = api_key or _DEFAULT_API_KEY
    api_url = api_url or _DEFAULT_API_URL
    model = model or _DEFAULT_MODEL
    
    if not api_key:
        print("[警告] 未设置 API_KEY，跳过翻译")
        return None

    lines = subtitle_content.strip().split('\n')
    
    # 分离非空行和空行位置
    non_empty_lines = [line for line in lines if line.strip()]
    empty_line_positions = [i for i, line in enumerate(lines) if not line.strip()]
    
    print(f"字幕共 {len(lines)} 行，其中非空行 {len(non_empty_lines)} 行", flush=True)
    
    if not non_empty_lines:
        print("警告: 没有可翻译的内容")
        return None
    
    # 估算每行平均字符数，动态计算每段行数
    total_chars = sum(len(line) for line in non_empty_lines)
    avg_chars_per_line = total_chars / len(non_empty_lines) if non_empty_lines else 100
    
    actual_lines_per_chunk = max(5, int(target_chars_per_chunk / avg_chars_per_line))
    actual_lines_per_chunk = min(actual_lines_per_chunk, lines_per_chunk)
    actual_lines_per_chunk = max(actual_lines_per_chunk, 5)
    
    all_translations = []
    total_chunks = (len(non_empty_lines) + actual_lines_per_chunk - 1) // actual_lines_per_chunk
    
    print(f"将分 {total_chunks} 段翻译", flush=True)
    
    for i in range(0, len(non_empty_lines), actual_lines_per_chunk):
        chunk_lines = non_empty_lines[i:i+actual_lines_per_chunk]
        chunk_text = '\n'.join(chunk_lines)
        chunk_num = i // actual_lines_per_chunk + 1
        
        print(f"翻译进度: {chunk_num}/{total_chunks}", flush=True)
        
        # 给每行加全局连续编号，帮助AI严格按行对应
        global_start_idx = i
        numbered_lines = '\n'.join(f"[{global_start_idx + idx + 1}] {line}" for idx, line in enumerate(chunk_lines))
        expected_count = len(chunk_lines)
        
        prompt = f"""请将以下英文字幕翻译成中文。

输入共 {expected_count} 行，你的输出必须严格为 {expected_count} 行，绝对禁止多行或少行。

要求：
1. 每行输入对应一行输出，保持原有顺序
2. 每行译文必须输出为一整行，无论多长都绝对禁止换行拆分
3. 输出格式必须与输入一致：每行以 [编号] 开头，后面紧跟译文
4. 不要合并多行，保持每行独立
5. 除带编号的译文行外，不要输出任何其他内容（不要总结、解释、空行）

字幕内容：
{numbered_lines}"""
        
        for attempt in range(max_retries):
            try:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 8192,
                    "temperature": 0.5,
                }
                response = requests.post(api_url, headers=headers, json=payload, timeout=180)
                response.raise_for_status()
                result = response.json()
                
                finish_reason = result.get("choices", [{}])[0].get("finish_reason", "")
                if finish_reason == "length":
                    print(f"  警告: 第 {chunk_num} 段翻译可能被截断")
                
                translation = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if not translation:
                    raise ValueError("翻译结果为空")
                
                # 后处理：解析带编号的译文行，验证编号连续性
                translated_lines = []
                expected_start = global_start_idx + 1
                last_num = expected_start - 1
                
                for ln in translation.split('\n'):
                    ln = ln.strip()
                    if not ln:
                        continue
                    m = re.match(r'^\[(\d+)\]\s*(.*)', ln)
                    if m:
                        num = int(m.group(1))
                        text = m.group(2).strip()
                        # 验证编号连续性
                        if num != last_num + 1:
                            print(f"  警告: 第 {chunk_num} 段编号不连续，期望 [{last_num + 1}]，实际 [{num}]")
                        last_num = num
                        translated_lines.append(text)
                    else:
                        # 没有编号前缀，整行作为译文（AI没按格式返回）
                        translated_lines.append(ln)
                
                expected_lines = len(chunk_lines)
                
                if len(translated_lines) != expected_lines:
                    print(f"  第 {chunk_num} 段行数不匹配: 期望{expected_lines}行, 实际{len(translated_lines)}行, 自动修复中...")
                    translated_lines = _force_line_alignment(translated_lines, expected_lines)
                
                all_translations.append('\n'.join(translated_lines))
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  第 {chunk_num} 段翻译失败，重试中... ({attempt+1}/{max_retries})")
                else:
                    print(f"  第 {chunk_num} 段翻译失败: {e}")
    
    # 合并所有翻译段
    full_translation = '\n'.join(all_translations)
    translated_lines = [ln for ln in full_translation.split('\n') if ln.strip()]
    
    # 最终校验：如果总行数仍不匹配，做全局修复
    if len(translated_lines) != len(non_empty_lines):
        print(f"警告: 全局行数不匹配，原文{len(non_empty_lines)}行 vs 译文{len(translated_lines)}行，强制对齐...")
        translated_lines = _force_line_alignment(translated_lines, len(non_empty_lines))
    
    # 返回纯译文（不含空行，行数=原文非空行数）
    return '\n'.join(translated_lines)


def merge_translation_to_bilingual(
    original_content: str,
    translation: str,
) -> str:
    """将原文和译文合并生成双语字幕
    
    参数:
        original_content: 原始字幕内容
        translation: 翻译后的中文内容
    
    返回:
        双语字幕内容（原文 + > 译文）
    """
    original_lines = original_content.strip().split('\n')
    chinese_lines = translation.strip().split('\n')
    
    bilingual_lines = []
    chinese_idx = 0
    
    for orig_line in original_lines:
        orig_line = orig_line.rstrip()
        bilingual_lines.append(orig_line)
        if orig_line:
            # 按顺序取对应的译文
            chinese = chinese_lines[chinese_idx].strip() if chinese_idx < len(chinese_lines) else ""
            if chinese:
                bilingual_lines.append(f"> {chinese}")
            chinese_idx += 1
    
    return '\n'.join(bilingual_lines).rstrip('\n')


def add_translation_to_file(filepath: Path, translation: str):
    """将翻译追加到字幕文件末尾（在 YAML frontmatter 之后）"""
    try:
        content = filepath.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        
        bilingual = merge_translation_to_bilingual(parts[2] if len(parts) >= 3 else content, translation)
        translation_section = f"\n---\n\n## 📝 双语字幕\n\n{bilingual}"
        
        if len(parts) >= 3:
            frontmatter = parts[0] + "---" + parts[1] + "---"
            new_content = frontmatter + translation_section
        else:
            new_content = content.rstrip("\n") + translation_section
        
        filepath.write_text(new_content, encoding="utf-8")
        print(f"✓ 已添加翻译: {filepath.name}")
    except Exception as e:
        print(f"写入翻译失败: {e}")


if __name__ == "__main__":
    # 单独测试翻译功能
    import os
    import sys
    
    # 添加项目根目录到路径
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_FLASH_MODEL
    
    # 测试文件
    test_file = Path(r"E:\Obsidian\主仓库\11-subtitles\Youtube\the most unhinged (recent!) computer science discoveries.md")
    
    if test_file.exists():
        print(f"读取文件: {test_file.name}")
        content = test_file.read_text(encoding="utf-8")
        
        # 调试：检查换行符
        import re
        newline_counts = {
            'CRLF': len(re.findall(r'\r\n', content)),
            'LF': len(re.findall(r'(?<!\r)\n', content)),
            'CR': len(re.findall(r'\r(?!\n)', content)),
        }
        print(f"换行符: CRLF={newline_counts['CRLF']}, LF={newline_counts['LF']}, CR={newline_counts['CR']}")
        print(f"文件长度: {len(content)} 字符")
        
        # 统一换行符
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # 找所有 --- 的位置
        import re
        positions = [m.start() for m in re.finditer('---', content)]
        print(f"所有 --- 位置: {positions}")
        
        # 文件结构分析：
        # 1. 标题（第1行）
        # 2. frontmatter 内容（第3-7行，键值对格式）
        # 3. 空行（第8行）
        # 4. --- (frontmatter结束标记，位置194)
        # 5. 空行
        # 6. 字幕内容
        # 7. --- (字幕结束标记，位置16586)
        
        # 找 frontmatter 结束标记（第一个 ---）
        # 字幕从 frontmatter 结束标记之后开始，到字幕结束标记之前
        if len(positions) >= 2:
            # positions[0] = frontmatter 结束标记
            # positions[1] = 字幕结束标记
            frontmatter_end = positions[0]
            subtitle_end = positions[1]
            subtitle = content[frontmatter_end + 3:subtitle_end].strip()
            print(f"字幕起始位置: {frontmatter_end + 3}，字幕结束位置: {subtitle_end}，字幕长度: {len(subtitle)}")
        elif len(positions) == 1:
            # 只有一个 ---，字幕从 --- 之后开始
            frontmatter_end = positions[0]
            subtitle = content[frontmatter_end + 3:].strip()
            print(f"字幕起始位置: {frontmatter_end + 3}，字幕长度: {len(subtitle)}")
        else:
            # 没有 ---，使用整个内容
            subtitle = content.strip()
            print("未找到 --- 分隔符，使用全部内容")
        
        lines = subtitle.split('\n')
        print(f"字幕总行数: {len(lines)}")
        non_empty = sum(1 for l in lines if l.strip())
        print(f"非空行数: {non_empty}")
        print(f"开始翻译...\n")
        
        if not subtitle.strip():
            print("错误: 字幕内容为空")
            sys.exit(1)
        
        translation = translate_subtitle_with_deepseek(
            subtitle,
            api_key=DEEPSEEK_API_KEY,
            api_url=DEEPSEEK_API_URL,
            model=DEEPSEEK_FLASH_MODEL,
        )
        
        if translation:
            print(f"\n翻译完成，测试合并...")
            bilingual = merge_translation_to_bilingual(subtitle, translation)
            print(f"合并后行数: {len(bilingual.split(chr(10)))}")
            print("\n前10行预览:")
            for i, line in enumerate(bilingual.split('\n')[:10]):
                print(f"  {line}")
    else:
        print(f"测试文件不存在: {test_file}")
