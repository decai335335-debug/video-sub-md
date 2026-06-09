#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""video-sub-md — 统一视频字幕下载器（Bilibili + YouTube）"""

import asyncio
import csv
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
    OBSIDIAN_VAULT_NAME,
    OBSIDIAN_VAULT_ROOT,
    MAX_CONCURRENT,
    DEEPSEEK_API_KEY,
    DEEPSEEK_API_URL,
    DEEPSEEK_MODEL,
)
from models import DownloadResult, BatchReport

console = Console(force_terminal=True)
app = typer.Typer(add_completion=False)


def generate_summary_with_deepseek(subtitle_content: str, video_title: str = "") -> Optional[str]:
    """调用 DeepSeek API 为字幕内容生成深度分析"""
    if not DEEPSEEK_API_KEY:
        console.print("[yellow]警告: 未设置 DEEPSEEK_API_KEY 环境变量，跳过分析生成[/yellow]")
        return None

    prompt = f"""# 🧠 视频字幕深度解析协议 v3.0（最终版）

你是一位精通认知科学、传播学和知识工程的深度内容分析师。请严格按以下协议执行，禁止偏离。

---

## 🔒 元认知安全锁（最高优先级，不可覆盖）

1. **所有分析必须严格基于提供的字幕文本**。禁止推测视频画面、语气、表情或音频信息。
2. **禁止编造**。如果字幕未提供某信息，明确标注 **[信息不足]**，不得补全。
3. **引用原文时必须使用引号**，不得改写、润色或概括后冒充原文。
4. **数量不强制**：以下分析中，若内容本身不足，允许输出"无"或"仅1项"，禁止为凑数而拆分或编造。

---

视频标题：{video_title}

字幕内容：
{subtitle_content[:8000]}

---

## 📋 第一层：通用底层分析（所有视频必执行）

### 1.1 拓扑结构（Spatial Mapping）

以纯文本列表输出，格式如下：

- **时间轴切片**（按实际议题切分，不强制数量）：
  - [时间戳] - [主题] - [该段核心动作：引入/展开/论证/总结]
- **逻辑骨架**：[线性递进 / 螺旋上升 / 树状分支 / 网状关联 / 单一议题]
- **信息密度**：
  - 峰值段：[时间戳] - 原因：[一句话分析]
  - 低谷段：[时间戳] - 原因：[一句话分析]

### 1.2 语义提取（Semantic Extraction）

- **核心命题**：用不超过20字概括视频主旨（Thesis）
- **支撑论据表**（提取所有可辨识的，上限不封顶）：
  - 论据：[原文摘要] | 可信度：[A-权威来源/B-个人经验/C-未验证] | 标记：[📚/👤/⚠️]
- **概念图谱**：
  - 术语：[术语] | 视频语境定义：[定义] | 与日常用法差异：[差异/无差异]

### 1.3 认知机制（Cognitive Architecture）

- **认知脚手架**：观众必须具备的先验知识（列出所有，不强制数量）
- **注意力调度**：哪些段落使用了以下技巧？各举一例原文：
  - 悬念：[原文]
  - 重复：[原文]
  - 对比：[原文]
  - 故事化：[原文]
- **记忆锚点**：提取最可能被长期记住的3句原文，分析其记忆编码机制（如：韵律/反差/具体意象）

### 1.4 批判性重构（Critical Reconstruction）

1. **反事实假设**：如果核心结论错误，最可能的原因是什么？
2. **沉默的证据**：视频刻意回避或遗漏了哪些关键视角？
3. **适用边界**：这些内容在什么情境下会失效？给出至少2个反例场景。

### 1.5 趣味叙事重构（Fun Narrative Reconstruction）【新增】
用**非学术的、有趣的**方式重新讲述这个视频的核心故事，要求：

- **类比引擎**：将技术概念映射到日常生活场景，至少3个类比（如：把"禁用异常"比作"手术室禁用'也许能行'"）
- **彩蛋挖掘**：提取视频中所有有趣的旁支细节、冷知识、个人轶事，至少3个，并解释它们如何服务于主线叙事
- **叙事节奏（电影化）**：用电影类型描述视频结构（如：灾难片→历史悬疑→动作片→哲学片）
- **一句话钩子**：用一句带有悬念或反差感的话概括视频，适合推荐给朋友

输出格式：轻松但不失准确，可适度使用emoji和比喻。可以联网搜索推理，类比举例，但禁止编造视频未提及的内容。

---

## 🔌 第二层：类型识别与条件激活

请基于内容特征自行判断视频类型，**只激活对应插件**：

### 若识别为【教学型】（传授技能/系统知识/操作步骤）→ 激活插件A

#### A1 学习路径重构
- **先决条件检查清单**：
  - [ ] 知识前提：[必须预先掌握的概念]
  - [ ] 工具前提：[需要的软件/硬件/环境]
  - [ ] 认知前提：[需要具备的思维方式]
- **核心知识模块**（按实际依赖关系排列，不强制数量）：
  - 模块：[名称] | 难度：⭐/⭐⭐/⭐⭐⭐ | 可独立学习：是/否 | 前置依赖：[模块名/无]
- **常见陷阱地图**：
  - 易错点：[描述] | 原文位置：[时间戳] | 纠正方法：[具体动作]

#### A2 知识晶体提取
- 提取所有可抽象为通用模式的知识点，格式：
  - 场景：[具体场景] | 视频解法：[步骤] | 通用模式：[底层逻辑] | 可迁移领域：[领域]

#### A3 效率审计
- **信噪比评估**：核心知识占比约___%，冗余内容（寒暄/铺垫/重复）占比约___%
- **最优学习策略**：
  - 若只看一遍：重点看 [时间戳] 段，因为 [理由]
  - 若看两遍：第二遍聚焦 [时间戳] 段，因为 [理由]

---

### 若识别为【观点型】（表达立场/说服受众/评论分析）→ 激活插件B

#### B1 论证拆解（Argument Tree）
以缩进文本树输出：

核心主张：[一句话]
├── 论据A：[描述]
│   ├── 支撑A1：[事实/数据] — 可信度：[A/B/C]
│   └── 支撑A2：[案例/引用]
├── 论据B：[描述]
│   └── 支撑B1：[...]
└── 🔴 隐含前提X：[未明说但必须成立的前提] ← 论证最脆弱点

#### B2 修辞与说服分析
提取所有可辨识的策略，格式：
- 策略：[权威背书/情感共鸣/虚假二分/幸存者偏差/其他] | 原文证据："[引用]" | 效果：[增强可信度/降低批判性/限制思考空间] | 识别难度：[低/中/高]

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

并额外输出：
- **段落属性标注**：哪些时间区间是知识传授，哪些是观点输出？
- **交界点分析**：知识→观点的转折标志是什么？观点→知识的过渡方式是什么？

请按以上格式输出深度分析内容："""

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
        
        # 检查是否因长度被截断
        finish_reason = result.get("choices", [{}])[0].get("finish_reason", "")
        if finish_reason == "length":
            console.print("[yellow]警告: API 输出达到长度限制，分析内容可能不完整[/yellow]")
        
        summary = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        return summary if summary else None
    except Exception as e:
        console.print(f"[red]调用 DeepSeek API 失败: {e}[/red]")
        return None


