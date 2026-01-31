"""FastAPI dependency injection for API routes."""

from typing import Annotated, AsyncIterator

from fastapi import Depends, Request

from tcm_kgraph.core.config import Settings, get_settings
from tcm_kgraph.core.dependencies import Container, get_container
from tcm_kgraph.database.neo4j_client import Neo4jClient
from tcm_kgraph.llm.client import LLMClient
from tcm_kgraph.llm.embeddings import EmbeddingModel


def get_request_container(request: Request) -> Container:
    """Get container from request state."""
    return request.app.state.container


async def get_neo4j(
    container: Annotated[Container, Depends(get_request_container)],
) -> AsyncIterator[Neo4jClient]:
    """Get Neo4j client from container."""
    yield container.neo4j_client


async def get_llm(
    container: Annotated[Container, Depends(get_request_container)],
) -> AsyncIterator[LLMClient]:
    """Get LLM client from container."""
    yield container.llm_client


async def get_embedding_model(
    container: Annotated[Container, Depends(get_request_container)],
) -> AsyncIterator[EmbeddingModel]:
    """Get embedding model from container."""
    yield container.embedding_model


# Type aliases for dependency injection
SettingsDep = Annotated[Settings, Depends(get_settings)]
ContainerDep = Annotated[Container, Depends(get_request_container)]
Neo4jDep = Annotated[Neo4jClient, Depends(get_neo4j)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]
EmbeddingDep = Annotated[EmbeddingModel, Depends(get_embedding_model)]
