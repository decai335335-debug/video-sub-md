#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""video-sub-md — 统一视频字幕下载器（Bilibili + YouTube + Coursera）"""

import asyncio
import json
import os
import re
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import requests
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config import (
    BILIBILI_OUTPUT_DIR,
    YOUTUBE_OUTPUT_DIR,
    DEFAULT_OUTPUT_DIR,
    OBSIDIAN_VAULT_NAME,
    OBSIDIAN_VAULT_ROOT,
    MAX_CONCURRENT,
    DEEPSEEK_API_KEY,
    DEEPSEEK_API_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_FLASH_MODEL,
    DEFAULT_SESSDATA,
    LOCAL_MODEL_PATH,
    DEFAULT_AI_MODE,
)
from models import DownloadResult, BatchReport
from core.naming import add_date_prefix

console = Console(force_terminal=True)
app = typer.Typer(add_completion=False)
COURSERA_OUTPUT_DIR = DEFAULT_OUTPUT_DIR / "Coursera"
DOUYIN_OUTPUT_DIR = DEFAULT_OUTPUT_DIR / "Douyin"
MERGE_OUTPUT_DIR = Path("E:/Obsidian/主仓库/00000-Sub_Merge")


def _read_md_for_merge(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _merge_downloaded_markdown(success_results: List[DownloadResult]) -> Optional[Path]:
    paths: List[Path] = []
    seen = set()
    for result in success_results:
        if not result.filepath:
            continue
        path = result.filepath
        if not path.exists() or path.suffix.lower() != ".md":
            continue
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)

    if len(paths) < 2:
        console.print("[dim]本次可合并的 Markdown 少于 2 个，已跳过 merge[/dim]")
        return None

    first_parent = paths[0].parent
    if all(path.parent == first_parent for path in paths):
        source_name = first_parent.name
    else:
        common = Path(os.path.commonpath([str(path.parent) for path in paths]))
        source_name = common.name if common.name else first_parent.name

    MERGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = MERGE_OUTPUT_DIR / f"{add_date_prefix(source_name)}_合并.md"
    if output_file in paths:
        paths = [path for path in paths if path != output_file]

    merged_parts = []
    total_chars = 0
    for path in paths:
        content = _read_md_for_merge(path).strip()
        if not content:
            continue
        merged_parts.append(f"<!-- 来源：{path.name} -->\n\n{content}")
        total_chars += len(content)

    if not merged_parts:
        console.print("[yellow]没有可合并的 Markdown 内容[/yellow]")
        return None

    output_file.write_text("\n\n---\n\n".join(merged_parts) + "\n", encoding="utf-8")
    size_kb = output_file.stat().st_size / 1024
    console.print(f"[green][OK][/green] merge 完成: {output_file}")
    console.print(f"[dim]合并文件数: {len(merged_parts)} | 字符数: {total_chars:,} | 大小: {size_kb:.1f} KB[/dim]")
    return output_file


def _maybe_merge_downloaded_markdown(success_results: List[DownloadResult]) -> Optional[Path]:
    if not success_results:
        return None
    console.print()
    while True:
        choice = input("是否 merge 本次下载的 Markdown？(a 是 / b 否): ").strip().lower()
        if choice == "a":
            return _merge_downloaded_markdown(success_results)
        if choice == "b":
            console.print("[dim]已跳过 merge[/dim]")
            return None
        console.print("[yellow]请输入 a 或 b[/yellow]")


def _resolve_youtube_cookie_file(explicit_path: Optional[Path]) -> Optional[Path]:
    """Resolve YouTube cookies for both CLI and launcher-menu runs."""
    if explicit_path:
        return explicit_path.resolve()

    env_path = os.environ.get("VIDEO_SUB_MD_YOUTUBE_COOKIES", "").strip()
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path(__file__).resolve().parent / "cookies" / "youtube.txt")

    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved.is_file():
            return resolved
    return None


# 导入翻译模块
try:
    from core.translator import translate_subtitle_with_deepseek, add_translation_to_file
except ImportError:
    console.print("[yellow]警告: 无法导入 core.translator 模块，翻译功能将不可用[/yellow]")
    translate_subtitle_with_deepseek = None
    add_translation_to_file = None

# 导入本地模型模块（可选）
try:
    from core.local_llm import get_client as get_local_llm_client
except ImportError:
    get_local_llm_client = None

# 当前会话的 AI 模式："local" 或 "api"
_current_ai_mode: str = DEFAULT_AI_MODE


def _choose_ai_mode() -> str:
    """询问用户使用本地模型还是 API。"""
    global _current_ai_mode
    default_hint = "本地模型" if DEFAULT_AI_MODE == "local" else "DeepSeek API"
    print()
    console.print("[bold]选择 AI 模式[/bold]")
    console.print(f"[dim]直接回车 = 默认使用 {default_hint}[/dim]")
    console.print("[dim]按 0 = 本地模型（{0}）[/dim]".format(LOCAL_MODEL_PATH))
    console.print("[dim]按 1 = DeepSeek API[/dim]")
    choice = input("  选择 (0/1/回车): ").strip()
    if choice == "0":
        _current_ai_mode = "local"
    elif choice == "1":
        _current_ai_mode = "api"
    else:
        _current_ai_mode = DEFAULT_AI_MODE
    mode_text = "本地模型" if _current_ai_mode == "local" else "DeepSeek API"
    console.print(f"[dim]已选择: {mode_text}[/dim]")
    return _current_ai_mode


def _prompt_required_choice(prompt: str, valid_choices: set[str]) -> str:
    """Prompt until the user explicitly enters one of the allowed choices."""
    normalized_choices = {choice.lower() for choice in valid_choices}
    while True:
        choice = input(prompt).strip().lower()
        if choice in normalized_choices:
            return choice
        if not choice:
            console.print("[dim]空回车已忽略，请输入有效选项。[/dim]")
        else:
            console.print(f"[yellow]请输入: {' / '.join(sorted(normalized_choices))}[/yellow]")


def _clean_summary_markdown(text: str) -> str:
    """清洗 AI 输出的 Markdown，修复常见格式问题以确保正确渲染
    
    修复项目：
    1. 移除行首空格（防止表格被解析为代码块）
    2. 移除行首的 `> ` 引用标记（防止内容被包裹在引用块中）
    3. 修复表格分隔线：确保每个表格都有正确的 |:---| 分隔行
    4. 清理多余的空行
    """
    import re
    
    def _is_table_separator(line: str) -> bool:
        """检查行是否是表格分隔线（如 |:---|:---| ）"""
        stripped = line.strip()
        if '|' not in stripped:
            return False
        # 分隔线只包含 |、-、: 和空格
        content = stripped.replace('|', '').replace('-', '').replace(':', '').strip()
        return len(content) == 0
    
    def _is_table_row(line: str) -> bool:
        """检查行是否是表格数据/表头行（包含 | 且不是分隔线）"""
        return '|' in line and not _is_table_separator(line)
    
    lines = text.split('\n')
    cleaned = []
    
    for line in lines:
        # 1. 移除行首的 `> ` 引用标记（保留后面的空格作为列表缩进）
        if line.startswith('> '):
            line = line[2:]
        elif line.startswith('>'):
            line = line[1:]
        
        # 2. 只移除表格行的行首空格（防止表格被解析为代码块）
        # 保留列表的缩进空格（如 `  - 子项`）
        stripped = line.lstrip(' \t')
        if stripped.startswith('|') and line != stripped:
            # 这一行是表格行且有行首空格 → 移除空格
            line = stripped
        
        cleaned.append(line)
    
    # 3. 修复表格分隔线：识别连续表格块，在表头后插入分隔线
    result_lines = []
    i = 0
    while i < len(cleaned):
        line = cleaned[i]
        
        if _is_table_row(line):
            # 找到连续的表格行块
            table_block = [line]
            j = i + 1
            while j < len(cleaned) and (_is_table_row(cleaned[j]) or _is_table_separator(cleaned[j])):
                table_block.append(cleaned[j])
                j += 1
            
            # 检查第二行是否是分隔线，如果不是则在第一行后插入
            if len(table_block) >= 2:
                if not _is_table_separator(table_block[1]):
                    cols = line.count('|') - 1
                    if cols > 0:
                        sep = '|' + ':---|' * cols
                        table_block.insert(1, sep)
            elif len(table_block) == 1:
                # 只有一行表格，也插入分隔线
                cols = line.count('|') - 1
                if cols > 0:
                    sep = '|' + ':---|' * cols
                    table_block.append(sep)
            
            result_lines.extend(table_block)
            i = j
        else:
            result_lines.append(line)
            i += 1
    
    # 4. 清理多余空行（最多连续两个空行）
    final_lines = []
    empty_count = 0
    for line in result_lines:
        if line.strip() == '':
            empty_count += 1
            if empty_count <= 2:
                final_lines.append(line)
        else:
            empty_count = 0
            final_lines.append(line)
    
    return '\n'.join(final_lines).strip()


