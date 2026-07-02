"""LangGraph 问答工作流节点实现。"""

from typing import Any, Literal

from tcm_kgraph.agents.state import AgentState
from tcm_kgraph.core.logging import get_logger
from tcm_kgraph.database.cypher_guard import CypherGuardError, guard_readonly_cypher
from tcm_kgraph.extraction.prompts import ExtractionPrompts
from tcm_kgraph.graph_schema import normalize_entity_name, safe_label

logger = get_logger(__name__)


async def route_question(state: AgentState, llm_client: Any) -> AgentState:
    """意图路由：判断是否需要查询知识图谱。"""
    routing_prompt = f"""分析以下中医相关问题的类型：

问题：{state.question}

请判断这个问题的类型：
1. knowledge_query - 需要查询知识图谱的事实性问题（如：某药的功效、某方剂的组成）
2. general_chat - 一般性聊天或不需要查询知识库的问题
3. comparison - 需要比较多个实体的问题
4. recommendation - 需要推荐药物或方剂的问题

只返回类型名称，不要其他内容。"""

    try:
        intent = (await llm_client.generate(routing_prompt)).strip().lower()
        need = intent in ("knowledge_query", "comparison", "recommendation")
        return state.model_copy(update={"intent": intent, "should_retrieve": need})
    except Exception as e:
        logger.error(f"意图路由失败: {e}")
        return state.model_copy(update={"intent": "knowledge_query", "should_retrieve": True})


async def extract_entities(state: AgentState, llm_client: Any) -> AgentState:
    """从问题中识别实体并做名称归一化（别名对齐）。"""
    try:
        result = await llm_client.extract_json(
            ExtractionPrompts.question_entities(state.question)
        )
        entities = []
        for e in result.get("entities", []):
            name = normalize_entity_name(e.get("name") or "")
            if not name:
                continue
            entities.append({"name": name, "type": (e.get("type") or "").strip()})
        logger.debug(f"识别实体 {len(entities)} 个")
        return state.model_copy(update={"entities": entities})
    except Exception as e:
        logger.error(f"实体识别失败: {e}")
        return state.model_copy(update={"entities": []})


async def retrieve_knowledge(
    state: AgentState,
    neo4j_client: Any,
    llm_client: Any,
) -> AgentState:
    """Text2Cypher 检索：生成 → 安全校验 → 执行；失败则按实体名精确检索兜底。"""
    if not state.should_retrieve:
        return state

    # 主路径：LLM 生成 Cypher + 只读校验
    try:
        result = await llm_client.extract_json(
            ExtractionPrompts.question_to_cypher(state.question)
        )
        cypher = result.get("cypher", "")
        if cypher:
            safe_cypher = guard_readonly_cypher(cypher)
            graph_results = await neo4j_client.execute(safe_cypher)
            logger.debug(f"Cypher 查询返回 {len(graph_results)} 条")
            if graph_results:
                return state.model_copy(update={
                    "cypher_query": safe_cypher,
                    "graph_results": graph_results,
                    "context": _format_graph_results(graph_results),
                })
    except CypherGuardError as e:
        logger.warning(f"生成的 Cypher 未通过安全校验: {e}")
    except Exception as e:
        logger.error(f"Text2Cypher 检索失败: {e}")

    # 兜底路径：已归一化实体名的邻域检索
    all_results: list[dict[str, Any]] = []
    for entity in state.entities:
        name = entity.get("name", "")
        try:
            label = safe_label(entity.get("type", ""))
            query = (
                f"MATCH (n:{label} {{name: $name}}) "
                "OPTIONAL MATCH (n)-[r]->(m) "
                "RETURN n, labels(n) AS labels, "
                "collect({rel: type(r), target: m.name})[..20] AS relations"
            )
        except ValueError:
            query = (
                "MATCH (n {name: $name}) "
                "OPTIONAL MATCH (n)-[r]->(m) "
                "RETURN n, labels(n) AS labels, "
                "collect({rel: type(r), target: m.name})[..20] AS relations "
                "LIMIT 3"
            )
        try:
            all_results.extend(await neo4j_client.execute(query, {"name": name}))
        except Exception as e:
            logger.warning(f"实体兜底检索失败 {name}: {e}")

    return state.model_copy(update={
        "graph_results": all_results,
        "context": _format_graph_results(all_results),
    })


async def generate_response(state: AgentState, llm_client: Any) -> AgentState:
    """基于图谱上下文生成最终回答。"""
    if state.context:
        prompt = ExtractionPrompts.qa(context=state.context, question=state.question)
    else:
        prompt = f"""你是一个专业的中医知识助手。请回答以下问题：

问题：{state.question}

请提供准确、专业的回答。如果不确定，请明确说明。"""

    try:
        response = await llm_client.generate(prompt)

        sources = []
        for result in state.graph_results:
            if isinstance(result, dict):
                for value in result.values():
                    if isinstance(value, dict) and "name" in value:
                        sources.append({"name": value.get("name")})

        return state.model_copy(update={"response": response, "sources": sources})
    except Exception as e:
        logger.error(f"回答生成失败: {e}")
        return state.model_copy(update={
            "response": "抱歉，生成回答时出现错误。请稍后重试。",
            "error": str(e),
        })


def should_retrieve(state: AgentState) -> Literal["retrieve", "respond"]:
    """条件边：是否走检索。"""
    return "retrieve" if state.should_retrieve else "respond"


def _format_graph_results(results: list[dict[str, Any]]) -> str:
    """将查询结果格式化为 LLM 上下文文本。"""
    if not results:
        return ""

    lines = ["知识图谱查询结果：", ""]
    for i, result in enumerate(results, 1):
        lines.append(f"结果 {i}:")
        for key, value in result.items():
            if isinstance(value, dict):
                props = []
                for k, v in value.items():
                    if v and k not in ("raw_text", "embedding"):
                        if isinstance(v, list):
                            v = "、".join(str(item) for item in v)
                        props.append(f"  - {k}: {v}")
                if props:
                    lines.append(f"  {key}:")
                    lines.extend(props)
            elif isinstance(value, list):
                items = [
                    f"{d.get('rel')}→{d.get('target')}"
                    for d in value
                    if isinstance(d, dict) and d.get("rel")
                ]
                if items:
                    lines.append(f"  {key}: {'；'.join(items)}")
            elif value:
                lines.append(f"  {key}: {value}")
        lines.append("")

    return "\n".join(lines)
