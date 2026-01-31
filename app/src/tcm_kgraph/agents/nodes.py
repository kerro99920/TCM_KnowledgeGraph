"""Node implementations for LangGraph workflows."""

from typing import Any, Literal

from tcm_kgraph.agents.state import AgentState
from tcm_kgraph.core.logging import get_logger
from tcm_kgraph.extraction.prompts import ExtractionPrompts


logger = get_logger(__name__)


async def route_question(
    state: AgentState,
    llm_client: Any,
) -> AgentState:
    """
    Route question to appropriate processing path.

    Analyzes the question intent to determine whether knowledge
    graph retrieval is needed.

    Args:
        state: Current agent state
        llm_client: LLM client instance

    Returns:
        Updated state with intent and routing decision
    """
    question = state.question

    # Simple intent classification
    routing_prompt = f"""分析以下中医相关问题的类型：

问题：{question}

请判断这个问题的类型：
1. knowledge_query - 需要查询知识图谱的事实性问题（如：某药的功效、某方剂的组成）
2. general_chat - 一般性聊天或不需要查询知识库的问题
3. comparison - 需要比较多个实体的问题
4. recommendation - 需要推荐药物或方剂的问题

只返回类型名称，不要其他内容。"""

    try:
        intent = await llm_client.generate(routing_prompt)
        intent = intent.strip().lower()

        # Determine if retrieval is needed
        should_retrieve = intent in ["knowledge_query", "comparison", "recommendation"]

        logger.debug(f"Question routed: intent={intent}, should_retrieve={should_retrieve}")

        return AgentState(
            **state.model_dump(),
            intent=intent,
            should_retrieve=should_retrieve,
        )
    except Exception as e:
        logger.error(f"Question routing failed: {e}")
        return AgentState(
            **state.model_dump(),
            intent="knowledge_query",
            should_retrieve=True,
        )


async def extract_entities(
    state: AgentState,
    llm_client: Any,
) -> AgentState:
    """
    Extract entities from the user question.

    Identifies TCM entities mentioned in the question for
    knowledge graph querying.

    Args:
        state: Current agent state
        llm_client: LLM client instance

    Returns:
        Updated state with extracted entities
    """
    question = state.question

    extraction_prompt = f"""从以下中医问题中提取实体：

问题：{question}

请识别所有中医相关实体（中药、方剂、疾病、症状等），以JSON格式返回：
```json
{{
  "entities": [
    {{"name": "黄芪", "type": "Medicine"}},
    {{"name": "气虚", "type": "Symptom"}}
  ]
}}
```

只返回JSON，不要其他内容。"""

    try:
        result = await llm_client.extract_json(extraction_prompt)
        entities = result.get("entities", [])
        logger.debug(f"Extracted {len(entities)} entities from question")

        return AgentState(
            **state.model_dump(),
            entities=entities,
        )
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        return AgentState(**state.model_dump(), entities=[])


async def retrieve_knowledge(
    state: AgentState,
    neo4j_client: Any,
    llm_client: Any,
) -> AgentState:
    """
    Retrieve relevant knowledge from the graph database.

    Generates Cypher queries based on extracted entities and
    executes them against Neo4j.

    Args:
        state: Current agent state
        neo4j_client: Neo4j client instance
        llm_client: LLM client instance

    Returns:
        Updated state with graph results and context
    """
    if not state.should_retrieve:
        return state

    entities = state.entities
    question = state.question

    # Generate Cypher query
    prompts = ExtractionPrompts()
    cypher_prompt = prompts.QUESTION_TO_CYPHER.format(question=question)

    try:
        result = await llm_client.extract_json(cypher_prompt)
        cypher = result.get("cypher", "")

        if cypher:
            # Execute query
            graph_results = await neo4j_client.execute(cypher)
            logger.debug(f"Graph query returned {len(graph_results)} results")

            # Format context
            context = _format_graph_results(graph_results)

            return AgentState(
                **state.model_dump(),
                cypher_query=cypher,
                graph_results=graph_results,
                context=context,
            )

    except Exception as e:
        logger.error(f"Knowledge retrieval failed: {e}")

    # Fallback: query by entity names
    all_results: list[dict[str, Any]] = []
    for entity in entities:
        name = entity.get("name", "")
        entity_type = entity.get("type", "")

        if entity_type == "Medicine":
            query = "MATCH (n:Medicine) WHERE n.name = $name RETURN n LIMIT 1"
        elif entity_type == "Prescription":
            query = "MATCH (n:Prescription) WHERE n.name = $name RETURN n LIMIT 1"
        else:
            query = "MATCH (n) WHERE n.name = $name RETURN n LIMIT 1"

        try:
            results = await neo4j_client.execute(query, {"name": name})
            all_results.extend(results)
        except Exception:
            pass

    context = _format_graph_results(all_results)

    return AgentState(
        **state.model_dump(),
        graph_results=all_results,
        context=context,
    )


async def generate_response(
    state: AgentState,
    llm_client: Any,
) -> AgentState:
    """
    Generate final response using LLM.

    Combines context from knowledge graph with conversation
    history to generate a helpful response.

    Args:
        state: Current agent state
        llm_client: LLM client instance

    Returns:
        Updated state with generated response
    """
    question = state.question
    context = state.context

    prompts = ExtractionPrompts()

    if context:
        # Response with knowledge graph context
        prompt = prompts.TCM_QA_SYSTEM.format(
            context=context,
            question=question,
        )
    else:
        # General response without specific context
        prompt = f"""你是一个专业的中医知识助手。请回答以下问题：

问题：{question}

请提供准确、专业的回答。如果不确定，请明确说明。"""

    try:
        response = await llm_client.generate(prompt)
        logger.debug("Response generated successfully")

        # Extract sources from graph results
        sources = []
        for result in state.graph_results:
            if isinstance(result, dict):
                for value in result.values():
                    if isinstance(value, dict) and "name" in value:
                        sources.append({
                            "name": value.get("name"),
                            "type": value.get("type", "Entity"),
                        })

        return AgentState(
            **state.model_dump(),
            response=response,
            sources=sources,
        )
    except Exception as e:
        logger.error(f"Response generation failed: {e}")
        return AgentState(
            **state.model_dump(),
            response="抱歉，生成回答时出现错误。请稍后重试。",
            error=str(e),
        )


def should_retrieve(state: AgentState) -> Literal["retrieve", "respond"]:
    """
    Conditional edge function to decide retrieval path.

    Args:
        state: Current agent state

    Returns:
        Next node name
    """
    if state.should_retrieve:
        return "retrieve"
    return "respond"


def _format_graph_results(results: list[dict[str, Any]]) -> str:
    """Format graph query results as context string."""
    if not results:
        return ""

    lines = ["知识图谱查询结果：", ""]

    for i, result in enumerate(results, 1):
        lines.append(f"结果 {i}:")
        for key, value in result.items():
            if isinstance(value, dict):
                # Format node properties
                props = []
                for k, v in value.items():
                    if v and k not in ("raw_text", "embedding"):
                        if isinstance(v, list):
                            v = "、".join(str(item) for item in v)
                        props.append(f"  - {k}: {v}")
                if props:
                    lines.append(f"  {key}:")
                    lines.extend(props)
            else:
                lines.append(f"  {key}: {value}")
        lines.append("")

    return "\n".join(lines)
