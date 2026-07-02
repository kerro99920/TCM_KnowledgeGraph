"""Alpaca 导入纯函数的单元测试。"""

import json

from tcm_kgraph.ingest.alpaca_import import (
    build_node_queries,
    build_relation_queries,
    collect_entities_relations,
    parse_output,
    sanitize_props,
)


def _alpaca(output: dict) -> dict:
    return {"instruction": "x", "input": "y", "output": json.dumps(output, ensure_ascii=False)}


class TestParse:
    def test_invalid_json(self):
        assert parse_output("not json") == ([], [])
        assert parse_output(None) == ([], [])
        assert parse_output(123) == ([], [])

    def test_valid(self):
        e, r = parse_output(json.dumps({"entities": [{"name": "a"}], "relations": []}))
        assert len(e) == 1 and r == []


class TestCollect:
    def test_alias_dedup(self):
        # 别名对齐后 北芪/黄芪 应合并为同一实体
        data = [
            _alpaca({
                "entities": [
                    {"name": "黄芪", "type": "Herb", "attributes": {"effect": "补气"}},
                    {"name": "北芪", "type": "Herb", "attributes": {"dosage": "9-30g"}},
                ],
                "relations": [],
            })
        ]
        entity_map, _, skipped = collect_entities_relations(data)
        assert list(entity_map) == [("黄芪", "Herb")]
        # 属性合并：两条记录的属性都保留
        attrs = entity_map[("黄芪", "Herb")]["attributes"]
        assert attrs["effect"] == "补气" and attrs["dosage"] == "9-30g"
        assert skipped == []

    def test_old_label_mapped(self):
        data = [_alpaca({"entities": [{"name": "人参", "type": "Medicine"}], "relations": []})]
        entity_map, _, _ = collect_entities_relations(data)
        assert ("人参", "Herb") in entity_map

    def test_invalid_type_skipped(self):
        data = [
            _alpaca({
                "entities": [{"name": "张三", "type": "Person"}],
                "relations": [{
                    "subject": "a", "subject_type": "Herb",
                    "relation": "KNOWS",
                    "object": "b", "object_type": "Herb",
                }],
            })
        ]
        entity_map, relations, skipped = collect_entities_relations(data)
        assert not entity_map and not relations
        assert len(skipped) == 2

    def test_relation_endpoint_normalized(self):
        data = [
            _alpaca({
                "entities": [],
                "relations": [{
                    "subject": "四君子汤", "subject_type": "Formula",
                    "relation": "HAS_INGREDIENT",
                    "object": "云苓", "object_type": "Herb",
                }],
            })
        ]
        _, relations, _ = collect_entities_relations(data)
        assert relations[0]["object"] == "茯苓"


class TestBuild:
    def test_node_queries_unwind_merge(self):
        entity_map = {("黄芪", "Herb"): {"name": "黄芪", "label": "Herb", "attributes": {"effect": "补气"}}}
        queries = build_node_queries(entity_map)
        assert len(queries) == 1
        cypher, params = queries[0]
        assert "UNWIND $rows" in cypher and "MERGE (n:Herb" in cypher
        assert params["rows"][0]["name"] == "黄芪"

    def test_relation_queries_grouped(self):
        rels = [
            {"subject": "四君子汤", "subject_type": "Formula", "relation": "HAS_INGREDIENT",
             "object": "人参", "object_type": "Herb"},
            {"subject": "四君子汤", "subject_type": "Formula", "relation": "HAS_INGREDIENT",
             "object": "白术", "object_type": "Herb"},
        ]
        queries = build_relation_queries(rels)
        assert len(queries) == 1
        cypher, params = queries[0]
        assert "MERGE (a)-[r:HAS_INGREDIENT]->(b)" in cypher
        assert len(params["rows"]) == 2

    def test_sanitize_props(self):
        out = sanitize_props({"a": "x", "b": 1, "c": None, "d": ["y", "z"]})
        assert out == {"a": "x", "b": 1, "d": "['y', 'z']"}
