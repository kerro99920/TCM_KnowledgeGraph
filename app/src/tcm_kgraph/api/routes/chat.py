"""Chat and Q&A endpoints."""

from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from tcm_kgraph.api.dependencies import Neo4jDep, LLMDep
from tcm_kgraph.models.schemas import ChatRequest, ChatResponse
from tcm_kgraph.agents.graph import run_tcm_agent
from tcm_kgraph.core.logging import get_logger


logger = get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    neo4j: Neo4jDep,
    llm: LLMDep,
) -> ChatResponse:
    """
    Send a message and receive a response from the TCM knowledge assistant.

    The assistant will:
    1. Analyze the question intent
    2. Query the knowledge graph if relevant
    3. Generate a contextual response
    """
    # Convert history to list of dicts
    history = [
        {"role": msg.role.value, "content": msg.content}
        for msg in request.history
    ]

    # Run the agent
    result = await run_tcm_agent(
        question=request.message,
        llm_client=llm,
        neo4j_client=neo4j,
        history=history,
    )

    return ChatResponse(
        message=result["response"],
        sources=result.get("sources", []),
        graph_query=result.get("cypher_query"),
        confidence=None,
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    neo4j: Neo4jDep,
    llm: LLMDep,
) -> StreamingResponse:
    """
    Send a message and receive a streaming response.

    Returns Server-Sent Events (SSE) with response chunks.
    """
    async def generate() -> AsyncIterator[str]:
        # First, get context from knowledge graph
        if request.use_knowledge_graph:
            # Simple entity extraction and query
            query = f"""
            MATCH (n)
            WHERE toLower(n.name) CONTAINS toLower($query)
            RETURN n
            LIMIT 3
            """
            try:
                results = await neo4j.execute(query, {"query": request.message})
                context = _format_results(results)
            except Exception as e:
                logger.warning(f"Graph query failed: {e}")
                context = ""
        else:
            context = ""

        # Build prompt
        system_prompt = "你是一个专业的中医知识助手。"
        if context:
            system_prompt += f"\n\n参考信息:\n{context}"

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Add history
        for msg in request.history:
            messages.append({"role": msg.role.value, "content": msg.content})

        # Add current message
        messages.append({"role": "user", "content": request.message})

        # Stream response
        try:
            async for chunk in llm.chat_stream(messages):
                yield f"data: {chunk}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: [ERROR] {e}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/simple")
async def simple_chat(
    request: ChatRequest,
    llm: LLMDep,
) -> ChatResponse:
    """
    Simple chat without knowledge graph retrieval.

    Direct LLM conversation for general TCM questions.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个专业的中医知识助手。请根据你的知识回答用户关于中医药的问题。"
                "如果不确定答案，请明确说明。"
            ),
        },
    ]

    # Add history
    for msg in request.history:
        messages.append({"role": msg.role.value, "content": msg.content})

    # Add current message
    messages.append({"role": "user", "content": request.message})

    response = await llm.chat(messages)

    return ChatResponse(
        message=response,
        sources=[],
        graph_query=None,
        confidence=None,
    )


def _format_results(results: list[dict]) -> str:
    """Format graph results for context."""
    if not results:
        return ""

    lines = []
    for result in results:
        for key, value in result.items():
            if isinstance(value, dict):
                name = value.get("name", "")
                if name:
                    lines.append(f"- {name}")
                    for k, v in value.items():
                        if k not in ("name", "raw_text", "embedding") and v:
                            if isinstance(v, list):
                                v = "、".join(str(x) for x in v[:5])
                            lines.append(f"  {k}: {v}")

    return "\n".join(lines)