def add_summary_to_file(filepath: Path, summary: str):
    """将简介添加到字幕文件开头（位于 YAML frontmatter 之后）"""
    try:
        content = filepath.read_text(encoding="utf-8")
        # 找到 frontmatter 结束位置（第二个 ---）
        parts = content.split("---", 2)
        # 将多行简介转换为 Markdown 引用块格式
        summary_block = "\n> ".join([""] + summary.split("\n"))
        if len(parts) >= 3:
            # 有 frontmatter，在第二个 --- 之后插入简介
            frontmatter = parts[0] + "---" + parts[1] + "---"
            body = parts[2]
            new_content = frontmatter + f"\n\n> {summary_block}\n" + body
        else:
            # 没有 frontmatter，直接在开头插入
            new_content = f"> {summary_block}\n\n{content}"
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
    return "unknown"


def normalize_result(raw_result, platform: str) -> DownloadResult:
    """把平台特定的结果对象转换为通用格式"""
    return DownloadResult(
        platform=platform,
        video_id=getattr(raw_result, "bvid", "") or getattr(raw_result, "video_id", ""),
        title=getattr(raw_result, "title", ""),
        status=getattr(raw_result, "status", "error"),
        language=getattr(raw_result, "language", None) or None,
        filepath=getattr(raw_result, "filepath", None),
        error=getattr(raw_result, "error", None),
    )


