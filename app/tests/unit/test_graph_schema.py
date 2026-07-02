"""统一 schema 与实体对齐的单元测试。"""

import pytest

from tcm_kgraph.graph_schema import (
    NODE_LABELS,
    REL_TYPES,
    normalize_entity_name,
    safe_label,
    safe_prop_key,
    safe_rel_type,
    schema_prompt,
)


class TestNormalize:
    def test_alias_table(self):
        assert normalize_entity_name("北芪") == "黄芪"
        assert normalize_entity_name("元胡") == "延胡索"
        assert normalize_entity_name("田七") == "三七"

    def test_variant_chars(self):
        # 异体字：丹蔘 → 丹参、黄耆 → 黄芪
        assert normalize_entity_name("丹蔘") == "丹参"
        assert normalize_entity_name("黄耆") == "黄芪"

    def test_whitespace_and_fullwidth(self):
        assert normalize_entity_name("  人 参 ") == "人参"
        assert normalize_entity_name("ＡＢＣ") == "ABC"

    def test_passthrough(self):
        assert normalize_entity_name("四君子汤") == "四君子汤"
        assert normalize_entity_name("") == ""


class TestWhitelist:
    def test_safe_label_ok(self):
        for label in NODE_LABELS:
            assert safe_label(label) == label

    def test_safe_label_maps_old_schema(self):
        assert safe_label("Medicine") == "Herb"
        assert safe_label("Prescription") == "Formula"

    def test_safe_label_rejects(self):
        with pytest.raises(ValueError):
            safe_label("Person")
        with pytest.raises(ValueError):
            safe_label("Herb) DETACH DELETE (n")

    def test_safe_rel_type(self):
        for rt in REL_TYPES:
            assert safe_rel_type(rt) == rt
        with pytest.raises(ValueError):
            safe_rel_type("KNOWS")

    def test_safe_prop_key(self):
        assert safe_prop_key("dosage") == "dosage"
        with pytest.raises(ValueError):
            safe_prop_key("a b")
        with pytest.raises(ValueError):
            safe_prop_key("x`y")


def test_schema_prompt_covers_all():
    text = schema_prompt()
    for label in NODE_LABELS:
        assert label in text
    for rt in REL_TYPES:
        assert rt in text