def _split_file_sections(content: str) -> tuple:
    """把文件内容拆成 (frontmatter, analysis, subtitle) 三部分。

    优先使用 <!-- SUBTITLE_START --> 标记定位字幕起始位置；
    如果没有标记，再按 ## 🔍 深度分析 和 --- 分隔线做回退解析。
    """
    marker = "<!-- SUBTITLE_START -->"
    marker_pos = content.find(marker)
    if marker_pos != -1:
        before_marker = content[:marker_pos].rstrip("\n")
        # 如果 marker 前面紧跟 ---，把它从 analysis 中去掉
        if before_marker.endswith("---"):
            before_marker = before_marker[:-3].rstrip("\n")
        subtitle = content[marker_pos + len(marker):].lstrip("\n")
        # 从 before_marker 中分离 frontmatter 和 analysis
        first_sep = before_marker.find("---")
        if first_sep == -1:
            return (before_marker.strip(), "", subtitle)
        frontmatter = before_marker[:first_sep].rstrip("\n")
        after_frontmatter = before_marker[first_sep + 3:].lstrip("\n")
        analysis_heading = "## 🔍 深度分析"
        if after_frontmatter.startswith(analysis_heading):
            return (frontmatter, after_frontmatter.rstrip("\n"), subtitle)
        return (frontmatter, "", subtitle)

    # 无标记时的回退解析
    first_sep = content.find("---")
    if first_sep == -1:
        return (content.strip(), "", "")

    frontmatter = content[:first_sep].rstrip("\n")
    after_frontmatter = content[first_sep + 3:].lstrip("\n")

    analysis_heading = "## 🔍 深度分析"
    heading_pos = after_frontmatter.find(analysis_heading)
    has_analysis = after_frontmatter.startswith(analysis_heading) or (heading_pos != -1 and heading_pos < 200)

    if has_analysis:
        # 分析区内部可能也有 ---，优先找分析区结束后的最后一个 ---
        #  heuristic：从末尾往前找 ---，假设字幕区不会以 --- 结尾
        second_sep = after_frontmatter.rfind("---")
        if second_sep != -1 and second_sep > after_frontmatter.find(analysis_heading) + 20:
            analysis = after_frontmatter[:second_sep].rstrip("\n")
            subtitle = after_frontmatter[second_sep + 3:].lstrip("\n")
            return (frontmatter, analysis, subtitle)
        else:
            return (frontmatter, after_frontmatter.strip(), "")
    else:
        return (frontmatter, "", after_frontmatter)


def _extract_subtitle_body(content: str) -> str:
    """从文件内容中提取纯字幕部分，跳过 frontmatter 和已存在的分析内容。"""
    _, _, subtitle = _split_file_sections(content)
    return subtitle