async def download_bilibili_task(url: str, output_dir: Path, lang: Optional[str], cookie: str = "") -> DownloadResult:
    """异步包装 bilibili 下载"""
    from core.bilibili.downloader import download_one as bilibili_download
    from core.bilibili.metadata import set_cookie

    if cookie:
        set_cookie(cookie)
    result = await asyncio.to_thread(bilibili_download, url, output_dir, "md", lang)
    return normalize_result(result, "bilibili")


def _sync_youtube_download(meta, output_dir: Path, lang: Optional[str]):
    """同步包装器：在线程中运行 youtube 异步下载"""
    import asyncio
    from core.youtube.downloader import download_with_delay
    return asyncio.run(download_with_delay(meta, output_dir, lang))


async def download_youtube_task(url: str, output_dir: Path, lang: Optional[str]) -> DownloadResult:
    """异步包装 youtube 下载"""
    from core.youtube.metadata import fetch_metadata

    meta = await asyncio.to_thread(fetch_metadata, url)
    result = await asyncio.to_thread(_sync_youtube_download, meta, output_dir, lang)
    return normalize_result(result, "youtube")


def _process_downloads(urls: List[str], lang: Optional[str], max_concurrent: int, effective_cookie: str):
    """处理单次下载任务"""
    # 过滤 typer 单命令模式下误传的命令名
    if urls and urls[0] == "download":
        urls = urls[1:] if len(urls) > 1 else []

    # 按平台分组
    bilibili_urls = []
    youtube_urls = []
    for url in urls:
        platform = detect_platform(url)
        if platform == "bilibili":
            bilibili_urls.append(url)
        elif platform == "youtube":
            youtube_urls.append(url)
        else:
            console.print(f"[yellow]⚠[/yellow] 无法识别平台，跳过: {url}")

    if not bilibili_urls and not youtube_urls:
        console.print("[red]错误：没有有效的视频链接[/red]")
        return

    console.print(
        f"[dim]Bilibili: {len(bilibili_urls)} 个 | YouTube: {len(youtube_urls)} 个 | "
        f"并发: {max_concurrent}[/dim]\n"
    )

    # 构建任务列表
    tasks = []
    for url in bilibili_urls:
        tasks.append(("bilibili", url, BILIBILI_OUTPUT_DIR))
    for url in youtube_urls:
        tasks.append(("youtube", url, YOUTUBE_OUTPUT_DIR))

    # 异步批量下载
    async def _batch():
        semaphore = asyncio.Semaphore(max_concurrent)
        results: List[DownloadResult] = []

        async def _run(platform: str, url: str, output_dir: Path):
            async with semaphore:
                await asyncio.sleep(0.3)
                try:
                    if platform == "bilibili":
                        return await download_bilibili_task(url, output_dir, lang, effective_cookie)
                    else:
                        return await download_youtube_task(url, output_dir, lang)
                except Exception as e:
                    return DownloadResult(
                        platform=platform,
                        title=url[:50],
                        status="error",
                        error=str(e),
                    )

        coros = [_run(p, u, o) for p, u, o in tasks]
        results = await asyncio.gather(*coros)
        return results

    results = asyncio.run(_batch())

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
            try:
                rel_path = r.filepath.relative_to(OBSIDIAN_VAULT_ROOT).with_suffix("")
                rel_path_str = str(rel_path).replace("\\", "/")
                vault = urllib.parse.quote(OBSIDIAN_VAULT_NAME)
                file = urllib.parse.quote(rel_path_str, safe="/")
                obsidian_url = f"obsidian://open?vault={vault}&file={file}"
                path_text = Text(r.filepath.name, style=f"link {obsidian_url}")
            except ValueError:
                file_link = r.filepath.parent.resolve().as_uri()
                path_text = Text(r.filepath.name, style=f"link {file_link}")
            platform_tag = "[orange3]B站[/orange3]" if r.platform == "bilibili" else "[red]YouTube[/red]"
            file_table.add_row(platform_tag, r.title or "-", path_text)
        console.print()
        console.print(file_table)

    # 失败详情
    failed_results = [r for r in results if r.status != "success" and r.error]
    if failed_results:
        console.print()
        for r in failed_results:
            platform_tag = "[orange3]B站[/orange3]" if r.platform == "bilibili" else "[red]YouTube[/red]"
            console.print(f"[red]✗[/red] {platform_tag} {r.title or r.video_id or '未知'}: {r.error}")

    # CSV 报告
    _write_csv_report(report)

    # 询问是否生成分析
    if success_results and DEEPSEEK_API_KEY:
        console.print()
        choice = input("是否为下载的字幕生成深度分析？(a 是 / b 否): ").strip().lower()
        if choice == "a":
            console.print("\n[dim]正在生成深度分析...[/dim]")
            for r in success_results:
                if r.filepath and r.filepath.exists():
                    try:
                        content = r.filepath.read_text(encoding="utf-8")
                        summary = generate_summary_with_deepseek(content, r.title or "")
                        if summary:
                            add_summary_to_file(r.filepath, summary)
                            console.print(f"[dim]  已处理: {r.filepath.name}[/dim]")
                        else:
                            console.print(f"[yellow]  跳过（未生成分析）: {r.filepath.name}[/yellow]")
                    except Exception as e:
                        console.print(f"[red]  处理失败: {r.filepath.name} - {e}[/red]")
            console.print("[dim]分析生成完成[/dim]")
        elif choice == "b":
            console.print("[dim]已跳过分析生成[/dim]")
        else:
            console.print("[yellow]无效选择，已跳过分析生成[/yellow]")
    elif success_results and not DEEPSEEK_API_KEY:
        console.print()
        console.print("[dim]提示: 未设置 DEEPSEEK_API_KEY 环境变量，如需生成分析请先设置[/dim]")

    return report


