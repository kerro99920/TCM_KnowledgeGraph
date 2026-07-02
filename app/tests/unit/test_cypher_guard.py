"""Cypher 只读安全校验的单元测试。"""

import pytest

from tcm_kgraph.database.cypher_guard import CypherGuardError, guard_readonly_cypher


class TestReadonly:
    def test_valid_match(self):
        q = guard_readonly_cypher(
            "MATCH (h:Herb {name: '黄芪'}) RETURN h LIMIT 10"
        )
        assert q.startswith("MATCH")

    def test_auto_limit(self):
        q = guard_readonly_cypher("MATCH (h:Herb) RETURN h.name")
        assert q.endswith("LIMIT 50")

    def test_keeps_existing_limit(self):
        q = guard_readonly_cypher("MATCH (h:Herb) RETURN h LIMIT 5")
        assert q.count("LIMIT") == 1

    @pytest.mark.parametrize("bad", [
        "CREATE (n:Herb {name: 'x'})",
        "MATCH (n:Herb) DELETE n",
        "MATCH (n:Herb) DETACH DELETE n",
        "MATCH (n:Herb) SET n.name = 'y'",
        "MERGE (n:Herb {name: 'x'})",
        "MATCH (n:Herb) REMOVE n.name",
        "DROP CONSTRAINT foo",
        "CALL db.labels()",
        "MATCH (n:Herb) CALL { WITH n RETURN n } RETURN n",
        "LOAD CSV FROM 'file:///x' AS row RETURN row",
        "SHOW DATABASES",
    ])
    def test_rejects_writes(self, bad):
        with pytest.raises(CypherGuardError):
            guard_readonly_cypher(bad)

    def test_keyword_in_string_ok(self):
        # 字符串字面量中的关键字不应误杀
        q = guard_readonly_cypher(
            "MATCH (d:Disease) WHERE d.name = 'SET综合征' RETURN d"
        )
        assert "SET综合征" in q

    def test_keyword_inside_identifier_ok(self):
        q = guard_readonly_cypher("MATCH (h:Herb) RETURN h.dataset")
        assert "dataset" in q


class TestWhitelist:
    def test_rejects_unknown_label(self):
        with pytest.raises(CypherGuardError, match="节点标签"):
            guard_readonly_cypher("MATCH (p:Person) RETURN p")

    def test_rejects_unknown_rel(self):
        with pytest.raises(CypherGuardError, match="关系类型"):
            guard_readonly_cypher("MATCH (a:Herb)-[:KNOWS]->(b:Herb) RETURN a")

    def test_allows_whitelisted_rel(self):
        guard_readonly_cypher(
            "MATCH (f:Formula)-[:HAS_INGREDIENT]->(h:Herb) RETURN f, h LIMIT 5"
        )

    def test_allows_rel_alternation(self):
        guard_readonly_cypher(
            "MATCH (x)-[:TREATS_DISEASE|ALLEVIATES_SYMPTOM]->(y) RETURN x, y LIMIT 5"
        )

    def test_rejects_backticks(self):
        with pytest.raises(CypherGuardError):
            guard_readonly_cypher("MATCH (n:`Herb`) RETURN n")

    def test_rejects_empty(self):
        with pytest.raises(CypherGuardError):
            guard_readonly_cypher("   ")

    def test_rejects_non_query_head(self):
        with pytest.raises(CypherGuardError):
            guard_readonly_cypher("EXPLAIN MATCH (n:Herb) RETURN n")