def generate_summary_with_deepseek(subtitle_content: str, video_title: str = "") -> Optional[str]:
    """调用 DeepSeek API 或本地模型为字幕内容生成深度分析。"""
    system_prompt = (
        "你是一位精通认知科学、传播学和知识工程的深度内容分析师。"
        "请严格按以下协议执行，禁止偏离。"
        "除非直接引用原文，否则所有分析、总结、表格内容必须使用中文输出。"
        "引用原文时应尽量简短，并在引用后用中文说明其含义。"
    )
    prompt = f"""注意：输出时不要以 `# ` 或 `## ` 标题开头，直接从 `### ` 三级标题开始（如 `### 1.1 拓扑结构`）。文件外层已有 `## 🔍 深度分析` 标题，不要重复。

---

## 🔒 元认知安全锁（最高优先级，不可覆盖）

1. **所有分析必须严格基于提供的字幕文本**。禁止推测视频画面、语气、表情或音频信息。
2. **禁止编造**。如果字幕未提供某信息，明确标注 **[信息不足]**，不得补全。
3. **引用原文时必须使用引号**，不得改写、润色或概括后冒充原文。
4. **数量不强制**：以下分析中，若内容本身不足，允许输出"无"或"仅1项"，禁止为凑数而拆分或编造。

## 📝 格式规范锁（渲染安全，不可违反）

以下规则直接影响 Markdown 渲染效果，必须严格遵守：

1. **禁止行首空格**：任何行的第一个字符不能是空格。行首空格会导致表格被渲染为代码块。
2. **表格必须有分隔线**：每个表格必须在表头后紧跟分隔行 `|:---|:---|:---|`，列数与表头一致，使用 `:` 左对齐标记。
3. **论证树用代码块包裹**：B1 论证拆解的树状结构必须放在 triple backtick (```) 代码块中，而不是纯文本缩进。
4. **禁止用 `>` 引用块包裹章节**：不要在章节内容前加 `>`，引用块只用于真正的原文引用。
5. **列表最多两级嵌套，子项必须缩进两个空格**：
   - 一级列表：`- 父项`
   - 二级列表：`  - 子项`（前面必须有两个空格）
   - 禁止三级及以上嵌套
6. **表格不要放在 `- ` 列表内部**：表格标题用 `**标题**` 粗体即可，不要在前面加 `- `。表格前后各留一个空行。
7. **标题格式**：`#` 后必须有一个空格，如 `### 标题`，不要写成 `###标题`。
8. **分隔线统一使用 `---`**，前后各留一个空行。
9. **时间戳只用单个起始时间点**：如 `` `00:00` `` 或 `` `01:17` ``，不要写成区间 `` `00:00-00:49` ``。时间戳整体包裹在反引号中。
10. **不要用方括号 `[]` 包裹普通文本**：方括号在 Markdown 中是链接语法。时间轴中的主题和动作用普通文本或粗体即可，不要用 `[主题]` 或 `[动作]`。
11. **分析内容中不要使用 `---` 分隔线**：文件外层已用 `---` 分隔分析区和字幕区，分析内部再用 `---` 会导致结构解析错误。

---

视频标题：{video_title}

字幕内容：
{subtitle_content[:8000]}

---

## 📋 第一层：通用底层分析（所有视频必执行）

### 1.1 拓扑结构（Spatial Mapping）

以纯文本列表输出，格式如下：

- **时间轴切片**（按实际议题切分，不强制数量）：
  - `起始时间点` — 主题描述 — 核心动作（引入/展开/论证/总结）
- **逻辑骨架**：线性递进 / 螺旋上升 / 树状分支 / 网状关联 / 单一议题
- **信息密度**：
  - 峰值段：`起始时间点` — 原因：一句话分析
  - 低谷段：`起始时间点` — 原因：一句话分析

### 1.2 语义提取（Semantic Extraction）

- **核心命题**：用不超过20字概括视频主旨（Thesis）
- **支撑论据表**（提取所有可辨识的，上限不封顶，用 Markdown 表格输出）：

  | 论据 | 原文摘要 | 可信度 | 标记 |
  |:---|:---|:---|:---|
  | [名称/关键词] | [原文摘要] | [A-权威来源/B-个人经验/C-未验证] | [📚/👤/⚠️] |

- **概念图谱**（用 Markdown 表格输出）：

  | 术语 | 视频语境定义 | 与日常用法差异 |
  |:---|:---|:---|
  | [术语] | [定义] | [差异/无差异] |

### 1.3 认知机制（Cognitive Architecture）

- **认知脚手架**：观众必须具备的先验知识（列出所有，不强制数量）
- **注意力调度**：哪些段落使用了以下技巧？各举一例原文：
  - 悬念：[原文]
  - 重复：[原文]
  - 对比：[原文]
  - 故事化：[原文]
- **记忆锚点**：提取最可能被长期记住的3句原文，分析其记忆编码机制（如：韵律/反差/具体意象）

---

### 1.4 批判性重构（Critical Reconstruction）

1. **反事实假设**：如果核心结论错误，最可能的原因是什么？
2. **沉默的证据**：视频刻意回避或遗漏了哪些关键视角？
3. **适用边界**：这些内容在什么情境下会失效？给出至少2个反例场景。

### 1.5 趣味叙事重构（Fun Narrative Reconstruction）【新增】
用**非学术的、有趣的**方式重新讲述这个视频的核心故事，要求：

- **类比引擎**：将技术概念映射到日常生活场景，至少3个类比（如：把"禁用异常"比作"手术室禁用'也许能行'")
- **彩蛋挖掘**：提取视频中所有有趣的旁支细节、冷知识、个人轶事，至少3个，并解释它们如何服务于主线叙事
- **叙事节奏（电影化）**：用电影类型描述视频结构（如：灾难片→历史悬疑→动作片→哲学片）
- **一句话钩子**：用一句带有悬念或反差感的话概括视频，适合推荐给朋友

输出格式：轻松但不失准确，可适度使用emoji和比喻。可以联网搜索推理，类比举例，但禁止编造视频未提及的内容。

---

## 🔌 第二层：类型识别与条件激活

请基于内容特征自行判断视频类型，**只激活对应插件**。

输出时，在 `## 🔌 第二层：类型识别与条件激活` 之后，先输出视频类型和激活插件的简要说明（如 `**视频类型**：教学型`），然后补充 `### 插件X：xxx型分析` 作为中间层级标题，再输出具体模块内容。

### 若识别为【教学型】（传授技能/系统知识/操作步骤）→ 激活插件A

输出格式示例：
```
### 插件A：教学型分析

#### A1 学习路径重构
```

#### A1 学习路径重构
- **先决条件检查清单**（所有条目统一用 `- [ ]` 未勾选状态，禁止用 `- [x]` 打勾）：
  - [ ] 知识前提：[必须预先掌握的概念]
  - [ ] 工具前提：[需要的软件/硬件/环境]
  - [ ] 认知前提：[需要具备的思维方式]
- **核心知识模块**（用 Markdown 表格输出）：

  | 模块 | 难度 | 可独立学习 | 前置依赖 |
  |:---|:---|:---|:---|
  | [名称] | ⭐/⭐⭐/⭐⭐⭐ | 是/否 | [模块名/无] |

- **常见陷阱地图**（用 Markdown 表格输出）：

  | 易错点 | 原文位置 | 纠正方法 |
  |:---|:---|:---|
  | [描述] | `起始时间点` | [具体动作] |

#### A2 知识晶体提取
- 提取所有可抽象为通用模式的知识点，用 Markdown 表格输出：

  | 场景 | 视频解法 | 通用模式 | 可迁移领域 |
  |:---|:---|:---|:---|
  | [具体场景] | [步骤] | [底层逻辑] | [领域] |

#### A3 效率审计
- **信噪比评估**：核心知识占比约___%，冗余内容（寒暄/铺垫/重复）占比约___%
- **最优学习策略**：
  - 若只看一遍：重点看 `起始时间点` 段，因为 [理由]
  - 若看两遍：第二遍聚焦 `起始时间点` 段，因为 [理由]

---

### 若识别为【观点型】（表达立场/说服受众/评论分析）→ 激活插件B

输出格式示例：
```
### 插件B：观点型分析

#### B1 论证拆解（Argument Tree）
```

#### B1 论证拆解（Argument Tree）
用 triple backtick 代码块包裹缩进文本树：

```
核心主张：[一句话]
├── 论据A：[描述]
│   ├── 支撑A1：[事实/数据] — 可信度：[A/B/C]
│   └── 支撑A2：[案例/引用]
├── 论据B：[描述]
│   └── 支撑B1：[...]
└── 🔴 隐含前提X：[未明说但必须成立的前提] ← 论证最脆弱点
```

#### B2 修辞与说服分析
提取所有可辨识的策略，用 Markdown 表格输出：

| 策略 | 原文证据 | 效果 | 识别难度 |
|:---|:---|:---|:---|
| [权威背书/情感共鸣/虚假二分/幸存者偏差/其他] | "[引用]" | [增强可信度/降低批判性/限制思考空间] | [低/中/高] |

#### B3 立场光谱定位
- **坐标**：极端保守 [1]——[2]——[3]——[4]——[5] [极端激进]
- **作者位置**：约___分（简述判断依据）
- **邻近立场**：[2-3个相近但有差异的观点]
- **对立立场**：[2-3个最强反驳观点]

#### B4 行动转化
- 立即（24h内）：[具体动作] | 完成标志：[标准]
- 短期（1周内）：[验证假设] | 判断依据：[标准]
- 长期（1-3月）：[跟踪指标] | 信号特征：[标准]

---

### 若识别为【混合型】（教学+观点交织）→ 同时激活A+B

输出格式示例：
```
### 插件A：教学型分析

#### A1 ...
...

### 插件B：观点型分析

#### B1 ...
...
```

并额外输出：
- **段落属性标注**：哪些时间区间是知识传授，哪些是观点输出？
- **交界点分析**：知识→观点的转折标志是什么？观点→知识的过渡方式是什么？

请按以上格式输出深度分析内容："""

    if _current_ai_mode == "local" and get_local_llm_client:
        return _generate_summary_with_local_llm(prompt, system_prompt)

    if not DEEPSEEK_API_KEY:
        console.print("[yellow]警告: 未设置 DEEPSEEK_API_KEY 环境变量，跳过分析生成[/yellow]")
        return None

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 32768,
            "temperature": 0.7,
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
        }
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=180)
        response.raise_for_status()
        result = response.json()

        # 打印 token 消耗
        usage = result.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
        console.print(f"[dim]分析 Token: 提示词 {prompt_tokens} / 生成 {completion_tokens} / 总计 {total_tokens}[/dim]")

        # 检查是否因长度被截断
        finish_reason = result.get("choices", [{}])[0].get("finish_reason", "")
        if finish_reason == "length":
            console.print("[yellow]警告: API 输出达到长度限制，分析内容可能不完整[/yellow]")

        summary = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        summary = _clean_summary_markdown(summary)
        return summary if summary else None
    except Exception as e:
        console.print(f"[red]调用 DeepSeek API 失败: {e}[/red]")
        return None


def _generate_summary_with_local_llm(prompt: str, system_prompt: str) -> Optional[str]:
    """使用本地模型生成深度分析。"""
    try:
        client = get_local_llm_client(LOCAL_MODEL_PATH)
        result = client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_new_tokens=4096,
            temperature=0.7,
        )
        console.print(
            f"[dim]分析 Token: 提示词 {result['usage']['prompt_tokens']} / "
            f"生成 {result['usage']['completion_tokens']} / "
            f"总计 {result['usage']['total_tokens']} "
            f"(耗时 {result['elapsed']:.1f}s)[/dim]"
        )
        summary = _clean_summary_markdown(result["text"])
        return summary if summary else None
    except Exception as e:
        console.print(f"[red]本地模型分析失败: {e}[/red]")
        return None


