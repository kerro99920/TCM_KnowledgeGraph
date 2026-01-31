"""State models for LangGraph workflows."""

from typing import Annotated, Any

from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages


class AgentState(BaseModel):
    """
    State model for TCM knowledge graph agent.

    This state is passed between nodes in the LangGraph workflow,
    accumulating information as the agent processes a query.
    """

    # Input
    question: str = Field(default="", description="User's question")
    messages: Annotated[list[dict[str, Any]], add_messages] = Field(
        default_factory=list,
        description="Conversation history",
    )

    # Processing
    intent: str = Field(default="", description="Detected question intent")
    entities: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Extracted entities from question",
    )
    cypher_query: str = Field(default="", description="Generated Cypher query")

    # Knowledge retrieval
    graph_results: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Results from knowledge graph query",
    )
    context: str = Field(default="", description="Formatted context for LLM")

    # Output
    response: str = Field(default="", description="Generated response")
    sources: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Source references",
    )

    # Control
    error: str | None = Field(default=None, description="Error message if any")
    should_retrieve: bool = Field(
        default=True,
        description="Whether to query knowledge graph",
    )


class ExtractionState(BaseModel):
    """
    State model for entity extraction workflow.

    Used when processing raw text to extract entities and relations.
    """

    # Input
    text: str = Field(default="", description="Raw text to process")
    text_type: str = Field(default="medicine", description="Type of text (medicine/prescription)")

    # Processing
    extracted_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted structured data",
    )
    relations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Extracted relations",
    )

    # Output
    entity_id: str | None = Field(default=None, description="Created entity ID in database")
    success: bool = Field(default=False, description="Whether extraction succeeded")
    error: str | None = Field(default=None, description="Error message if any")


class CrawlState(BaseModel):
    """
    State model for crawling workflow.

    Used when orchestrating web crawling operations.
    """

    # Input
    url: str = Field(default="", description="URL to crawl")
    crawl_type: str = Field(default="medicine", description="Type of content to crawl")
    max_pages: int = Field(default=1, description="Maximum pages to crawl")

    # Processing
    urls_to_crawl: list[str] = Field(
        default_factory=list,
        description="Queue of URLs to process",
    )
    crawled_items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Successfully crawled items",
    )

    # Output
    total_crawled: int = Field(default=0, description="Total items crawled")
    total_failed: int = Field(default=0, description="Total failed items")
    error: str | None = Field(default=None, description="Error message if any")
