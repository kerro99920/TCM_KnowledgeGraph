"""LangGraph 问答工作流定义。"""

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


def create_tcm_graph(llm_client: Any, neo4j_client: Any):
    """构建问答工作流：路由 → 实体识别 → 图谱检索 → 生成回答。"""
    workflow = StateGraph(AgentState)

    async def route_node(state: AgentState) -> AgentState:
        return await route_question(state, llm_client)

    async def extract_node(state: AgentState) -> AgentState:
        return await extract_entities(state, llm_client)

    async def retrieve_node(state: AgentState) -> AgentState:
        return await retrieve_knowledge(state, neo4j_client, llm_client)

    async def respond_node(state: AgentState) -> AgentState:
        return await generate_response(state, llm_client)

    workflow.add_node("route", route_node)
    workflow.add_node("extract", extract_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("respond", respond_node)

    workflow.set_entry_point("route")
    workflow.add_edge("route", "extract")
    workflow.add_conditional_edges(
        "extract",
        should_retrieve,
        {"retrieve": "retrieve", "respond": "respond"},
    )
    workflow.add_edge("retrieve", "respond")
    workflow.add_edge("respond", END)

    return workflow.compile()


async def run_tcm_agent(
    question: str,
    llm_client: Any,
    neo4j_client: Any,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """执行问答，返回回答与检索元数据。"""
    graph = create_tcm_graph(llm_client, neo4j_client)
    initial_state = AgentState(question=question, messages=history or [])

    try:
        # ainvoke 返回各通道值的 dict
        final_state = await graph.ainvoke(initial_state)
        return {
            "response": final_state.get("response", ""),
            "sources": final_state.get("sources", []),
            "cypher_query": final_state.get("cypher_query", ""),
            "intent": final_state.get("intent", ""),
            "entities": final_state.get("entities", []),
            "error": final_state.get("error"),
        }
    except Exception as e:
        logger.error(f"Agent 执行失败: {e}")
        return {
            "response": "抱歉，处理您的问题时出现错误。请稍后重试。",
            "sources": [],
            "cypher_query": "",
            "intent": "",
            "entities": [],
            "error": str(e),
        }
