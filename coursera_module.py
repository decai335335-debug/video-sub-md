"""Standalone Coursera subtitle module runner.

Example:
    python coursera_module.py "https://www.coursera.org/learn/google-ai-fundamentals/home/module/1" --lang en
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from core.coursera.downloader import CourseraDownloader


app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def download(
    url: str = typer.Argument(..., help="Coursera course/module/lecture URL or course slug"),
    output: Path = typer.Option(
        Path("E:/Obsidian/主仓库/11-subtitles/Coursera"),
        "--output",
        "-o",
        help="Output directory for the merged Markdown file",
    ),
    lang: str = typer.Option("en", "--lang", "-l", help="Preferred subtitle language, e.g. en, zh-CN, ja"),
    cookie: str = typer.Option("", "--cookie", help="Raw Coursera Cookie header when login is required"),
    cookies_file: Path | None = typer.Option(None, "--cookies-file", help="Netscape cookies.txt file"),
    cookies_from_browser: str = typer.Option(
        "",
        "--cookies-from-browser",
        help="Load Coursera cookies from browser: chrome, edge, firefox, brave",
    ),
) -> None:
    downloader = CourseraDownloader(
        cookie=cookie,
        cookies_file=cookies_file,
        cookies_from_browser=cookies_from_browser,
    )
    console.print(f"[cyan]Scanning Coursera course...[/cyan] {url}")
    result = downloader.download_course_markdown(url, output, preferred_lang=lang)

    console.print(f"[green]Saved:[/green] {result.output_path}")
    console.print(
        f"[green]success {result.success_count}[/green] | "
        f"[yellow]skipped {result.skipped_count}[/yellow] | "
        f"[red]failed {result.failed_count}[/red]"
    )
    for lecture in result.course.lectures:
        status = "OK" if lecture.segments else f"SKIP {lecture.error}"
        console.print(f"{lecture.index:02d}. {lecture.title} [{lecture.selected_lang or '-'}] {status}")


if __name__ == "__main__":
    app()
