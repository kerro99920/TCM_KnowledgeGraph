"""LangGraph workflow definitions for TCM Knowledge Graph."""

from typing import Any

from langgraph.graph import StateGraph, END

from tcm_kgraph.agents.state import AgentState
from tcm_kgraph.agents.nodes import (
    route_question,
    extract_entities,
    retrieve_knowledge,
    generate_response,
    should_retrieve,
)
from tcm_kgraph.core.logging import get_logger


logger = get_logger(__name__)


def create_tcm_graph(
    llm_client: Any,
    neo4j_client: Any,
) -> StateGraph:
    """
    Create the TCM knowledge graph agent workflow.

    The workflow processes user questions through:
    1. Question routing - determine intent
    2. Entity extraction - identify TCM entities
    3. Knowledge retrieval - query Neo4j graph
    4. Response generation - create final answer

    Args:
        llm_client: LLM client for text generation
        neo4j_client: Neo4j client for graph queries

    Returns:
        Compiled LangGraph StateGraph
    """
    # Create graph with state schema
    workflow = StateGraph(AgentState)

    # Define node functions with injected dependencies
    async def route_node(state: AgentState) -> AgentState:
        return await route_question(state, llm_client)

    async def extract_node(state: AgentState) -> AgentState:
        return await extract_entities(state, llm_client)

    async def retrieve_node(state: AgentState) -> AgentState:
        return await retrieve_knowledge(state, neo4j_client, llm_client)

    async def respond_node(state: AgentState) -> AgentState:
        return await generate_response(state, llm_client)

    # Add nodes
    workflow.add_node("route", route_node)
    workflow.add_node("extract", extract_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("respond", respond_node)

    # Define edges
    workflow.set_entry_point("route")
    workflow.add_edge("route", "extract")

    # Conditional routing after extraction
    workflow.add_conditional_edges(
        "extract",
        should_retrieve,
        {
            "retrieve": "retrieve",
            "respond": "respond",
        },
    )

    workflow.add_edge("retrieve", "respond")
    workflow.add_edge("respond", END)

    # Compile the graph
    graph = workflow.compile()
    logger.info("TCM agent workflow compiled successfully")

    return graph


async def run_tcm_agent(
    question: str,
    llm_client: Any,
    neo4j_client: Any,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Run the TCM agent to answer a question.

    Args:
        question: User's question
        llm_client: LLM client instance
        neo4j_client: Neo4j client instance
        history: Optional conversation history

    Returns:
        Dictionary with response and metadata
    """
    graph = create_tcm_graph(llm_client, neo4j_client)

    # Initialize state
    initial_state = AgentState(
        question=question,
        messages=history or [],
    )

    # Run the graph
    try:
        final_state = await graph.ainvoke(initial_state)

        return {
            "response": final_state.response,
            "sources": final_state.sources,
            "cypher_query": final_state.cypher_query,
            "intent": final_state.intent,
            "entities": final_state.entities,
            "error": final_state.error,
        }
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        return {
            "response": "抱歉，处理您的问题时出现错误。请稍后重试。",
            "sources": [],
            "error": str(e),
        }
