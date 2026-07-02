"""FastAPI 依赖注入。"""

from typing import Annotated, AsyncIterator

from fastapi import Depends, Request

from tcm_kgraph.core.config import Settings, get_settings
from tcm_kgraph.core.dependencies import Container
from tcm_kgraph.database.neo4j_client import Neo4jClient
from tcm_kgraph.llm.client import LLMClient


def get_request_container(request: Request) -> Container:
    """从应用状态获取容器。"""
    return request.app.state.container


async def get_neo4j(
    container: Annotated[Container, Depends(get_request_container)],
) -> AsyncIterator[Neo4jClient]:
    yield container.neo4j_client


async def get_llm(
    container: Annotated[Container, Depends(get_request_container)],
) -> AsyncIterator[LLMClient]:
    yield container.llm_client


SettingsDep = Annotated[Settings, Depends(get_settings)]
ContainerDep = Annotated[Container, Depends(get_request_container)]
Neo4jDep = Annotated[Neo4jClient, Depends(get_neo4j)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]
