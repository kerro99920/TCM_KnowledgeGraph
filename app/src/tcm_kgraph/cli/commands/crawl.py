"""Crawler CLI commands."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from tcm_kgraph.core.config import get_settings
from tcm_kgraph.core.logging import setup_logging


console = Console()
app = typer.Typer(help="爬虫相关命令")


@app.command("medicine")
def crawl_medicine(
    pages: int = typer.Option(1, "--pages", "-p", help="爬取页数"),
    limit: int = typer.Option(0, "--limit", "-l", help="每页限制数量 (0=不限制)"),
    output: Path = typer.Option(None, "--output", "-o", help="输出目录"),
    export_excel: bool = typer.Option(False, "--excel", help="导出Excel文件"),
) -> None:
    """爬取中药信息"""
    settings = get_settings()
    setup_logging(level=settings.log_level)

    output_dir = output or settings.medicines_dir

    console.print(f"[bold]开始爬取中药信息[/bold]")
    console.print(f"  页数: {pages}")
    console.print(f"  输出目录: {output_dir}")

    async def run_crawl() -> None:
        from tcm_kgraph.crawlers import HttpClient, MedicineCrawler

        async with HttpClient(
            timeout=settings.crawler_timeout,
            max_retries=settings.crawler_max_retries,
            delay=settings.crawler_delay,
            concurrent_limit=settings.crawler_concurrent_limit,
        ) as client:
            crawler = MedicineCrawler(client, output_dir=output_dir)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("爬取中...", total=None)

                items = await crawler.crawl_all(
                    max_pages=pages,
                    items_per_page=limit if limit > 0 else None,
                    save_raw=True,
                )

                progress.update(task, completed=True)

            console.print(f"[green]完成! 共爬取 {len(items)} 条中药信息[/green]")

            if export_excel and items:
                import pandas as pd

                excel_path = settings.exports_dir / "medicines.xlsx"
                settings.exports_dir.mkdir(parents=True, exist_ok=True)

                df = pd.DataFrame(items)
                df.to_excel(excel_path, index=False)
                console.print(f"[green]Excel已导出: {excel_path}[/green]")

    asyncio.run(run_crawl())


@app.command("prescription")
def crawl_prescription(
    pages: int = typer.Option(1, "--pages", "-p", help="爬取页数"),
    limit: int = typer.Option(0, "--limit", "-l", help="每页限制数量 (0=不限制)"),
    output: Path = typer.Option(None, "--output", "-o", help="输出目录"),
    export_excel: bool = typer.Option(False, "--excel", help="导出Excel文件"),
) -> None:
    """爬取方剂信息"""
    settings = get_settings()
    setup_logging(level=settings.log_level)

    output_dir = output or settings.prescriptions_dir

    console.print(f"[bold]开始爬取方剂信息[/bold]")
    console.print(f"  页数: {pages}")
    console.print(f"  输出目录: {output_dir}")

    async def run_crawl() -> None:
        from tcm_kgraph.crawlers import HttpClient, PrescriptionCrawler

        async with HttpClient(
            timeout=settings.crawler_timeout,
            max_retries=settings.crawler_max_retries,
            delay=settings.crawler_delay,
            concurrent_limit=settings.crawler_concurrent_limit,
        ) as client:
            crawler = PrescriptionCrawler(client, output_dir=output_dir)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("爬取中...", total=None)

                items = await crawler.crawl_all(
                    max_pages=pages,
                    items_per_page=limit if limit > 0 else None,
                    save_raw=True,
                )

                progress.update(task, completed=True)

            console.print(f"[green]完成! 共爬取 {len(items)} 条方剂信息[/green]")

            if export_excel and items:
                import pandas as pd

                excel_path = settings.exports_dir / "prescriptions.xlsx"
                settings.exports_dir.mkdir(parents=True, exist_ok=True)

                df = pd.DataFrame(items)
                df.to_excel(excel_path, index=False)
                console.print(f"[green]Excel已导出: {excel_path}[/green]")

    asyncio.run(run_crawl())


@app.command("all")
def crawl_all(
    pages: int = typer.Option(1, "--pages", "-p", help="每种类型爬取页数"),
    export_excel: bool = typer.Option(True, "--excel/--no-excel", help="导出Excel文件"),
) -> None:
    """爬取所有类型数据 (中药+方剂)"""
    console.print("[bold]开始爬取所有数据[/bold]\n")

    # Crawl medicines
    console.print("[bold blue]1/2 爬取中药[/bold blue]")
    crawl_medicine(pages=pages, limit=0, output=None, export_excel=export_excel)

    console.print()

    # Crawl prescriptions
    console.print("[bold blue]2/2 爬取方剂[/bold blue]")
    crawl_prescription(pages=pages, limit=0, output=None, export_excel=export_excel)

    console.print("\n[bold green]全部完成![/bold green]")
