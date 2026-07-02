"""信息抽取 CLI 命令。"""

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from tcm_kgraph.core.config import get_settings
from tcm_kgraph.core.logging import setup_logging

console = Console()
app = typer.Typer(help="信息抽取命令")

INSTRUCTION = "请从以下中医文本中抽取知识图谱结构，包括实体与关系。"


@app.command("triples")
def extract_triples(
    input_dir: Path = typer.Argument(..., help="原始文本目录（每文件一个条目）"),
    output: Path = typer.Option(..., "--output", "-o", help="输出 Alpaca JSON 路径"),
    limit: int = typer.Option(0, "--limit", "-l", help="处理文件数限制 (0=不限制)"),
) -> None:
    """遍历目录抽取三元组，输出 Alpaca 格式（可直接用 db import-alpaca 导入）。"""
    settings = get_settings()
    setup_logging(level=settings.log_level)

    if not input_dir.is_dir():
        console.print(f"[red]输入目录不存在: {input_dir}[/red]")
        raise typer.Exit(1)

    async def run() -> None:
        from tcm_kgraph.core.dependencies import get_container, cleanup_container
        from tcm_kgraph.extraction.triple_extractor import TripleExtractor

        container = get_container()
        extractor = TripleExtractor(container.llm_client)

        files = sorted(f for f in input_dir.iterdir() if f.is_file())
        if limit > 0:
            files = files[:limit]
        console.print(f"[bold]三元组抽取[/bold] 共 {len(files)} 个文件")

        alpaca_list: list[dict] = []
        errors: list[str] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("抽取中...", total=len(files))
            for f in files:
                try:
                    text = f.read_text(encoding="utf-8", errors="replace").strip()
                    result = (
                        await extractor.extract(text)
                        if text
                        else {"entities": [], "relations": []}
                    )
                    alpaca_list.append({
                        "instruction": INSTRUCTION,
                        "input": text,
                        "output": json.dumps(result, ensure_ascii=False),
                    })
                except Exception as e:
                    errors.append(f"{f.name}: {e}")
                progress.update(task, advance=1)

        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as fp:
            json.dump(alpaca_list, fp, ensure_ascii=False, indent=2)

        console.print(f"\n[green]成功 {len(alpaca_list)} 条 -> {output}[/green]")
        if errors:
            console.print(f"[yellow]失败 {len(errors)} 条（前5）:[/yellow]")
            for e in errors[:5]:
                console.print(f"  - {e}")

        await cleanup_container()

    asyncio.run(run())
