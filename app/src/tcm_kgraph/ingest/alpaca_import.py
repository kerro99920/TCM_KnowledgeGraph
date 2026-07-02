"""Alpaca 三元组 JSON 批量导入 Neo4j：实体对齐 → 去重 → UNWIND+MERGE。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tcm_kgraph.graph_schema import (
    normalize_entity_name,
    safe_label,
    safe_prop_key,
    safe_rel_type,
)

if TYPE_CHECKING:
    from tcm_kgraph.database.neo4j_client import Neo4jClient

# 单批 UNWIND 行数上限
BATCH_SIZE = 500


def load_alpaca_list(path: str | Path) -> list[dict]:
    """加载 Alpaca JSON 数组，每项含 instruction/input/output。"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Alpaca 文件应为 JSON 数组: {path}")
    return data


def parse_output(output_str: Any) -> tuple[list[dict], list[dict]]:
    """解析单条 output 字符串，返回 (entities, relations)，解析失败返回空。"""
    if not output_str or not isinstance(output_str, str):
        return [], []
    try:
        data = json.loads(output_str)
    except (json.JSONDecodeError, TypeError):
        return [], []
    if not isinstance(data, dict):
        return [], []
    return data.get("entities") or [], data.get("relations") or []


def collect_entities_relations(
    alpaca_list: list[dict],
) -> tuple[dict[tuple[str, str], dict], list[dict], list[str]]:
    """
    汇总实体与关系：名称归一化（别名对齐）→ (name, label) 去重 → 属性合并。
    返回 (entity_map, relation_list, skipped)。
    """
    entity_map: dict[tuple[str, str], dict] = {}
    relation_seen: set[tuple] = set()
    relation_list: list[dict] = []
    skipped: list[str] = []

    def _label(raw: str) -> str | None:
        try:
            return safe_label(raw)
        except ValueError:
            skipped.append(f"标签越界: {raw!r}")
            return None

    for item in alpaca_list:
        entities, relations = parse_output(item.get("output"))

        for e in entities:
            name = normalize_entity_name(e.get("name") or "")
            label = _label((e.get("type") or "").strip()) if name else None
            if not name or not label:
                continue
            key = (name, label)
            attrs = {k: v for k, v in dict(e.get("attributes") or {}).items() if v is not None}
            if key not in entity_map:
                entity_map[key] = {"name": name, "label": label, "attributes": attrs}
            else:
                # 别名对齐后同一实体：补齐缺失属性
                merged = entity_map[key]["attributes"]
                for k, v in attrs.items():
                    merged.setdefault(k, v)

        for r in relations:
            subj = normalize_entity_name(r.get("subject") or "")
            obj = normalize_entity_name(r.get("object") or "")
            stype = _label((r.get("subject_type") or "").strip()) if subj else None
            otype = _label((r.get("object_type") or "").strip()) if obj else None
            try:
                rel = safe_rel_type((r.get("relation") or "").strip())
            except ValueError as exc:
                skipped.append(str(exc))
                continue
            if not all([subj, stype, obj, otype]):
                continue
            t = (subj, stype, rel, obj, otype)
            if t not in relation_seen:
                relation_seen.add(t)
                relation_list.append({
                    "subject": subj,
                    "subject_type": stype,
                    "relation": rel,
                    "object": obj,
                    "object_type": otype,
                })

    return entity_map, relation_list, skipped


def sanitize_props(props: dict) -> dict:
    """属性键校验 + 值转为 Neo4j 支持的标量类型。"""
    out: dict[str, Any] = {}
    for k, v in props.items():
        if v is None:
            continue
        key = safe_prop_key(str(k))
        out[key] = v if isinstance(v, (str, int, float, bool)) else str(v)
    return out


def _chunks(rows: list, size: int = BATCH_SIZE):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def build_node_queries(entity_map: dict[tuple[str, str], dict]) -> list[tuple[str, dict]]:
    """按标签分组生成 UNWIND+MERGE 节点批量导入语句。"""
    by_label: dict[str, list[dict]] = {}
    for rec in entity_map.values():
        by_label.setdefault(rec["label"], []).append({
            "name": rec["name"],
            "props": sanitize_props(rec["attributes"]),
        })

    queries: list[tuple[str, dict]] = []
    for label, rows in by_label.items():
        sl = safe_label(label)
        cypher = (
            f"UNWIND $rows AS row\n"
            f"MERGE (n:{sl} {{name: row.name}})\n"
            f"SET n += row.props"
        )
        for batch in _chunks(rows):
            queries.append((cypher, {"rows": batch}))
    return queries


def build_relation_queries(relation_list: list[dict]) -> list[tuple[str, dict]]:
    """按 (subject_type, relation, object_type) 分组生成 UNWIND+MERGE 关系语句。"""
    by_triple: dict[tuple[str, str, str], list[dict]] = {}
    for r in relation_list:
        key = (r["subject_type"], r["relation"], r["object_type"])
        by_triple.setdefault(key, []).append({"subj": r["subject"], "obj": r["object"]})

    queries: list[tuple[str, dict]] = []
    for (stype, rtype, otype), rows in by_triple.items():
        sl, rl, ol = safe_label(stype), safe_rel_type(rtype), safe_label(otype)
        cypher = (
            f"UNWIND $rows AS row\n"
            f"MATCH (a:{sl} {{name: row.subj}}), (b:{ol} {{name: row.obj}})\n"
            f"MERGE (a)-[r:{rl}]->(b)"
        )
        for batch in _chunks(rows):
            queries.append((cypher, {"rows": batch}))
    return queries


async def import_alpaca_files(
    client: "Neo4jClient",
    paths: list[Path],
    clear: bool = False,
) -> dict[str, Any]:
    """执行导入：可选清库 → 唯一性约束 → 节点 → 关系，返回统计。"""
    from tcm_kgraph.graph_schema import NODE_LABELS

    alpaca_list: list[dict] = []
    for p in paths:
        alpaca_list.extend(load_alpaca_list(p))

    entity_map, relation_list, skipped = collect_entities_relations(alpaca_list)
    node_queries = build_node_queries(entity_map)
    rel_queries = build_relation_queries(relation_list)

    if clear:
        await client.execute_write("MATCH (n) DETACH DELETE n")

    # name 唯一性约束（幂等）
    for label in NODE_LABELS:
        await client.execute_write(
            f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.name IS UNIQUE"
        )

    for cypher, params in node_queries:
        await client.execute_write(cypher, params)
    for cypher, params in rel_queries:
        await client.execute_write(cypher, params)

    return {
        "records": len(alpaca_list),
        "entities": len(entity_map),
        "relations": len(relation_list),
        "node_batches": len(node_queries),
        "relation_batches": len(rel_queries),
        "skipped": skipped,
    }
