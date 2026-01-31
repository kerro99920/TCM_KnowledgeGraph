"""Database CLI commands."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from tcm_kgraph.core.config import get_settings
from tcm_kgraph.core.logging import setup_logging


console = Console()
app = typer.Typer(help="数据库相关命令")


@app.command("status")
def db_status() -> None:
    """检查数据库连接状态"""
    settings = get_settings()
    setup_logging(level=settings.log_level)

    console.print("[bold]检查数据库状态[/bold]\n")

    async def check_status() -> None:
        from tcm_kgraph.core.dependencies import get_container, cleanup_container

        container = get_container()

        try:
            await container.neo4j_client.verify_connectivity()
            console.print("[green]Neo4j: 已连接[/green]")

            # Get node counts
            query = """
            CALL {
                MATCH (m:Medicine) RETURN 'Medicine' as label, count(m) as count
                UNION ALL
                MATCH (p:Prescription) RETURN 'Prescription' as label, count(p) as count
                UNION ALL
                MATCH (d:Disease) RETURN 'Disease' as label, count(d) as count
                UNION ALL
                MATCH (s:Symptom) RETURN 'Symptom' as label, count(s) as count
            }
            RETURN label, count
            """
            results = await container.neo4j_client.execute(query)

            table = Table(title="节点统计")
            table.add_column("类型", style="cyan")
            table.add_column("数量", style="green", justify="right")

            for row in results:
                table.add_row(row["label"], str(row["count"]))

            console.print(table)

            # Get relationship counts
            rel_query = """
            CALL {
                MATCH ()-[r:TREATS]->() RETURN 'TREATS' as type, count(r) as count
                UNION ALL
                MATCH ()-[r:CONTAINS]->() RETURN 'CONTAINS' as type, count(r) as count
                UNION ALL
                MATCH ()-[r:ENTERS_MERIDIAN]->() RETURN 'ENTERS_MERIDIAN' as type, count(r) as count
            }
            RETURN type, count
            """
            rel_results = await container.neo4j_client.execute(rel_query)

            rel_table = Table(title="关系统计")
            rel_table.add_column("类型", style="cyan")
            rel_table.add_column("数量", style="green", justify="right")

            for row in rel_results:
                rel_table.add_row(row["type"], str(row["count"]))

            console.print(rel_table)

        except Exception as e:
            console.print(f"[red]Neo4j: 连接失败 - {e}[/red]")

        await cleanup_container()

    asyncio.run(check_status())


@app.command("import")
def db_import(
    input_file: Path = typer.Argument(..., help="Excel文件路径"),
    entity_type: str = typer.Option(
        "medicine",
        "--type",
        "-t",
        help="实体类型 (medicine/prescription)",
    ),
    clear: bool = typer.Option(False, "--clear", help="导入前清空已有数据"),
) -> None:
    """从Excel导入数据到Neo4j"""
    settings = get_settings()
    setup_logging(level=settings.log_level)

    if not input_file.exists():
        console.print(f"[red]文件不存在: {input_file}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]导入数据到Neo4j[/bold]")
    console.print(f"  文件: {input_file}")
    console.print(f"  类型: {entity_type}")

    async def run_import() -> None:
        import pandas as pd
        from tcm_kgraph.core.dependencies import get_container, cleanup_container
        from tcm_kgraph.database.repositories import MedicineRepository, PrescriptionRepository
        from tcm_kgraph.models.entities import Medicine, Prescription

        container = get_container()

        # Read Excel
        df = pd.read_excel(input_file)
        console.print(f"  读取 {len(df)} 条记录")

        if clear:
            label = "Medicine" if entity_type == "medicine" else "Prescription"
            clear_query = f"MATCH (n:{label}) DETACH DELETE n"
            await container.neo4j_client.execute_write(clear_query)
            console.print(f"[yellow]已清空 {label} 节点[/yellow]")

        # Import data
        if entity_type == "medicine":
            repo = MedicineRepository(container.neo4j_client)
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console,
            ) as progress:
                task = progress.add_task("导入中...", total=len(df))

                for _, row in df.iterrows():
                    medicine = Medicine(
                        name=str(row.get("name", "")),
                        pinyin=str(row.get("pinyin", "")) if pd.notna(row.get("pinyin")) else None,
                        functions=_parse_list(row.get("functions")),
                        indications=_parse_list(row.get("indications")),
                        usage=str(row.get("usage", "")) if pd.notna(row.get("usage")) else None,
                    )
                    await repo.create(medicine)
                    progress.update(task, advance=1)

        else:
            repo = PrescriptionRepository(container.neo4j_client)
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console,
            ) as progress:
                task = progress.add_task("导入中...", total=len(df))

                for _, row in df.iterrows():
                    prescription = Prescription(
                        name=str(row.get("name", "")),
                        pinyin=str(row.get("pinyin", "")) if pd.notna(row.get("pinyin")) else None,
                        source_book=str(row.get("source_book", "")) if pd.notna(row.get("source_book")) else None,
                        functions=_parse_list(row.get("functions")),
                        indications=_parse_list(row.get("indications")),
                    )
                    await repo.create(prescription)
                    progress.update(task, advance=1)

        console.print(f"\n[green]导入完成![/green]")
        await cleanup_container()

    asyncio.run(run_import())


@app.command("export")
def db_export(
    output: Path = typer.Argument(..., help="输出Excel路径"),
    entity_type: str = typer.Option(
        "all",
        "--type",
        "-t",
        help="实体类型 (medicine/prescription/all)",
    ),
) -> None:
    """从Neo4j导出数据到Excel"""
    settings = get_settings()
    setup_logging(level=settings.log_level)

    console.print(f"[bold]从Neo4j导出数据[/bold]")
    console.print(f"  输出: {output}")
    console.print(f"  类型: {entity_type}")

    async def run_export() -> None:
        import pandas as pd
        from tcm_kgraph.core.dependencies import get_container, cleanup_container
        from tcm_kgraph.database.repositories import MedicineRepository, PrescriptionRepository

        container = get_container()
        output.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            if entity_type in ("medicine", "all"):
                repo = MedicineRepository(container.neo4j_client)
                medicines = await repo.find_all(limit=10000)
                data = [m.model_dump() for m in medicines]
                df = pd.DataFrame(data)
                df.to_excel(writer, sheet_name="Medicines", index=False)
                console.print(f"  导出 {len(medicines)} 条中药")

            if entity_type in ("prescription", "all"):
                repo = PrescriptionRepository(container.neo4j_client)
                prescriptions = await repo.find_all(limit=10000)
                data = [p.model_dump() for p in prescriptions]
                df = pd.DataFrame(data)
                df.to_excel(writer, sheet_name="Prescriptions", index=False)
                console.print(f"  导出 {len(prescriptions)} 条方剂")

        console.print(f"\n[green]导出完成: {output}[/green]")
        await cleanup_container()

    asyncio.run(run_export())


@app.command("query")
def db_query(
    cypher: str = typer.Argument(..., help="Cypher查询语句"),
) -> None:
    """执行Cypher查询"""
    settings = get_settings()
    setup_logging(level=settings.log_level)

    async def run_query() -> None:
        from tcm_kgraph.core.dependencies import get_container, cleanup_container

        container = get_container()

        try:
            results = await container.neo4j_client.execute(cypher)

            if not results:
                console.print("[yellow]查询无结果[/yellow]")
            else:
                console.print(f"[green]返回 {len(results)} 条结果[/green]\n")

                for i, record in enumerate(results[:20], 1):
                    console.print(f"[bold]#{i}[/bold]")
                    for key, value in record.items():
                        if isinstance(value, dict):
                            console.print(f"  {key}:")
                            for k, v in value.items():
                                if k not in ("raw_text", "embedding"):
                                    console.print(f"    {k}: {v}")
                        else:
                            console.print(f"  {key}: {value}")
                    console.print()

                if len(results) > 20:
                    console.print(f"[dim]... 还有 {len(results) - 20} 条结果[/dim]")

        except Exception as e:
            console.print(f"[red]查询失败: {e}[/red]")

        await cleanup_container()

    asyncio.run(run_query())


@app.command("clear")
def db_clear(
    entity_type: str = typer.Option(
        "all",
        "--type",
        "-t",
        help="要清空的实体类型 (medicine/prescription/all)",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="跳过确认"),
) -> None:
    """清空数据库中的数据"""
    if not force:
        confirm = typer.confirm(f"确定要清空 {entity_type} 数据吗?")
        if not confirm:
            console.print("[yellow]已取消[/yellow]")
            raise typer.Exit()

    settings = get_settings()
    setup_logging(level=settings.log_level)

    async def run_clear() -> None:
        from tcm_kgraph.core.dependencies import get_container, cleanup_container

        container = get_container()

        if entity_type == "all":
            query = "MATCH (n) DETACH DELETE n"
            await container.neo4j_client.execute_write(query)
            console.print("[green]已清空所有数据[/green]")
        else:
            label = "Medicine" if entity_type == "medicine" else "Prescription"
            query = f"MATCH (n:{label}) DETACH DELETE n"
            await container.neo4j_client.execute_write(query)
            console.print(f"[green]已清空 {label} 数据[/green]")

        await cleanup_container()

    asyncio.run(run_clear())


def _parse_list(value: str | list | None) -> list[str]:
    """Parse a value into a list of strings."""
    import pandas as pd

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Try to parse as list-like string
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            import ast
            try:
                return ast.literal_eval(value)
            except (ValueError, SyntaxError):
                pass
        # Split by common delimiters
        for delimiter in ["、", ",", ";"]:
            if delimiter in value:
                return [v.strip() for v in value.split(delimiter) if v.strip()]
        return [value] if value else []
    return []