def add_summary_to_file(filepath: Path, summary: str):
    """将深度分析添加到字幕文件（位于标题元数据之后、字幕内容之前）
    
    文件结构: [标题+元数据] + --- + [字幕内容]
    插入后:   [标题+元数据] + --- + [## 深度分析 + 分析内容 + ---] + [字幕内容]
    """
    try:
        content = filepath.read_text(encoding="utf-8")
        parts = content.split("---", 1)  # 只分割一次，--- 是 markdown 分隔线
        
        # 分析内容直接作为普通 Markdown 插入（不用 > 引用块，确保表格/列表正确渲染）
        # 使用 <!-- SUBTITLE_START --> 标记明确分隔分析区和字幕区，避免后续翻译时误判
        import re
        summary = summary.strip()
        # 如果 AI 已经输出了 ## 🔍 深度分析 标题，避免重复
        if summary.startswith("## 🔍 深度分析"):
            analysis_body = summary[len("## 🔍 深度分析"):].lstrip("\n")
        else:
            analysis_body = summary
        # 清理尾部可能存在的 --- 分隔线，避免生成多个连续分隔线
        analysis_body = re.sub(r"\n*---\s*$", "", analysis_body).strip()
        # 用 <!-- SUBTITLE_START --> 明确标记字幕区起点
        analysis_section = f"## 🔍 深度分析\n\n{analysis_body}\n\n---\n<!-- SUBTITLE_START -->\n"

        if len(parts) >= 2:
            header = parts[0].rstrip("\n")
            body = parts[1].lstrip("\n")
            new_content = f"{header}\n\n---\n\n{analysis_section}\n\n{body}"
        else:
            # 没有 --- 分隔线，直接在开头插入
            new_content = f"{analysis_section}\n\n{content}"
        
        filepath.write_text(new_content, encoding="utf-8")
        console.print(f"[green]✓[/green] 已添加简介: {filepath.name}")
    except Exception as e:
        console.print(f"[red]写入简介失败: {e}[/red]")


def detect_platform(url: str) -> str:
    """根据 URL 自动识别平台"""
    u = url.lower()
    if "bilibili.com" in u or u.startswith("bv"):
        return "bilibili"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "douyin.com" in u:
        return "douyin"
    if "coursera.org" in u or re.fullmatch(r"[a-z0-9][a-z0-9_-]*", u):
        return "coursera"
    return "unknown"


def normalize_result(raw_result, platform: str, source_url: str = "", output_dir: Path | None = None) -> DownloadResult:
    """把平台特定的结果对象转换为通用格式"""
    return DownloadResult(
        platform=platform,
        source_url=source_url,
        video_id=getattr(raw_result, "bvid", "") or getattr(raw_result, "video_id", ""),
        title=getattr(raw_result, "title", ""),
        status=getattr(raw_result, "status", "error"),
        language=getattr(raw_result, "language", None) or None,
        filepath=getattr(raw_result, "filepath", None),
        output_dir=output_dir,
        error=getattr(raw_result, "error", None),
    )


async def download_bilibili_task(url: str, output_dir: Path, lang: Optional[str], cookie: str = "") -> DownloadResult:
    """异步包装 bilibili 下载"""
    from core.bilibili.downloader import download_one as bilibili_download
    from core.bilibili.metadata import set_cookie

    if cookie:
        set_cookie(cookie)
    result = await asyncio.to_thread(bilibili_download, url, output_dir, "md", lang)
    return normalize_result(result, "bilibili", source_url=url, output_dir=output_dir)


def _sync_youtube_download(meta, output_dir: Path, lang: Optional[str]):
    """同步包装器：在线程中运行 youtube 异步下载"""
    import asyncio
    from core.youtube.downloader import download_with_delay
    return asyncio.run(download_with_delay(meta, output_dir, lang))


async def download_youtube_task(
    url: str,
    output_dir: Path,
    lang: Optional[str],
    youtube_cookie_file: Optional[Path] = None,
) -> DownloadResult:
    """异步包装 youtube 下载"""
    from core.youtube import metadata as youtube_metadata

    if youtube_cookie_file:
        youtube_metadata.YDLP_OPTS["cookiefile"] = str(youtube_cookie_file)
    meta = await asyncio.to_thread(youtube_metadata.fetch_metadata, url)
    result = await asyncio.to_thread(_sync_youtube_download, meta, output_dir, lang)
    return normalize_result(result, "youtube", source_url=url, output_dir=output_dir)


async def download_coursera_task(url: str, output_dir: Path, lang: Optional[str]) -> DownloadResult:
    """异步包装 Coursera 课程字幕下载：一个课程链接生成一个合并 Markdown"""
    from core.coursera.downloader import CourseraDownloader

    def _sync_download():
        downloader = CourseraDownloader(
            cookies_from_browser=os.environ.get("COURSERA_COOKIES_FROM_BROWSER", "")
        )
        return downloader.download_course_markdown(url, output_dir, preferred_lang=lang or "en")

    result = await asyncio.to_thread(_sync_download)
    status = "success" if result.success_count > 0 else "error"
    error = None if status == "success" else "Coursera course subtitles not found"
    return DownloadResult(
        platform="coursera",
        source_url=url,
        video_id=result.course.course_id,
        title=result.course.title,
        status=status,
        language=lang or "en",
        filepath=result.output_path,
        output_dir=output_dir,
        error=error,
    )


def download_douyin_batch(urls: List[str], output_dir: Path, lang: Optional[str]) -> List[DownloadResult]:
    """Download Douyin audio, transcribe with local SenseVoice, and write Markdown."""
    if not urls:
        return []

    try:
        from asr_fallback_module import DEFAULT_MODEL_PATH, SenseVoiceTranscriber, process_url
        from core.douyin.extractor import extract_video_id, normalize_url
    except Exception as exc:
        return [
            DownloadResult(
                platform="douyin",
                source_url=url,
                title=url[:50],
                status="error",
                error=f"Douyin ASR module unavailable: {exc}",
                output_dir=output_dir,
            )
            for url in urls
        ]

    model_path = Path(os.environ.get("VIDEO_SUB_MD_ASR_MODEL") or os.environ.get("SENSEVOICE_MODEL_PATH") or DEFAULT_MODEL_PATH)
    asr_lang = lang or "auto"

    try:
        transcriber = SenseVoiceTranscriber(model_path=model_path, device=os.environ.get("VIDEO_SUB_MD_ASR_DEVICE", "auto"))
    except Exception as exc:
        return [
            DownloadResult(
                platform="douyin",
                source_url=url,
                video_id=extract_video_id(url),
                title=url[:50],
                status="error",
                error=f"Failed to load SenseVoice model: {exc}",
                output_dir=output_dir,
            )
            for url in urls
        ]

    results: List[DownloadResult] = []
    for url in urls:
        normalized = normalize_url(url)
        video_id = extract_video_id(url)
        try:
            console.print(f"[cyan]Douyin ASR:[/cyan] {normalized}")
            output_path = process_url(
                url=normalized,
                transcriber=transcriber,
                output_dir=output_dir,
                language=asr_lang,
                keep_audio=False,
                cookie_file=None,
                cookies_from_browser=os.environ.get("VIDEO_SUB_MD_ASR_COOKIES_FROM_BROWSER", ""),
            )
            results.append(
                DownloadResult(
                    platform="douyin",
                    source_url=normalized,
                    video_id=video_id,
                    title=output_path.stem,
                    status="success",
                    language=f"ASR:{asr_lang}",
                    filepath=output_path,
                    output_dir=output_dir,
                )
            )
        except Exception as exc:
            results.append(
                DownloadResult(
                    platform="douyin",
                    source_url=normalized,
                    video_id=video_id,
                    title=normalized,
                    status="error",
                    error=str(exc),
                    output_dir=output_dir,
                )
            )
    return results


def platform_tag(platform: str) -> str:
    """Rich label for result tables."""
    if platform == "bilibili":
        return "[orange3]B站[/orange3]"
    if platform == "youtube":
        return "[red]YouTube[/red]"
    if platform == "coursera":
        return "[blue]Coursera[/blue]"
    if platform == "douyin":
        return "[magenta]Douyin[/magenta]"
    return platform or "-"


def _asr_output_dir_for(platform: str) -> Path:
    if platform == "bilibili":
        return BILIBILI_OUTPUT_DIR
    if platform == "youtube":
        return YOUTUBE_OUTPUT_DIR
    if platform == "douyin":
        return DOUYIN_OUTPUT_DIR
    return DEFAULT_OUTPUT_DIR / "ASR"


