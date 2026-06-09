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

    prompt = f"""你是一位精通认知科学、传播学和知识工程的深度内容分析师。请对以下视频字幕按四层解码模型进行分析。

视频标题：{video_title}

字幕内容：
{subtitle_content[:8000]}

## 四层解码模型

### 第一层：拓扑结构（Spatial Mapping）
将视频内容视为一张认知地图，完成以下任务：

1. **时间轴**：标记每个议题的起止时间，计算各议题时长占比
2. **逻辑骨架**：识别整体结构：线性递进 / 螺旋上升 / 树状分支 / 网状关联
3. **信息密度**：标出3个信息密度峰值段和3个低谷段，分析原因

### 第二层：语义提取（Semantic Extraction）
1. **核心命题**：用不超过20字概括视频的主命题（Thesis）
2. **支撑论据**：提取所有事实、数据、案例、引用
3. **概念图谱**：列出所有关键术语，定义其在视频语境中的含义

### 第三层：认知机制（Cognitive Architecture）
- **认知脚手架**：作者使用了哪些前置假设？观众需要具备什么先验知识？
- **注意力调度**：哪些段落使用了悬念、重复、对比、故事化来锚定注意力？
- **记忆锚点**：提取3个最可能被长期记住的"金句"或画面描述

### 第四层：批判性重构（Critical Reconstruction）
1. **反事实假设**：如果视频的核心结论是错误的，最可能的原因是什么？
2. **沉默的证据**：视频刻意回避或遗漏了哪些关键视角？
3. **适用边界**：这些内容在什么情境下会失效？

## 元认知安全锁
如果某部分分析因字幕信息不足无法完成，请明确标注 **[信息不足]**，禁止推测编造。

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
            "max_tokens": 800,
            "temperature": 0.7,
        }
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
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


@app.command()
def download(
    urls: Optional[List[str]] = typer.Argument(None, help="视频链接（支持 Bilibili + YouTube 混合）"),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help="指定语言代码，如 zh, en"),
    max_concurrent: int = typer.Option(MAX_CONCURRENT, "--max-concurrent", "-c", help="最大并发数"),
    cookie: Optional[str] = typer.Option(None, "--cookie", help="Bilibili SESSDATA Cookie"),
):
    """下载 Bilibili + YouTube 字幕为 Markdown，支持混合链接"""
    console.print(Panel.fit(
        "[bold cyan]video-sub-md[/bold cyan] — 统一视频字幕下载器\n"
        "[dim]Bilibili + YouTube · Markdown 输出 · Ctrl+点击跳转 Obsidian[/dim]",
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

    # 交互式输入
    if not urls:
        console.print("[dim]未检测到参数，进入交互模式...[/dim]\n")
        console.print("-" * 50)
        console.print("  [bold]粘贴视频链接[/bold]")
        console.print("  · 支持 Bilibili + YouTube 混合粘贴")
        console.print("  · 空格、逗号、换行分隔均可")
        console.print("  · 输入空行结束")
        console.print("-" * 50)
        raw_lines = []
        while True:
            line = input("  > ")
            if line.strip() == "":
                break
            raw_lines.append(line)
        all_text = "\n".join(raw_lines)
        parts = [p.strip() for p in all_text.replace(",", " ").split() if p.strip()]
        seen = set()
        urls = []
        for p in parts:
            if p not in seen:
                seen.add(p)
                urls.append(p)
        console.print(f"[blue]ℹ[/blue] 解析到 {len(urls)} 个链接\n")

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
        raise typer.Exit(1)

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

    if report.failed > 0:
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
