"""Information extraction CLI commands."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from tcm_kgraph.core.config import get_settings
from tcm_kgraph.core.logging import setup_logging


console = Console()
app = typer.Typer(help="信息抽取命令")


@app.command("medicine")
def extract_medicine(
    input_dir: Path = typer.Option(None, "--input", "-i", help="输入目录"),
    output: Path = typer.Option(None, "--output", "-o", help="输出Excel路径"),
    limit: int = typer.Option(0, "--limit", "-l", help="处理文件数限制 (0=不限制)"),
) -> None:
    """从文本文件抽取中药实体"""
    settings = get_settings()
    setup_logging(level=settings.log_level)

    input_path = input_dir or settings.medicines_dir
    output_path = output or settings.exports_dir / "medicines_extracted.xlsx"

    if not input_path.exists():
        console.print(f"[red]输入目录不存在: {input_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]开始抽取中药实体[/bold]")
    console.print(f"  输入目录: {input_path}")
    console.print(f"  输出文件: {output_path}")

    async def run_extraction() -> None:
        from tcm_kgraph.core.dependencies import get_container, cleanup_container
        from tcm_kgraph.extraction import EntityExtractor

        container = get_container()
        extractor = EntityExtractor(container.llm_client)

        # Find all text files
        txt_files = list(input_path.glob("*.txt"))
        if limit > 0:
            txt_files = txt_files[:limit]

        console.print(f"  找到 {len(txt_files)} 个文件")

        results = []
        errors = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("抽取中...", total=len(txt_files))

            for txt_file in txt_files:
                try:
                    text = txt_file.read_text(encoding="utf-8")
                    data = await extractor.extract_medicine(text)
                    data["source_file"] = txt_file.name
                    results.append(data)
                except Exception as e:
                    errors.append({"file": txt_file.name, "error": str(e)})

                progress.update(task, advance=1)

        console.print(f"\n[green]成功抽取: {len(results)} 条[/green]")
        if errors:
            console.print(f"[yellow]失败: {len(errors)} 条[/yellow]")

        # Export to Excel
        if results:
            import pandas as pd

            output_path.parent.mkdir(parents=True, exist_ok=True)
            df = pd.DataFrame(results)
            df.to_excel(output_path, index=False)
            console.print(f"[green]已导出: {output_path}[/green]")

        await cleanup_container()

    asyncio.run(run_extraction())


@app.command("prescription")
def extract_prescription(
    input_dir: Path = typer.Option(None, "--input", "-i", help="输入目录"),
    output: Path = typer.Option(None, "--output", "-o", help="输出Excel路径"),
    limit: int = typer.Option(0, "--limit", "-l", help="处理文件数限制 (0=不限制)"),
) -> None:
    """从文本文件抽取方剂实体"""
    settings = get_settings()
    setup_logging(level=settings.log_level)

    input_path = input_dir or settings.prescriptions_dir
    output_path = output or settings.exports_dir / "prescriptions_extracted.xlsx"

    if not input_path.exists():
        console.print(f"[red]输入目录不存在: {input_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]开始抽取方剂实体[/bold]")
    console.print(f"  输入目录: {input_path}")
    console.print(f"  输出文件: {output_path}")

    async def run_extraction() -> None:
        from tcm_kgraph.core.dependencies import get_container, cleanup_container
        from tcm_kgraph.extraction import EntityExtractor

        container = get_container()
        extractor = EntityExtractor(container.llm_client)

        # Find all text files
        txt_files = list(input_path.glob("*.txt"))
        if limit > 0:
            txt_files = txt_files[:limit]

        console.print(f"  找到 {len(txt_files)} 个文件")

        results = []
        errors = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("抽取中...", total=len(txt_files))

            for txt_file in txt_files:
                try:
                    text = txt_file.read_text(encoding="utf-8")
                    data = await extractor.extract_prescription(text)
                    data["source_file"] = txt_file.name
                    results.append(data)
                except Exception as e:
                    errors.append({"file": txt_file.name, "error": str(e)})

                progress.update(task, advance=1)

        console.print(f"\n[green]成功抽取: {len(results)} 条[/green]")
        if errors:
            console.print(f"[yellow]失败: {len(errors)} 条[/yellow]")

        # Export to Excel
        if results:
            import pandas as pd

            output_path.parent.mkdir(parents=True, exist_ok=True)
            df = pd.DataFrame(results)
            df.to_excel(output_path, index=False)
            console.print(f"[green]已导出: {output_path}[/green]")

        await cleanup_container()

    asyncio.run(run_extraction())


@app.command("relations")
def extract_relations(
    input_file: Path = typer.Argument(..., help="输入文本文件"),
    output: Path = typer.Option(None, "--output", "-o", help="输出JSON路径"),
) -> None:
    """从文本中抽取实体关系"""
    settings = get_settings()
    setup_logging(level=settings.log_level)

    if not input_file.exists():
        console.print(f"[red]输入文件不存在: {input_file}[/red]")
        raise typer.Exit(1)

    output_path = output or input_file.with_suffix(".relations.json")

    console.print(f"[bold]开始抽取实体关系[/bold]")
    console.print(f"  输入文件: {input_file}")
    console.print(f"  输出文件: {output_path}")

    async def run_extraction() -> None:
        import json
        from tcm_kgraph.core.dependencies import get_container, cleanup_container
        from tcm_kgraph.extraction import EntityExtractor

        container = get_container()
        extractor = EntityExtractor(container.llm_client)

        text = input_file.read_text(encoding="utf-8")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("抽取关系中...", total=None)
            relations = await extractor.extract_relations(text)

        console.print(f"\n[green]抽取到 {len(relations)} 条关系[/green]")

        # Save to JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"relations": relations}, f, ensure_ascii=False, indent=2)

        console.print(f"[green]已保存: {output_path}[/green]")

        # Display relations
        for rel in relations[:10]:
            console.print(
                f"  {rel.get('source')} --[{rel.get('relation')}]--> {rel.get('target')}"
            )
        if len(relations) > 10:
            console.print(f"  ... 还有 {len(relations) - 10} 条关系")

        await cleanup_container()

    asyncio.run(run_extraction())