def _maybe_run_asr_fallback(failed_results: List[DownloadResult], lang: Optional[str]) -> None:
    """Ask once whether failed/no-subtitle videos should be transcribed from audio."""
    candidates = [
        r for r in failed_results
        if r.platform in {"bilibili", "youtube"} and (r.source_url or r.video_id)
    ]
    if not candidates:
        return

    console.print()
    console.print(
        f"[yellow]检测到 {len(candidates)} 个 Bilibili/YouTube 视频没有成功拿到字幕。[/yellow]"
    )
    choice = _prompt_required_choice("是否下载音频并用本地 SenseVoice 识别？(a 识别 / b 跳过): ", {"a", "b"})
    if choice != "a":
        console.print("[dim]已跳过音频识别兜底[/dim]")
        return

    try:
        from asr_fallback_module import DEFAULT_MODEL_PATH, SenseVoiceTranscriber, process_url
    except Exception as exc:
        console.print(f"[red]ASR 模块不可用: {exc}[/red]")
        return

    model_path = Path(os.environ.get("VIDEO_SUB_MD_ASR_MODEL") or os.environ.get("SENSEVOICE_MODEL_PATH") or DEFAULT_MODEL_PATH)
    asr_lang = lang or "auto"

    try:
        transcriber = SenseVoiceTranscriber(model_path=model_path, device=os.environ.get("VIDEO_SUB_MD_ASR_DEVICE", "auto"))
    except Exception as exc:
        console.print(f"[red]加载 SenseVoice 模型失败: {exc}[/red]")
        return

    for r in candidates:
        url = r.source_url
        if not url and r.video_id:
            if r.platform == "bilibili":
                url = f"https://www.bilibili.com/video/{r.video_id}/"
            elif r.platform == "youtube":
                url = f"https://www.youtube.com/watch?v={r.video_id}"
        if not url:
            continue

        try:
            console.print(f"[cyan]ASR 兜底:[/cyan] {r.title or url}")
            output_path = process_url(
                url=url,
                transcriber=transcriber,
                output_dir=r.output_dir or _asr_output_dir_for(r.platform),
                language=asr_lang,
                keep_audio=False,
                cookie_file=None,
                cookies_from_browser=os.environ.get("VIDEO_SUB_MD_ASR_COOKIES_FROM_BROWSER", ""),
            )
            r.status = "success"
            r.language = f"ASR:{asr_lang}"
            r.filepath = output_path
            r.error = None
            if not r.title:
                r.title = output_path.stem
            console.print(f"[green]  ✓ ASR 已生成:[/green] {output_path}")
        except Exception as exc:
            r.error = f"字幕下载失败；ASR 也失败: {exc}"
            console.print(f"[red]  ✗ ASR 失败:[/red] {r.title or url} - {exc}")


def _bilibili_video_url(bvid: str) -> str:
    return f"https://www.bilibili.com/video/{bvid}/"


def _bilibili_video_page_url(bvid: str, page: int) -> str:
    return f"https://www.bilibili.com/video/{bvid}/?p={page}"


def _dedupe_urls(urls: List[str]) -> List[str]:
    seen = set()
    unique = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def _safe_folder_name(name: str, fallback: str = "playlist") -> str:
    cleaned = re.sub(r"[\u2028\u2029\r\n\t]+", " ", str(name or fallback))
    for ch in '\\/:*?"<>|':
        cleaned = cleaned.replace(ch, "_")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._")
    return add_date_prefix((cleaned or fallback)[:120])


def _prompt_batch_folder() -> str:
    console.print("[bold]本批是否新建统一文件夹？[/bold]")
    console.print("[dim]输入名称创建；直接回车准备跳过。[/dim]")
    name = input("  文件夹名> ").strip()
    if not name:
        name = input("  确认跳过？直接回车确认，或现在输入文件夹名称> ").strip()
    if not name:
        console.print("[dim]本批不新建统一文件夹。[/dim]")
        return ""
    folder = _safe_folder_name(name, "batch")
    console.print(f"[dim]本批将保存到各平台目录下的文件夹: {folder}[/dim]")
    return folder


def _with_batch_folder(base_dir: Path, batch_folder: str) -> Path:
    return base_dir / batch_folder if batch_folder else base_dir


def _dedupe_bilibili_tasks(tasks: List[tuple[str, Path]]) -> List[tuple[str, Path]]:
    seen = set()
    unique = []
    for url, output_dir in tasks:
        key = (url, str(output_dir).lower())
        if key not in seen:
            seen.add(key)
            unique.append((url, output_dir))
    return unique