@app.command()
def download(
    urls: Optional[List[str]] = typer.Argument(None, help="视频链接（支持 Bilibili + YouTube 混合）"),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help="指定语言代码，如 zh, en"),
    max_concurrent: int = typer.Option(MAX_CONCURRENT, "--max-concurrent", "-c", help="最大并发数"),
    cookie: Optional[str] = typer.Option(None, "--cookie", help="Bilibili SESSDATA Cookie"),
):
    """下载 Bilibili + YouTube 字幕为 Markdown，支持混合链接，按 q 退出"""
    console.print(Panel.fit(
        "[bold cyan]video-sub-md[/bold cyan] — 统一视频字幕下载器\n"
        "[dim]Bilibili + YouTube · Markdown 输出 · Ctrl+点击跳转 Obsidian · 按 q 退出[/dim]",
        border_style="cyan",
    ))

    # 优先命令行参数，其次环境变量，最后配置文件中的默认值
    effective_cookie = cookie or os.environ.get("BILI_COOKIE") or os.environ.get("BILIBILI_SESSDATA") or config.DEFAULT_SESSDATA or ""

    from core.bilibili.metadata import set_cookie

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
    else:
        console.print("[dim]提示：如需下载登录后才能看到的字幕，请输入 SESSDATA（直接回车则以游客身份运行）：[/dim]")
        user_cookie = input("  SESSDATA> ").strip()
        if user_cookie:
            effective_cookie = user_cookie
            set_cookie(effective_cookie)
            import core.bilibili.metadata as _meta
            console.print(f"[dim]已设置登录 Cookie ({len(_meta._global_cookie)} 字符)[/dim]")

    # 循环处理下载任务
    while True:
        current_urls = urls if urls else []
        urls = None  # 重置，下次进入交互模式

        # 交互式输入（首次或后续循环）
        if not current_urls:
            console.print("\n" + "-" * 50)
            console.print("  [bold]粘贴视频链接[/bold]")
            console.print("  · 支持 Bilibili + YouTube 混合粘贴")
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
        report = _process_downloads(current_urls, lang, max_concurrent, effective_cookie)
        
        # 检查是否有失败（非循环模式下）
        if urls and report and report.failed > 0:
            raise typer.Exit(1)


def _write_csv_report(report: BatchReport):
    path = Path("E:/Obsidian/主仓库/11-subtitles") / f"_download_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["platform", "video_id", "title", "status", "language", "filepath", "error"])
        for r in report.results:
            writer.writerow([
                r.platform,
                r.video_id,
                r.title,
                r.status,
                r.language or "",
                str(r.filepath) if r.filepath else "",
                r.error or "",
            ])
    console.print(f"\n[dim]报告已保存: {path}[/dim]")


if __name__ == "__main__":
    app()
