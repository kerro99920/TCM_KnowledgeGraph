"""Text2Cypher 安全防线：只读校验 + 标签/关系白名单 + LIMIT 兜底（仅依赖标准库）。"""

from __future__ import annotations

import re

from tcm_kgraph.graph_schema import NODE_LABELS, REL_TYPES


class CypherGuardError(ValueError):
    """Cypher 未通过安全校验。"""


# 写操作与危险子句（词边界匹配，字符串字面量已剥离）
_FORBIDDEN = (
    "CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP",
    "FOREACH", "LOAD", "CALL", "SHOW", "GRANT", "DENY", "REVOKE",
    "START", "TERMINATE", "ALTER", "INSTALL",
)

_ALLOWED_HEADS = ("MATCH", "OPTIONAL", "WITH", "RETURN", "UNWIND")

_STRING_RE = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)

# 节点模式中的标签链: (n:Herb) / (:Herb:Formula)
_NODE_LABELS_RE = re.compile(r"\(\s*\w*((?:\s*:\s*[A-Za-z_]\w*)+)")
_IDENT_AFTER_COLON_RE = re.compile(r":\s*([A-Za-z_]\w*)")
# 关系模式方括号内容: [r:HAS_EFFECT|TREATS_DISEASE*1..2]
_REL_BRACKET_RE = re.compile(r"\[([^\]]*)\]")
_REL_TYPE_RE = re.compile(r"[:|]\s*!?\s*([A-Za-z_]\w*)")


def _strip_literals(query: str) -> str:
    q = _BLOCK_COMMENT_RE.sub(" ", query)
    q = _LINE_COMMENT_RE.sub(" ", q)
    return _STRING_RE.sub("''", q)


def guard_readonly_cypher(cypher: str, default_limit: int = 50) -> str:
    """校验 LLM 生成的 Cypher 只读且仅使用白名单 schema，返回可执行语句。"""
    q = (cypher or "").strip().rstrip(";").strip()
    if not q:
        raise CypherGuardError("空 Cypher 语句")
    if "`" in q:
        raise CypherGuardError("不允许反引号标识符")

    bare = _strip_literals(q)

    head = bare.split(None, 1)[0].upper() if bare.split() else ""
    if head not in _ALLOWED_HEADS:
        raise CypherGuardError(f"语句必须以 {'/'.join(_ALLOWED_HEADS)} 开头，实际: {head or '空'}")

    for kw in _FORBIDDEN:
        if re.search(rf"\b{kw}\b", bare, re.IGNORECASE):
            raise CypherGuardError(f"检测到禁止的关键字: {kw}")

    # 节点标签白名单
    for m in _NODE_LABELS_RE.finditer(bare):
        for label in _IDENT_AFTER_COLON_RE.findall(m.group(1)):
            if label not in NODE_LABELS:
                raise CypherGuardError(f"未授权的节点标签: {label}")

    # 关系类型白名单（仅检查含冒号的方括号，跳过下标/切片）
    for m in _REL_BRACKET_RE.finditer(bare):
        content = m.group(1)
        if ":" not in content:
            continue
        for rel in _REL_TYPE_RE.findall(content):
            if rel not in REL_TYPES and rel not in NODE_LABELS:
                raise CypherGuardError(f"未授权的关系类型: {rel}")

    # 无 LIMIT 自动兜底
    if not re.search(r"\bLIMIT\b", bare, re.IGNORECASE):
        q = f"{q} LIMIT {default_limit}"

    return q
