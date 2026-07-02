"""知识图谱查询接口（schema 驱动 + 只读安全防线）。"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from tcm_kgraph.api.dependencies import Neo4jDep
from tcm_kgraph.core.logging import get_logger
from tcm_kgraph.database.cypher_guard import CypherGuardError, guard_readonly_cypher
from tcm_kgraph.graph_schema import (
    NODE_LABELS,
    REL_TYPES,
    normalize_entity_name,
    safe_label,
    schema_summary,
)
from tcm_kgraph.models.schemas import (
    EntityResponse,
    GraphQueryRequest,
    GraphQueryResponse,
    SearchRequest,
    SearchResult,
)

logger = get_logger(__name__)
router = APIRouter()


@router.get("/schema")
async def get_schema() -> dict[str, Any]:
    """返回统一 schema 定义。"""
    return schema_summary()


@router.get("/stats")
async def get_stats(neo4j: Neo4jDep) -> dict[str, Any]:
    """按标签/关系类型统计图谱规模。"""
    labels: dict[str, int] = {}
    for label in NODE_LABELS:
        rows = await neo4j.execute(f"MATCH (n:{label}) RETURN count(n) AS c")
        labels[label] = rows[0]["c"] if rows else 0

    relations: dict[str, int] = {}
    for rt in REL_TYPES:
        rows = await neo4j.execute(f"MATCH ()-[r:{rt}]->() RETURN count(r) AS c")
        relations[rt] = rows[0]["c"] if rows else 0

    return {
        "labels": labels,
        "relations": relations,
        "total_nodes": sum(labels.values()),
        "total_relations": sum(relations.values()),
    }


@router.get("/entity/{label}/{name}")
async def get_entity(label: str, name: str, neo4j: Neo4jDep) -> EntityResponse:
    """按标签+名称查询实体及其出入边（名称自动归一化对齐）。"""
    try:
        sl = safe_label(label)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    norm_name = normalize_entity_name(name)
    query = (
        f"MATCH (n:{sl} {{name: $name}}) "
        "OPTIONAL MATCH (n)-[r_out]->(m_out) "
        "WITH n, collect(DISTINCT {rel: type(r_out), name: m_out.name, "
        "label: head(labels(m_out))}) AS outgoing "
        "OPTIONAL MATCH (m_in)-[r_in]->(n) "
        "RETURN n, outgoing, collect(DISTINCT {rel: type(r_in), name: m_in.name, "
        "label: head(labels(m_in))}) AS incoming"
    )
    rows = await neo4j.execute(query, {"name": norm_name})
    if not rows:
        raise HTTPException(status_code=404, detail=f"未找到 {sl} 实体: {norm_name}")

    row = rows[0]
    related = [
        {**item, "direction": direction}
        for direction, items in (("out", row["outgoing"]), ("in", row["incoming"]))
        for item in items
        if item.get("rel")
    ]
    return EntityResponse(
        entity_type=sl,
        entity_id=norm_name,
        data=dict(row["n"]),
        related_entities=related,
    )


@router.post("/search")
async def search_entities(request: SearchRequest, neo4j: Neo4jDep) -> list[SearchResult]:
    """按名称模糊检索（浏览用途，白名单标签内）。"""
    labels = request.entity_types or list(NODE_LABELS)
    results: list[SearchResult] = []

    for label in labels:
        try:
            sl = safe_label(label)
        except ValueError:
            continue
        query = (
            f"MATCH (n:{sl}) WHERE n.name CONTAINS $q "
            "RETURN n.name AS name LIMIT $limit"
        )
        rows = await neo4j.execute(query, {"q": request.query, "limit": request.limit})
        for r in rows:
            results.append(SearchResult(
                entity_type=sl,
                entity_id=r["name"],
                name=r["name"],
                score=1.0 if r["name"] == request.query else 0.5,
            ))

    results.sort(key=lambda x: x.score, reverse=True)
    return results[: request.limit]


@router.post("/query")
async def query_graph(request: GraphQueryRequest, neo4j: Neo4jDep) -> GraphQueryResponse:
    """执行只读 Cypher 查询（经安全校验）。"""
    if not request.cypher:
        raise HTTPException(status_code=400, detail="必须提供 cypher 字段")

    try:
        safe_cypher = guard_readonly_cypher(request.cypher)
    except CypherGuardError as e:
        raise HTTPException(status_code=400, detail=f"Cypher 未通过安全校验: {e}")

    try:
        results = await neo4j.execute(safe_cypher, request.parameters)
    except Exception as e:
        logger.error(f"图查询失败: {e}")
        raise HTTPException(status_code=400, detail=f"查询执行失败: {e}")

    return GraphQueryResponse(raw_results=results, executed_cypher=safe_cypher)