def _youtube_playlist_id(url: str) -> str:
    """Return the YouTube playlist id carried by either playlist or watch URLs."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc.lower() not in {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "music.youtube.com",
        }:
            return ""
        return (urllib.parse.parse_qs(parsed.query).get("list") or [""])[0].strip()
    except (TypeError, ValueError):
        return ""


def _expand_youtube_playlists(
    urls: List[str],
    output_base_dir: Path,
    youtube_cookie_file: Optional[Path] = None,
) -> List[tuple[str, Path]]:
    """Expand YouTube playlist/watch-with-list URLs into ordinary video tasks."""
    if not urls:
        return []

    import yt_dlp

    console.print("[dim]正在检测 YouTube 播放列表...[/dim]")
    expanded: List[tuple[str, Path]] = []
    playlist_cache: dict[str, tuple[str, List[str]]] = {}

    for url in urls:
        playlist_id = _youtube_playlist_id(url)
        if not playlist_id:
            expanded.append((url, output_base_dir))
            continue

        try:
            if playlist_id not in playlist_cache:
                playlist_url = "https://www.youtube.com/playlist?" + urllib.parse.urlencode(
                    {"list": playlist_id}
                )
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "skip_download": True,
                    "extract_flat": "in_playlist",
                    "ignoreerrors": True,
                }
                if youtube_cookie_file:
                    ydl_opts["cookiefile"] = str(youtube_cookie_file)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(playlist_url, download=False)

                if not info:
                    raise RuntimeError("yt-dlp 没有返回播放列表信息")

                video_urls: List[str] = []
                for entry in info.get("entries") or []:
                    if not entry:
                        continue
                    video_id = str(entry.get("id") or "").strip()
                    if re.fullmatch(r"[0-9A-Za-z_-]{11}", video_id):
                        video_urls.append(f"https://www.youtube.com/watch?v={video_id}")

                video_urls = _dedupe_urls(video_urls)
                if not video_urls:
                    raise RuntimeError("播放列表中没有可解析的视频")

                playlist_title = str(info.get("title") or f"YouTube播放列表_{playlist_id}")
                playlist_cache[playlist_id] = (playlist_title, video_urls)

            playlist_title, video_urls = playlist_cache[playlist_id]
            playlist_dir = output_base_dir / _safe_folder_name(playlist_title, "YouTube播放列表")
            console.print(
                f"[yellow]检测到 YouTube 播放列表[/yellow]: {playlist_title}，共 {len(video_urls)} 个视频。"
            )
            console.print(f"[dim]将保存到: {playlist_dir}[/dim]")
            expanded.extend((video_url, playlist_dir) for video_url in video_urls)
        except Exception as exc:
            # A watch URL can still be processed as one video if playlist lookup fails.
            try:
                from core.youtube.extractor import extract_video_id

                video_id = extract_video_id(url)
                fallback_url = f"https://www.youtube.com/watch?v={video_id}"
            except ValueError:
                fallback_url = url
            console.print(f"[yellow]YouTube 播放列表检测失败，按单个链接处理: {url} ({exc})[/yellow]")
            expanded.append((fallback_url, output_base_dir))

    return _dedupe_bilibili_tasks(expanded)


def _skip_existing_youtube_tasks(tasks: List[tuple[str, Path]]) -> List[tuple[str, Path]]:
    """Skip videos already represented by Markdown files in their playlist folder."""
    if not tasks:
        return []

    from core.youtube.extractor import extract_video_id

    ids_by_output_dir: dict[Path, set[str]] = {}
    remaining: List[tuple[str, Path]] = []
    skipped = 0

    for url, output_dir in tasks:
        resolved_dir = output_dir.resolve()
        if resolved_dir not in ids_by_output_dir:
            existing_ids: set[str] = set()
            if resolved_dir.is_dir():
                for markdown_path in resolved_dir.glob("*.md"):
                    try:
                        content = markdown_path.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        continue
                    existing_ids.update(
                        re.findall(r"youtube\.com/watch\?v=([0-9A-Za-z_-]{11})", content)
                    )
                    existing_ids.update(
                        re.findall(r'data-video-id="([0-9A-Za-z_-]{11})"', content)
                    )
            ids_by_output_dir[resolved_dir] = existing_ids

        try:
            video_id = extract_video_id(url)
        except ValueError:
            remaining.append((url, output_dir))
            continue

        if video_id in ids_by_output_dir[resolved_dir]:
            skipped += 1
        else:
            remaining.append((url, output_dir))

    if skipped:
        console.print(f"[dim]断点续传：已跳过 {skipped} 个已有 YouTube Markdown。[/dim]")
    return remaining


def _expand_bilibili_playlists(urls: List[str], output_base_dir: Path) -> List[tuple[str, Path]]:
    """Ask whether Bilibili collections/seasons should be expanded to all videos."""
    if not urls:
        return []

    from core.bilibili.extractor import extract_bvid, extract_collection_info, extract_page_index, is_collection_url
    from core.bilibili.metadata import fetch_collection_videos, fetch_video_meta, fetch_video_ugc_season

    console.print("[dim]正在检测 B站合集/播放列表/分P选集...[/dim]")
    expanded: List[tuple[str, Path]] = []
    current_only_for_rest = False
    for url in urls:
        if current_only_for_rest:
            expanded.append((url, output_base_dir))
            continue

        try:
            title = ""
            bvids: List[str] = []
            page_urls: List[str] = []
            current_bvid = extract_bvid(url) or ""

            if is_collection_url(url):
                collection_type, params = extract_collection_info(url)
                bvids = fetch_collection_videos(collection_type, params)
                title = f"{collection_type} {params.get('sid') or params.get('mlid') or ''}".strip()
            elif current_bvid:
                title, bvids = fetch_video_ugc_season(current_bvid)
                meta = fetch_video_meta(current_bvid)
                if len(meta.pages) > 1:
                    title = meta.title
                    bvids = []
                    page_urls = [_bilibili_video_page_url(current_bvid, page.page) for page in meta.pages]

            item_count = len(page_urls) if page_urls else len(bvids)
            if item_count <= 1:
                expanded.append((url, output_base_dir))
                continue

            current_hint = ""
            if current_bvid and current_bvid in bvids:
                current_hint = f"当前视频位于第 {bvids.index(current_bvid) + 1}/{len(bvids)} 个"
            elif page_urls:
                current_page = extract_page_index(url)
                current_hint = f"当前分 P 位于第 {current_page}/{len(page_urls)} 个"

            console.print()
            console.print(
                f"[yellow]检测到 B站合集/播放列表/分P选集[/yellow]: {title or '未命名'}，共 {item_count} 个视频。"
            )
            if current_hint:
                console.print(f"[dim]{current_hint}[/dim]")
            choice = input("是否下载全部？(a 全部 / b 仅当前 / q 本批都仅当前): ").strip().lower()
            if choice == "a":
                playlist_dir = output_base_dir / _safe_folder_name(title, "Bilibili播放列表")
                if page_urls:
                    expanded.extend((page_url, playlist_dir) for page_url in page_urls)
                else:
                    expanded.extend((_bilibili_video_url(bvid), playlist_dir) for bvid in bvids)
                console.print(f"[dim]将保存到: {playlist_dir}[/dim]")
            else:
                if choice == "q":
                    current_only_for_rest = True
                    console.print("[dim]本批后续 B站合集/播放列表/分P选集将自动仅下载当前视频。[/dim]")
                expanded.append((url, output_base_dir))
        except Exception as exc:
            console.print(f"[yellow]播放列表检测失败，按单个视频处理: {url} ({exc})[/yellow]")
            expanded.append((url, output_base_dir))

    return _dedupe_bilibili_tasks(expanded)


def _process_downloads(
    urls: List[str],
    lang: Optional[str],
    max_concurrent: int,
    effective_cookie: str,
    youtube_cookie_file: Optional[Path] = None,
):
    """处理单次下载任务"""
    # 过滤 typer 单命令模式下误传的命令名
    if urls and urls[0] == "download":
        urls = urls[1:] if len(urls) > 1 else []

    # 按平台分组
    bilibili_urls = []
    youtube_urls = []
    coursera_urls = []
    douyin_urls = []
    for url in urls:
        platform = detect_platform(url)
        if platform == "bilibili":
            bilibili_urls.append(url)
        elif platform == "youtube":
            youtube_urls.append(url)
        elif platform == "coursera":
            coursera_urls.append(url)
        elif platform == "douyin":
            douyin_urls.append(url)
        else:
            console.print(f"[yellow]⚠[/yellow] 无法识别平台，跳过: {url}")

    has_valid_urls = bool(bilibili_urls or youtube_urls or coursera_urls or douyin_urls)
    batch_folder = _prompt_batch_folder() if has_valid_urls else ""
    bilibili_output_base = _with_batch_folder(BILIBILI_OUTPUT_DIR, batch_folder)
    youtube_output_base = _with_batch_folder(YOUTUBE_OUTPUT_DIR, batch_folder)
    coursera_output_base = _with_batch_folder(COURSERA_OUTPUT_DIR, batch_folder)
    douyin_output_base = _with_batch_folder(DOUYIN_OUTPUT_DIR, batch_folder)

    bilibili_tasks = _expand_bilibili_playlists(bilibili_urls, bilibili_output_base)
    youtube_tasks = _expand_youtube_playlists(
        youtube_urls,
        youtube_output_base,
        youtube_cookie_file=youtube_cookie_file,
    )
    youtube_tasks = _skip_existing_youtube_tasks(youtube_tasks)

    coursera_expand_errors = []
    if coursera_urls:
        expanded_coursera_urls = []
        seen_coursera = set()
        from core.coursera.downloader import CourseraDownloader

        coursera_downloader = CourseraDownloader(
            cookies_from_browser=os.environ.get("COURSERA_COOKIES_FROM_BROWSER", "")
        )
        for url in coursera_urls:
            try:
                course_slugs = coursera_downloader.expand_to_course_slugs(url)
                for slug in course_slugs:
                    if slug not in seen_coursera:
                        seen_coursera.add(slug)
                        expanded_coursera_urls.append(slug)
            except Exception as exc:
                coursera_expand_errors.append(
                    DownloadResult(
                        platform="coursera",
                        source_url=url,
                        title=url[:80],
                        status="error",
                        error=str(exc),
                        output_dir=coursera_output_base,
                    )
                )
        coursera_urls = expanded_coursera_urls

    if not bilibili_tasks and not youtube_tasks and not coursera_urls and not douyin_urls:
        console.print("[red]错误：没有有效的视频链接[/red]")
        if coursera_expand_errors:
            report = BatchReport(
                total=len(coursera_expand_errors),
                success=0,
                failed=len(coursera_expand_errors),
                results=coursera_expand_errors,
            )
            _write_download_report(report)
            return report
        return

    console.print(
        f"[dim]Bilibili: {len(bilibili_tasks)} 个 | YouTube: {len(youtube_tasks)} 个 | Coursera: {len(coursera_urls)} 个 | Douyin: {len(douyin_urls)} 个 | "
        f"并发: {max_concurrent}[/dim]\n"
    )

    # 构建任务列表
    tasks = []
    for url, output_dir in bilibili_tasks:
        tasks.append(("bilibili", url, output_dir))
    for url, output_dir in youtube_tasks:
        tasks.append(("youtube", url, output_dir))
    for url in coursera_urls:
        tasks.append(("coursera", url, coursera_output_base))

    # 异步批量下载
    async def _batch():
        semaphore = asyncio.Semaphore(max_concurrent)
        results: List[Optional[DownloadResult]] = [None] * len(tasks)
        total_tasks = len(tasks)

        async def _run(index: int, platform: str, url: str, output_dir: Path):
            async with semaphore:
                await asyncio.sleep(0.3)
                try:
                    if platform == "bilibili":
                        result = await download_bilibili_task(url, output_dir, lang, effective_cookie)
                    elif platform == "youtube":
                        result = await download_youtube_task(
                            url,
                            output_dir,
                            lang,
                            youtube_cookie_file=youtube_cookie_file,
                        )
                    else:
                        result = await download_coursera_task(url, output_dir, lang)
                    return index, result
                except Exception as e:
                    return index, DownloadResult(
                        platform=platform,
                        source_url=url,
                        title=url[:50],
                        status="error",
                        error=str(e),
                        output_dir=output_dir,
                    )

        coros = [_run(i, p, u, o) for i, (p, u, o) in enumerate(tasks)]
        completed = 0
        print(f"下载进度：0/{total_tasks}", end="", flush=True)
        for coro in asyncio.as_completed(coros):
            index, result = await coro
            results[index] = result
            completed += 1
            print(f"\r下载进度：{completed}/{total_tasks}", end="", flush=True)
        print()
        return [r for r in results if r is not None]

    results = coursera_expand_errors + asyncio.run(_batch())
    results.extend(download_douyin_batch(douyin_urls, douyin_output_base, lang))

    # 统计
    success = sum(1 for r in results if r.status == "success")
    report = BatchReport(
        total=len(results),
        success=success,
        failed=len(results) - success,
        results=results,
    )

    # 报告表格
    table = Table(title="下载报告", show_header=True, header_style="bold magenta")
    table.add_column("状态", style="bold")
    table.add_column("数量", justify="right")
    table.add_column("比例")
    if report.total > 0:
        table.add_row("[green]成功", str(report.success), f"{report.success/report.total*100:.1f}%")
        table.add_row("[red]失败", str(report.failed), f"{report.failed/report.total*100:.1f}%")
    else:
        table.add_row("[green]成功", "0", "0.0%")
        table.add_row("[red]失败", "0", "0.0%")
    table.add_row("总计", str(report.total), "100.0%")
    console.print()
    console.print(table)

    # 可点击文件列表
    success_results = [r for r in results if r.status == "success" and r.filepath]
    if success_results:
        file_table = Table(title="下载结果")
        file_table.add_column("平台", style="cyan")
        file_table.add_column("视频", style="green")
        file_table.add_column("文件路径")
        for r in success_results:
            # 生成 Obsidian URI，优先使用 vault+file 模式
            filepath_str = str(r.filepath).replace("\\", "/")
            vault_root_str = str(OBSIDIAN_VAULT_ROOT).replace("\\", "/")
            vault = urllib.parse.quote(OBSIDIAN_VAULT_NAME)
            
            # 检查文件是否在 vault 根目录下（字符串前缀匹配，避免 relative_to 的大小写问题）
            if filepath_str.lower().startswith(vault_root_str.lower() + "/"):
                rel_path = filepath_str[len(vault_root_str) + 1 :]
                if rel_path.endswith(".md"):
                    rel_path = rel_path[:-3]
                file = urllib.parse.quote(rel_path, safe="/")
                obsidian_url = f"obsidian://open?vault={vault}&file={file}"
                path_text = Text(r.filepath.name, style=f"link {obsidian_url}")
            else:
                # fallback: 文件不在 vault 下，用 file:// 链接
                file_link = r.filepath.parent.resolve().as_uri()
                path_text = Text(r.filepath.name, style=f"link {file_link}")
                console.print(f"[yellow]警告:[/yellow] {r.filepath.name} 不在 Obsidian vault 路径下，使用 file:// 链接")
            
            file_table.add_row(platform_tag(r.platform), r.title or "-", path_text)
        console.print()
        console.print(file_table)

    # 失败详情
    failed_results = [r for r in results if r.status != "success" and r.error]
    if failed_results:
        console.print()
        for r in failed_results:
            console.print(f"[red]✗[/red] {platform_tag(r.platform)} {r.title or r.video_id or '未知'}: {r.error}")
        _maybe_run_asr_fallback(failed_results, lang)
        success = sum(1 for r in results if r.status == "success")
        report = BatchReport(
            total=len(results),
            success=success,
            failed=len(results) - success,
            results=results,
        )
        success_results = [r for r in results if r.status == "success" and r.filepath]
        still_failed = [r for r in results if r.status != "success" and r.error]
        if len(still_failed) != len(failed_results):
            console.print()
            console.print(f"[dim]ASR 后结果: 成功 {report.success} / 失败 {report.failed} / 总计 {report.total}[/dim]")

    # CSV 报告
    _write_download_report(report)

    # 询问是否生成分析
    ai_mode_label = "本地模型" if _current_ai_mode == "local" else "DeepSeek API"
    if success_results and (_current_ai_mode == "local" or DEEPSEEK_API_KEY):
        console.print()
        console.print(f"[dim]当前 AI 模式: {ai_mode_label}[/dim]")
        choice_analysis = input("是否为下载的字幕生成深度分析？(a 是 / b 否): ").strip().lower()

        # 只有翻译模块可用时才询问翻译
        if translate_subtitle_with_deepseek:
            choice_translate = input("是否为下载的字幕生成翻译？(a 是 / b 否): ").strip().lower()
        else:
            choice_translate = "b"
            console.print("[dim]提示: 翻译模块不可用，已跳过翻译选项[/dim]")

        do_analysis = choice_analysis == "a"
        do_translate = choice_translate == "a"

        if do_analysis or do_translate:
            console.print()
            if do_analysis:
                analysis_label = "本地模型" if _current_ai_mode == "local" else "Pro"
                console.print(f"[dim]正在生成深度分析 ({analysis_label})...[/dim]")
            if do_translate:
                translate_label = "本地模型" if _current_ai_mode == "local" else "Flash"
                console.print(f"[dim]正在生成翻译 ({translate_label})...[/dim]")
            
            for r in success_results:
                if r.filepath and r.filepath.exists():
                    try:
                        # 保存原始文件内容（在添加分析之前）
                        original_file_content = r.filepath.read_text(encoding="utf-8")
                        
                        # 提取纯字幕内容用于翻译（去除 frontmatter 和已有分析内容）
                        subtitle_content = original_file_content
                        content_normalized = original_file_content.replace('\r\n', '\n').replace('\r', '\n')
                        subtitle_content = _extract_subtitle_body(content_normalized)
                        
                        if do_analysis:
                            summary = generate_summary_with_deepseek(original_file_content, r.title or "")
                            if summary:
                                add_summary_to_file(r.filepath, summary)
                                console.print(f"[dim]  ✓ 分析完成: {r.filepath.name}[/dim]")
                            else:
                                console.print(f"[yellow]  ✗ 分析失败: {r.filepath.name}[/yellow]")
                        
                        if do_translate and translate_subtitle_with_deepseek:
                            # 使用提取的纯字幕内容翻译，而不是整个文件内容
                            translation = translate_subtitle_with_deepseek(
                                subtitle_content, 
                                video_title=r.title or "",
                                api_key=DEEPSEEK_API_KEY,
                                api_url=DEEPSEEK_API_URL,
                                model=DEEPSEEK_FLASH_MODEL
                            )
                            if translation:
                                add_translation_to_file(r.filepath, translation, subtitle_content)
                                console.print(f"[dim]  ✓ 翻译完成: {r.filepath.name}[/dim]")
                            else:
                                console.print(f"[yellow]  ✗ 翻译失败: {r.filepath.name}[/yellow]")
                    except Exception as e:
                        console.print(f"[red]  处理失败: {r.filepath.name} - {e}[/red]")
            
            if do_analysis:
                console.print("[dim]深度分析完成[/dim]")
            if do_translate:
                console.print("[dim]翻译完成[/dim]")
        else:
            console.print("[dim]已跳过分析生成[/dim]")
    elif success_results and not DEEPSEEK_API_KEY:
        console.print()
        console.print("[dim]提示: 未设置 DEEPSEEK_API_KEY 环境变量，如需生成分析或翻译请先设置[/dim]")

    _maybe_merge_downloaded_markdown(success_results)

    return report


@app.command()
def download(
    urls: Optional[List[str]] = typer.Argument(None, help="视频链接（支持 Bilibili + YouTube + Coursera 混合）"),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help="指定语言代码，如 zh, en"),
    max_concurrent: int = typer.Option(MAX_CONCURRENT, "--max-concurrent", "-c", help="最大并发数"),
    cookie: Optional[str] = typer.Option(None, "--cookie", help="Bilibili SESSDATA Cookie"),
    youtube_cookies: Optional[Path] = typer.Option(
        None,
        "--youtube-cookies",
        help="YouTube Netscape Cookie 文件路径",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
):
    """下载 Bilibili + YouTube + Coursera 字幕为 Markdown，支持混合链接，按 q 退出"""
    console.print(Panel.fit(
        "[bold cyan]video-sub-md[/bold cyan] — 统一视频字幕下载器\n"
        "[dim]Bilibili + YouTube + Coursera · Markdown 输出 · Ctrl+点击跳转 Obsidian · 按 q 退出[/dim]",
        border_style="cyan",
    ))

    # 优先命令行参数，其次环境变量，最后配置文件中的默认值
    effective_cookie = cookie or os.environ.get("BILI_COOKIE") or os.environ.get("BILIBILI_SESSDATA") or DEFAULT_SESSDATA or ""
    youtube_cookies = _resolve_youtube_cookie_file(youtube_cookies)
    if youtube_cookies:
        console.print(f"[dim]已启用 YouTube Cookie: {youtube_cookies}[/dim]")
    else:
        console.print("[dim]未配置 YouTube Cookie；登录/年龄限制视频可能无法访问。[/dim]")

    from core.bilibili.metadata import set_cookie

    # 设置翻译模块默认模式
    if translate_subtitle_with_deepseek:
        from core import translator as _translator
        _translator.set_defaults(
            api_key=DEEPSEEK_API_KEY,
            api_url=DEEPSEEK_API_URL,
            model=DEEPSEEK_FLASH_MODEL,
            mode=DEFAULT_AI_MODE,
            local_model_path=LOCAL_MODEL_PATH,
        )

    def _check_cookie_validity(cookie_value: str) -> bool:
        """检查 SESSDATA 是否能让 B站识别为登录状态。"""
        if not cookie_value:
            return False
        try:
            import requests
            from config import build_headers
            from core.bilibili.http import create_bilibili_session

            session = create_bilibili_session()
            resp = session.get(
                "https://api.bilibili.com/x/web-interface/nav",
                headers=build_headers(cookie_value),
                timeout=5,
            )
            resp.raise_for_status()
            nav = resp.json()
            return bool(nav.get("data", {}).get("isLogin"))
        except Exception:
            return False

    # 选择 AI 模式
    _choose_ai_mode()
    if translate_subtitle_with_deepseek:
        from core import translator as _translator
        _translator.set_defaults(mode=_current_ai_mode)

    # Cookie 设置与提示
    if effective_cookie:
        raw_len = len(effective_cookie)
        set_cookie(effective_cookie)
        import core.bilibili.metadata as _meta
        clean_len = len(_meta._global_cookie)
        if clean_len == 0:
            console.print(f"[red]警告: Cookie 过滤后为空 (原始值: {repr(effective_cookie)}), 字幕可能无法获取[/red]")
        elif clean_len < raw_len * 0.8:
            console.print(f"[yellow]警告: Cookie 过滤后长度从 {raw_len} 变为 {clean_len}，部分字符被移除[/yellow]")
        else:
            console.print(f"[dim]已设置登录 Cookie (原始 {raw_len} 字符, 有效 {clean_len} 字符)[/dim]")

        # 默认跳过启动联网校验，避免未开 VPN/代理失效/运营商直连慢时卡在启动页。
        if os.environ.get("VIDEO_SUB_MD_CHECK_BILI_COOKIE", "").strip() == "1":
            console.print("[dim]正在快速校验 B站 Cookie...[/dim]")
            if not _check_cookie_validity(effective_cookie):
                console.print("[yellow]警告: 当前 Cookie 未通过 B站登录校验，部分需要登录的字幕（含大部分 AI 生成字幕）可能无法获取[/yellow]")
                console.print("[dim]提示: 请从浏览器开发者工具复制最新的 SESSDATA 值，或设置 BILI_COOKIE 环境变量[/dim]")

        console.print("[dim]如需临时更新 B站 SESSDATA，可输入 1 后回车再粘贴；也可直接粘贴 SESSDATA；直接回车继续。[/dim]")
        cookie_choice = input("  更新 SESSDATA? (1/直接粘贴/回车)> ").strip()
        if cookie_choice:
            user_cookie = input("  新 SESSDATA> ").strip() if cookie_choice == "1" else cookie_choice
            if user_cookie:
                effective_cookie = user_cookie
                set_cookie(effective_cookie)
                import core.bilibili.metadata as _meta
                console.print(f"[dim]已更新本次运行的登录 Cookie ({len(_meta._global_cookie)} 字符)[/dim]")
            else:
                console.print("[dim]未输入新 SESSDATA，继续使用原 Cookie[/dim]")
    else:
        console.print("[dim]提示：如需下载登录后才能看到的字幕，请输入 SESSDATA（直接回车则以游客身份运行）：[/dim]")
        user_cookie = input("  SESSDATA> ").strip()
        if user_cookie:
            effective_cookie = user_cookie
            set_cookie(effective_cookie)
            import core.bilibili.metadata as _meta
            console.print(f"[dim]已设置登录 Cookie ({len(_meta._global_cookie)} 字符)[/dim]")

    # 循环处理下载任务
    cli_mode = bool(urls)
    while True:
        current_urls = urls if urls else []
        urls = None  # 重置，下次进入交互模式

        # 交互式输入（首次或后续循环）
        if not current_urls:
            console.print("\n" + "-" * 50)
            console.print("  [bold]粘贴视频链接[/bold]")
            console.print("  · 支持 Bilibili + YouTube + Coursera 混合粘贴")
            console.print("  · 空格、逗号、换行分隔均可")
            console.print("  · 输入空行结束，按 q 退出")
            console.print("-" * 50)
            raw_lines = []
            while True:
                line = input("  > ")
                if line.strip().lower() == "q":
                    console.print("\n[dim]再见！[/dim]")
                    raise typer.Exit(0)
                if line.strip() == "":
                    break
                raw_lines.append(line)
            if not raw_lines:
                console.print("[red]错误：没有输入任何链接[/red]")
                continue
            all_text = "\n".join(raw_lines)
            parts = [p.strip() for p in all_text.replace(",", " ").split() if p.strip()]
            seen = set()
            current_urls = []
            for p in parts:
                if p not in seen:
                    seen.add(p)
                    current_urls.append(p)
            console.print(f"[blue]ℹ[/blue] 解析到 {len(current_urls)} 个链接\n")

        # 处理下载
        report = _process_downloads(
            current_urls,
            lang,
            max_concurrent,
            effective_cookie,
            youtube_cookie_file=youtube_cookies,
        )
        
        # 检查是否有失败（非循环模式下）
        if cli_mode:
            if report and report.failed > 0:
                raise typer.Exit(1)
            return


def _write_download_report(report: BatchReport):
    path = DEFAULT_OUTPUT_DIR / "_download_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run = {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "created_at": now,
        "summary": {
            "total": report.total,
            "success": report.success,
            "failed": report.failed,
        },
        "results": [
            {
                "platform": r.platform,
                "source_url": r.source_url,
                "video_id": r.video_id,
                "title": r.title,
                "status": r.status,
                "language": r.language or "",
                "filepath": str(r.filepath) if r.filepath else "",
                "output_dir": str(r.output_dir) if r.output_dir else "",
                "error": r.error or "",
            }
            for r in report.results
        ],
    }

    data = {"schema_version": 1, "runs": []}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
                if not isinstance(data.get("runs"), list):
                    data["runs"] = []
        except json.JSONDecodeError:
            backup = path.with_suffix(f".broken_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            path.rename(backup)
            console.print(f"[yellow]旧报告 JSON 解析失败，已备份为: {backup}[/yellow]")

    data["schema_version"] = 1
    data["updated_at"] = now
    data.setdefault("runs", []).append(run)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"\n[dim]报告已追加保存: {path}[/dim]")


if __name__ == "__main__":
    app()
