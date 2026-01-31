"""API request and response schemas."""

from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthResponse(BaseModel):
    """Health check response."""

    status: HealthStatus = Field(description="Overall health status")
    version: str = Field(description="Application version")
    timestamp: datetime = Field(default_factory=datetime.now, description="Check timestamp")
    components: dict[str, HealthStatus] = Field(
        default_factory=dict, description="Component health statuses"
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T] = Field(description="List of items")
    total: int = Field(ge=0, description="Total number of items")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, description="Items per page")
    total_pages: int = Field(ge=0, description="Total number of pages")

    @classmethod
    def create(
        cls, items: list[T], total: int, page: int, page_size: int
    ) -> "PaginatedResponse[T]":
        """Create a paginated response."""
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


class SearchRequest(BaseModel):
    """Search request parameters."""

    query: str = Field(min_length=1, max_length=500, description="Search query")
    entity_types: list[str] | None = Field(
        default=None, description="Filter by entity types"
    )
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Result offset")
    use_embedding: bool = Field(default=True, description="Use vector similarity search")


class SearchResult(BaseModel):
    """Single search result."""

    entity_type: str = Field(description="Type of entity (medicine/prescription/disease)")
    entity_id: str = Field(description="Entity identifier")
    name: str = Field(description="Entity name")
    score: float = Field(ge=0, le=1, description="Relevance score")
    snippet: str | None = Field(default=None, description="Matching text snippet")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class EntityResponse(BaseModel):
    """Generic entity response."""

    entity_type: str = Field(description="Type of entity")
    entity_id: str = Field(description="Entity identifier")
    data: dict[str, Any] = Field(description="Entity data")
    related_entities: list[dict[str, Any]] = Field(
        default_factory=list, description="Related entities from graph"
    )


class GraphQueryRequest(BaseModel):
    """Graph query request."""

    cypher: str | None = Field(default=None, description="Raw Cypher query")
    natural_language: str | None = Field(
        default=None, description="Natural language query to convert"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Query parameters"
    )


class GraphQueryResponse(BaseModel):
    """Graph query response."""

    nodes: list[dict[str, Any]] = Field(default_factory=list, description="Result nodes")
    relationships: list[dict[str, Any]] = Field(
        default_factory=list, description="Result relationships"
    )
    raw_results: list[dict[str, Any]] = Field(
        default_factory=list, description="Raw query results"
    )
    generated_cypher: str | None = Field(
        default=None, description="Generated Cypher query (if from NL)"
    )


class MessageRole(str, Enum):
    """Chat message roles."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """Single chat message."""

    role: MessageRole = Field(description="Message role")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now, description="Message timestamp")


class ChatRequest(BaseModel):
    """Chat request."""

    message: str = Field(min_length=1, max_length=2000, description="User message")
    history: list[ChatMessage] = Field(
        default_factory=list, description="Conversation history"
    )
    use_knowledge_graph: bool = Field(
        default=True, description="Whether to query knowledge graph"
    )
    stream: bool = Field(default=False, description="Enable streaming response")


class ChatResponse(BaseModel):
    """Chat response."""

    message: str = Field(description="Assistant response")
    sources: list[dict[str, Any]] = Field(
        default_factory=list, description="Knowledge sources used"
    )
    graph_query: str | None = Field(
        default=None, description="Generated graph query"
    )
    confidence: float | None = Field(
        default=None, ge=0, le=1, description="Response confidence score"
    )
