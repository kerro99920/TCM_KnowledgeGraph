"""智能问答接口（唯一问答路径：LangGraph Text2Cypher Agent）。"""

from fastapi import APIRouter

from tcm_kgraph.agents.graph import run_tcm_agent
from tcm_kgraph.api.dependencies import LLMDep, Neo4jDep
from tcm_kgraph.core.logging import get_logger
from tcm_kgraph.models.schemas import ChatRequest, ChatResponse

logger = get_logger(__name__)
router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, neo4j: Neo4jDep, llm: LLMDep) -> ChatResponse:
    """问答流程：意图路由 → 实体识别 → Text2Cypher 检索 → 生成回答。"""
    history = [
        {"role": msg.role.value, "content": msg.content}
        for msg in request.history
    ]

    result = await run_tcm_agent(
        question=request.message,
        llm_client=llm,
        neo4j_client=neo4j,
        history=history,
    )

    return ChatResponse(
        message=result["response"],
        sources=result.get("sources", []),
        graph_query=result.get("cypher_query") or None,
        intent=result.get("intent") or None,
    )
