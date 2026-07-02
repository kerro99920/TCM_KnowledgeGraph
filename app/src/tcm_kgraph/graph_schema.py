"""统一图谱 Schema：节点/关系/属性/别名对齐的唯一权威定义（仅依赖标准库）。"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class NodeDef:
    zh: str
    props: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelDef:
    zh: str
    domain: tuple[str, ...]
    range: tuple[str, ...]
    props: tuple[str, ...] = ()


# 节点标签白名单（name 为所有节点的唯一键属性）
NODE_LABELS: dict[str, NodeDef] = {
    "Herb": NodeDef(
        "中药材",
        (
            "name", "alias", "property_flavor", "meridian", "effect",
            "indication", "dosage", "usage", "taboo", "origin",
            "place", "processing", "traits",
        ),
    ),
    "Formula": NodeDef(
        "方剂",
        ("name", "alias", "effect", "indication", "usage", "taboo"),
    ),
    "Disease": NodeDef("疾病", ("name",)),
    "Symptom": NodeDef("症状", ("name",)),
    "Effect": NodeDef("功效", ("name",)),
    "Source": NodeDef("文献出处", ("name",)),
}

# 关系类型白名单（含定义域/值域约束）
REL_TYPES: dict[str, RelDef] = {
    "HAS_INGREDIENT": RelDef("方剂包含药材", ("Formula",), ("Herb",), ("dosage", "role")),
    "TREATS_DISEASE": RelDef("治疗疾病", ("Herb", "Formula"), ("Disease",)),
    "ALLEVIATES_SYMPTOM": RelDef("缓解症状", ("Herb", "Formula"), ("Symptom",)),
    "HAS_EFFECT": RelDef("具有功效", ("Herb", "Formula"), ("Effect",)),
    "HAS_SYMPTOM": RelDef("疾病表现症状", ("Disease",), ("Symptom",)),
    "FROM_SOURCE": RelDef("出自文献", ("Herb", "Formula"), ("Source",)),
}

# LLM 输出中常见的旧标签写法 → 统一标签（输出归一，不是运行时兼容层）
LABEL_ALIASES: dict[str, str] = {
    "Medicine": "Herb",
    "Prescription": "Formula",
}

# 常见异体字归一
_CHAR_MAP = str.maketrans({"蔘": "参", "薑": "姜", "黃": "黄", "藥": "药", "耆": "芪", "歸": "归"})

# 常见药材异名 → 规范名（实体对齐第二层：别名表）
ENTITY_ALIASES: dict[str, str] = {
    "黄耆": "黄芪",
    "绵芪": "黄芪",
    "北芪": "黄芪",
    "云苓": "茯苓",
    "白茯苓": "茯苓",
    "元胡": "延胡索",
    "玄胡": "延胡索",
    "田七": "三七",
    "山萸肉": "山茱萸",
    "仙灵脾": "淫羊藿",
    "双花": "金银花",
    "二花": "金银花",
    "国老": "甘草",
    "川军": "大黄",
    "怀山药": "山药",
    "淮山": "山药",
    "于术": "白术",
}

_IDENT_RE = re.compile(r"^[A-Za-z_]\w*$")


def normalize_entity_name(name: str) -> str:
    """实体名归一化：NFKC → 去空白 → 异体字 → 别名表。"""
    s = unicodedata.normalize("NFKC", name or "").strip()
    s = re.sub(r"\s+", "", s)
    s = s.translate(_CHAR_MAP)
    return ENTITY_ALIASES.get(s, s)


def safe_label(label: str) -> str:
    """校验并返回白名单内的节点标签，非法即抛错。"""
    key = LABEL_ALIASES.get((label or "").strip(), (label or "").strip())
    if key not in NODE_LABELS:
        raise ValueError(f"非法节点标签: {label!r}，允许: {sorted(NODE_LABELS)}")
    return key


def safe_rel_type(rel_type: str) -> str:
    """校验并返回白名单内的关系类型，非法即抛错。"""
    key = (rel_type or "").strip()
    if key not in REL_TYPES:
        raise ValueError(f"非法关系类型: {rel_type!r}，允许: {sorted(REL_TYPES)}")
    return key


def safe_prop_key(key: str) -> str:
    """属性键必须是合法标识符（防注入）。"""
    k = (key or "").strip()
    if not _IDENT_RE.match(k):
        raise ValueError(f"非法属性键: {key!r}")
    return k


def schema_prompt() -> str:
    """生成注入 Text2Cypher 提示词的 schema 描述。"""
    lines = ["节点标签（唯一键属性为 name）："]
    for label, nd in NODE_LABELS.items():
        props = "、".join(nd.props)
        lines.append(f"- {label}（{nd.zh}），属性: {props}")
    lines.append("")
    lines.append("关系类型（方向固定）：")
    for rt, rd in REL_TYPES.items():
        dom = "|".join(rd.domain)
        rng = "|".join(rd.range)
        prop = f"，属性: {'、'.join(rd.props)}" if rd.props else ""
        lines.append(f"- ({dom})-[:{rt}]->({rng})  {rd.zh}{prop}")
    return "\n".join(lines)


def schema_summary() -> dict:
    """结构化 schema 摘要（供 API /schema 接口与前端使用）。"""
    return {
        "labels": {label: {"zh": nd.zh, "props": list(nd.props)} for label, nd in NODE_LABELS.items()},
        "relations": {
            rt: {
                "zh": rd.zh,
                "domain": list(rd.domain),
                "range": list(rd.range),
                "props": list(rd.props),
            }
            for rt, rd in REL_TYPES.items()
        },
    }
