"""
Read medicine_alpaca.json and prescription_alpaca.json, parse output (entities and relations),
and write to Neo4j database.

Usage (from project root):
    python database/import_alpaca_to_neo4j.py [--clear]
    --clear: Clear database before import (use with caution)
"""

import json
import argparse
import sys
import os
from pathlib import Path
from typing import Tuple, List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.path_utils import get_file_path
from common.neo4j_manager import neo4j_client

# Data file paths (relative to project root)
ZHONGYAO_ALPACA = "extraction/medicine_alpaca.json"
FANGJI_ALPACA = "extraction/prescription_alpaca.json"


def load_alpaca_list(path: str) -> List[dict]:
    """加载 Alpaca JSON（数组），每项含 instruction/input/output。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_output(output_str: str) -> Tuple[List[dict], List[dict]]:
    """解析单条 output 字符串，返回 (entities, relations)。"""
    if not output_str or not isinstance(output_str, str):
        return [], []
    try:
        data = json.loads(output_str)
    except (json.JSONDecodeError, TypeError):
        return [], []
    entities = data.get("entities") or []
    relations = data.get("relations") or []
    return entities, relations


def collect_entities_relations(alpaca_list: List[dict]) -> Tuple[Dict[tuple, dict], List[dict]]:
    """
    从多条 Alpaca 记录中汇总实体与关系并去重。
    返回:
        entity_map: {(name, type): {"name", "type", "attributes"}}
        relation_list: [{"subject", "subject_type", "relation", "object", "object_type"}, ...]
    """
    entity_map = {}
    relation_seen = set()
    relation_list = []

    for item in alpaca_list:
        out = item.get("output")
        if out is None:
            continue
        entities, relations = parse_output(out)
        for e in entities:
            name = (e.get("name") or "").strip()
            etype = (e.get("type") or "").strip()
            if not name or not etype:
                continue
            key = (name, etype)
            if key not in entity_map:
                entity_map[key] = {
                    "name": name,
                    "type": etype,
                    "attributes": dict(e.get("attributes") or {}),
                }
        for r in relations:
            subj = (r.get("subject") or "").strip()
            stype = (r.get("subject_type") or "").strip()
            rel = (r.get("relation") or "").strip()
            obj = (r.get("object") or "").strip()
            otype = (r.get("object_type") or "").strip()
            if not all([subj, stype, rel, obj, otype]):
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

    return entity_map, relation_list


def sanitize_props(props: dict) -> dict:
    """保证属性值为 Neo4j 支持的类型（str/int/float/bool）。"""
    out = {}
    for k, v in props.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        else:
            out[k] = str(v)
    return out


def safe_label(s: str) -> str:
    """生成合法 Cypher 标签/关系类型（仅字母数字下划线）。"""
    return "".join(c if c.isalnum() or c == "_" else "_" for c in s) or "Entity"


def build_node_queries(entity_map: Dict[tuple, dict]) -> List[Tuple[str, dict]]:
    """按实体类型分组，生成 MERGE 节点的 Cypher 与参数。"""
    by_label = {}
    for (_name, _type), rec in entity_map.items():
        by_label.setdefault(rec["type"], []).append({
            "name": rec["name"],
            "props": sanitize_props(rec["attributes"]),
        })

    queries = []
    for label, rows in by_label.items():
        sl = safe_label(label)
        cypher = f"""
        UNWIND $rows AS row
        MERGE (n:{sl} {{name: row.name}})
        SET n += row.props
        """
        queries.append((cypher.strip(), {"rows": rows}))
    return queries


def build_relation_queries(relation_list: List[dict]) -> List[Tuple[str, dict]]:
    """按 (subject_type, relation_type, object_type) 分组，生成 MERGE 关系的 Cypher 与参数。"""
    by_triple = {}
    for r in relation_list:
        st, rt, ot = r["subject_type"], r["relation"], r["object_type"]
        key = (st, rt, ot)
        by_triple.setdefault(key, []).append({"subj": r["subject"], "obj": r["object"]})

    queries = []
    for (stype, rtype, otype), rows in by_triple.items():
        sl, rl, ol = safe_label(stype), safe_label(rtype), safe_label(otype)
        if not rl:
            rl = "REL"
        cypher = f"""
        UNWIND $rows AS row
        MATCH (a:{sl} {{name: row.subj}}), (b:{ol} {{name: row.obj}})
        MERGE (a)-[r:{rl}]->(b)
        """
        queries.append((cypher.strip(), {"rows": rows}))
    return queries


def main():
    parser = argparse.ArgumentParser(description="将中药/方剂 Alpaca JSON 导入 Neo4j")
    parser.add_argument("--clear", action="store_true", help="导入前清空数据库")
    args = parser.parse_args()

    zhongyao_path = get_file_path(ZHONGYAO_ALPACA)
    fangji_path = get_file_path(FANGJI_ALPACA)

    for p in [zhongyao_path, fangji_path]:
        if not Path(p).is_file():  # 代码健壮性,非空判断
            print(f"文件不存在: {p}")
            sys.exit(1)

    print("加载 Alpaca 数据...")
    zhongyao = load_alpaca_list(zhongyao_path)
    fangji = load_alpaca_list(fangji_path)
    alpaca_list = zhongyao + fangji
    print(f"  中药条数: {len(zhongyao)}, 方剂条数: {len(fangji)}, 合计: {len(alpaca_list)}")

    entity_map, relation_list = collect_entities_relations(alpaca_list)
    print(f"去重后 实体数: {len(entity_map)}, 关系数: {len(relation_list)}")

    node_queries = build_node_queries(entity_map)
    rel_queries = build_relation_queries(relation_list)
    print(f"节点批次数: {len(node_queries)}, 关系批次数: {len(rel_queries)}")

    if args.clear:
        print("正在清空数据库...")
        neo4j_client.clear_database()

    print("写入节点...")
    neo4j_client.run_multiple_cypher(node_queries)
    print("写入关系...")
    neo4j_client.run_multiple_cypher(rel_queries)
    print("导入完成。")


if __name__ == "__main__":
    main()
