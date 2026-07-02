"""LLM 三元组抽取器：文本 → 统一 schema 的实体与关系。"""

from __future__ import annotations

from typing import Any

from tcm_kgraph.core.exceptions import ExtractionError
from tcm_kgraph.core.logging import get_logger
from tcm_kgraph.extraction.prompts import ExtractionPrompts
from tcm_kgraph.graph_schema import normalize_entity_name, safe_label, safe_rel_type

logger = get_logger(__name__)


def clean_extraction(raw: dict[str, Any]) -> dict[str, Any]:
    """校验并归一化抽取结果：名称归一、标签/关系白名单过滤（纯函数，可单测）。"""
    entities: list[dict[str, Any]] = []
    for e in raw.get("entities") or []:
        name = normalize_entity_name(e.get("name") or "")
        if not name:
            continue
        try:
            label = safe_label((e.get("type") or "").strip())
        except ValueError:
            continue
        item: dict[str, Any] = {"name": name, "type": label}
        attrs = {k: v for k, v in dict(e.get("attributes") or {}).items() if v}
        if attrs:
            item["attributes"] = attrs
        entities.append(item)

    relations: list[dict[str, Any]] = []
    for r in raw.get("relations") or []:
        subj = normalize_entity_name(r.get("subject") or "")
        obj = normalize_entity_name(r.get("object") or "")
        try:
            stype = safe_label((r.get("subject_type") or "").strip())
            otype = safe_label((r.get("object_type") or "").strip())
            rel = safe_rel_type((r.get("relation") or "").strip())
        except ValueError:
            continue
        if not subj or not obj:
            continue
        relations.append({
            "subject": subj,
            "subject_type": stype,
            "relation": rel,
            "object": obj,
            "object_type": otype,
        })

    return {"entities": entities, "relations": relations}


class TripleExtractor:
    """基于 LLM 的三元组抽取器。"""

    def __init__(self, llm_client: Any) -> None:
        self._llm = llm_client

    async def extract(self, text: str) -> dict[str, Any]:
        """抽取单段文本，返回 {"entities": [...], "relations": [...]}。"""
        try:
            raw = await self._llm.extract_json(
                prompt=ExtractionPrompts.triple_extraction(text),
                system_prompt=ExtractionPrompts.SYSTEM_PROMPT,
            )
        except Exception as e:
            raise ExtractionError(
                f"三元组抽取失败: {e}", details={"text_length": len(text)}
            ) from e
        cleaned = clean_extraction(raw)
        logger.debug(
            f"抽取实体 {len(cleaned['entities'])} 个，关系 {len(cleaned['relations'])} 条"
        )
        return cleaned
