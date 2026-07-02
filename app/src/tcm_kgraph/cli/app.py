"""Typer CLI application for TCM Knowledge Graph."""

import typer
from rich.console import Console

from tcm_kgraph import __version__
from tcm_kgraph.cli.commands import crawl, extract, db


console = Console()

app = typer.Typer(
    name="tcm",
    help="中医知识图谱CLI工具 - TCM Knowledge Graph CLI",
    no_args_is_help=True,
    add_completion=False,
)

# Add sub-command groups
app.add_typer(crawl.app, name="crawl", help="爬虫相关命令")
app.add_typer(extract.app, name="extract", help="信息抽取命令")
app.add_typer(db.app, name="db", help="数据库相关命令")


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="显示版本信息",
        is_eager=True,
    ),
) -> None:
    """中医知识图谱CLI工具"""
    if version:
        console.print(f"TCM Knowledge Graph v{__version__}")
        raise typer.Exit()


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="服务器地址"),
    port: int = typer.Option(8000, help="服务器端口"),
    reload: bool = typer.Option(False, help="开发模式自动重载"),
) -> None:
    """启动API服务器"""
    import uvicorn

    console.print(f"[green]启动API服务器: http://{host}:{port}[/green]")
    console.print("[dim]按 Ctrl+C 停止服务器[/dim]")

    uvicorn.run(
        "tcm_kgraph.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def chat() -> None:
    """交互式对话（与 API 同一条问答链路）"""
    import asyncio
    from tcm_kgraph.agents.graph import run_tcm_agent
    from tcm_kgraph.core.dependencies import get_container, cleanup_container

    console.print("[bold green]中医知识图谱对话系统[/bold green]")
    console.print("[dim]输入 'quit' 或 'exit' 退出[/dim]\n")

    async def run_chat() -> None:
        container = get_container()

        try:
            await container.neo4j_client.verify_connectivity()
            console.print("[green]已连接到知识图谱[/green]\n")
        except Exception as e:
            console.print(f"[yellow]警告: 无法连接知识图谱 ({e})，检索将自动降级[/yellow]\n")

        history: list[dict[str, str]] = []

        while True:
            try:
                question = console.input("[bold blue]你: [/bold blue]")
            except (KeyboardInterrupt, EOFError):
                break

            if question.lower() in ("quit", "exit", "q"):
                break
            if not question.strip():
                continue

            try:
                result = await run_tcm_agent(
                    question=question,
                    llm_client=container.llm_client,
                    neo4j_client=container.neo4j_client,
                    history=history,
                )
                console.print(f"\n[bold green]助手: [/bold green]{result['response']}\n")
                if result.get("cypher_query"):
                    console.print(f"[dim]Cypher: {result['cypher_query']}[/dim]\n")

                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": result["response"]})
                history = history[-10:]
            except Exception as e:
                console.print(f"[red]错误: {e}[/red]\n")

        await cleanup_container()

    asyncio.run(run_chat())
    console.print("[dim]再见![/dim]")


if __name__ == "__main__":
    app()
