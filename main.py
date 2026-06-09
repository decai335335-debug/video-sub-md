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
)
from models import DownloadResult, BatchReport

console = Console(force_terminal=True)
app = typer.Typer(add_completion=False)


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

    # 优先命令行参数，其次环境变量
    effective_cookie = cookie or os.environ.get("BILI_COOKIE") or os.environ.get("BILIBILI_SESSDATA") or ""

    # Cookie 设置与提示
    if effective_cookie:
        from core.bilibili.metadata import set_cookie, _global_cookie
        raw_len = len(effective_cookie)
        set_cookie(effective_cookie)
        clean_len = len(_global_cookie)
        if clean_len == 0:
            console.print("[red]警告: Cookie 过滤后为空，字幕可能无法获取[/red]")
        elif clean_len < raw_len * 0.8:
            console.print(f"[yellow]警告: Cookie 过滤后长度从 {raw_len} 变为 {clean_len}，部分字符被移除[/yellow]")
        else:
            console.print(f"[dim]已设置登录 Cookie (原始 {raw_len} 字符, 有效 {clean_len} 字符)[/dim]")
    else:
        console.print("[dim]提示：如需下载登录后才能看到的字幕，请用 --cookie 参数或 BILI_COOKIE 环境变量传入 SESSDATA[/dim]")

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
