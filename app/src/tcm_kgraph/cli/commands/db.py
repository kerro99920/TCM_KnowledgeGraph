"""数据库 CLI 命令。"""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from tcm_kgraph.core.config import get_settings
from tcm_kgraph.core.logging import setup_logging
from tcm_kgraph.graph_schema import NODE_LABELS, REL_TYPES, safe_label

console = Console()
app = typer.Typer(help="数据库相关命令")


def _setup() -> None:
    setup_logging(level=get_settings().log_level)


@app.command("status")
def db_status() -> None:
    """检查数据库连接与图谱规模（按统一 schema 统计）。"""
    _setup()

    async def run() -> None:
        from tcm_kgraph.core.dependencies import get_container, cleanup_container

        container = get_container()
        try:
            await container.neo4j_client.verify_connectivity()
            console.print("[green]Neo4j: 已连接[/green]")

            table = Table(title="节点统计")
            table.add_column("标签", style="cyan")
            table.add_column("说明", style="dim")
            table.add_column("数量", style="green", justify="right")
            for label, nd in NODE_LABELS.items():
                rows = await container.neo4j_client.execute(
                    f"MATCH (n:{label}) RETURN count(n) AS c"
                )
                table.add_row(label, nd.zh, str(rows[0]["c"] if rows else 0))
            console.print(table)

            rel_table = Table(title="关系统计")
            rel_table.add_column("类型", style="cyan")
            rel_table.add_column("说明", style="dim")
            rel_table.add_column("数量", style="green", justify="right")
            for rt, rd in REL_TYPES.items():
                rows = await container.neo4j_client.execute(
                    f"MATCH ()-[r:{rt}]->() RETURN count(r) AS c"
                )
                rel_table.add_row(rt, rd.zh, str(rows[0]["c"] if rows else 0))
            console.print(rel_table)
        except Exception as e:
            console.print(f"[red]Neo4j: 连接失败 - {e}[/red]")
            console.print("[dim]请确认 Neo4j 已启动且 .env 中 NEO4J_* 配置正确[/dim]")
        finally:
            await cleanup_container()

    asyncio.run(run())


@app.command("import-alpaca")
def db_import_alpaca(
    files: list[Path] = typer.Argument(..., help="Alpaca 三元组 JSON 文件（可多个）"),
    clear: bool = typer.Option(False, "--clear", help="导入前清空数据库"),
) -> None:
    """导入 Alpaca 三元组 JSON（实体对齐 + UNWIND/MERGE 批量写入）。"""
    _setup()

    for f in files:
        if not f.is_file():
            console.print(f"[red]文件不存在: {f}[/red]")
            raise typer.Exit(1)

    async def run() -> None:
        from tcm_kgraph.core.dependencies import get_container, cleanup_container
        from tcm_kgraph.ingest.alpaca_import import import_alpaca_files

        container = get_container()
        try:
            await container.neo4j_client.verify_connectivity()
        except Exception as e:
            console.print(f"[red]无法连接 Neo4j: {e}[/red]")
            await cleanup_container()
            raise typer.Exit(1)

        if clear:
            console.print("[yellow]导入前将清空数据库[/yellow]")

        stats = await import_alpaca_files(container.neo4j_client, files, clear=clear)
        console.print(
            f"[green]导入完成[/green] 记录 {stats['records']} 条，"
            f"实体 {stats['entities']} 个，关系 {stats['relations']} 条 "
            f"(节点批 {stats['node_batches']}，关系批 {stats['relation_batches']})"
        )
        if stats["skipped"]:
            console.print(f"[yellow]越界跳过 {len(stats['skipped'])} 项（前5）:[/yellow]")
            for s in stats["skipped"][:5]:
                console.print(f"  - {s}")
        await cleanup_container()

    asyncio.run(run())


@app.command("query")
def db_query(
    cypher: str = typer.Argument(..., help="Cypher 查询语句（仅只读）"),
) -> None:
    """执行只读 Cypher 查询（经安全校验）。"""
    _setup()

    from tcm_kgraph.database.cypher_guard import CypherGuardError, guard_readonly_cypher

    try:
        safe_cypher = guard_readonly_cypher(cypher)
    except CypherGuardError as e:
        console.print(f"[red]安全校验未通过: {e}[/red]")
        raise typer.Exit(1)

    async def run() -> None:
        from tcm_kgraph.core.dependencies import get_container, cleanup_container

        container = get_container()
        try:
            results = await container.neo4j_client.execute(safe_cypher)
            if not results:
                console.print("[yellow]查询无结果[/yellow]")
            else:
                console.print(f"[green]返回 {len(results)} 条结果[/green]\n")
                for i, record in enumerate(results[:20], 1):
                    console.print(f"[bold]#{i}[/bold] {record}")
                if len(results) > 20:
                    console.print(f"[dim]... 还有 {len(results) - 20} 条[/dim]")
        except Exception as e:
            console.print(f"[red]查询失败: {e}[/red]")
        finally:
            await cleanup_container()

    asyncio.run(run())


@app.command("clear")
def db_clear(
    label: str = typer.Option("all", "--label", "-l", help="要清空的节点标签，all=全部"),
    force: bool = typer.Option(False, "--force", "-f", help="跳过确认"),
) -> None:
    """清空数据库数据。"""
    if label != "all":
        try:
            label = safe_label(label)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)

    if not force and not typer.confirm(f"确定要清空 {label} 数据吗?"):
        console.print("[yellow]已取消[/yellow]")
        raise typer.Exit()

    _setup()

    async def run() -> None:
        from tcm_kgraph.core.dependencies import get_container, cleanup_container

        container = get_container()
        try:
            if label == "all":
                await container.neo4j_client.execute_write("MATCH (n) DETACH DELETE n")
            else:
                await container.neo4j_client.execute_write(
                    f"MATCH (n:{label}) DETACH DELETE n"
                )
            console.print(f"[green]已清空 {label} 数据[/green]")
        except Exception as e:
            console.print(f"[red]清空失败: {e}[/red]")
        finally:
            await cleanup_container()

    asyncio.run(run())
