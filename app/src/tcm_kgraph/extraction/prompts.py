"""LLM 提示词模板（全部基于统一 schema 生成）。"""

from tcm_kgraph.graph_schema import schema_prompt


class ExtractionPrompts:
    """中医知识抽取与问答提示词集合。"""

    SYSTEM_PROMPT = (
        "你是一个专业的中医知识图谱助手。"
        "请严格按照要求的JSON格式输出，不要添加任何额外的文字说明。"
    )

    # 三元组抽取（构图用）
    TRIPLE_EXTRACTION = """你是一个中医知识图谱抽取专家。请从以下文本中提取结构化知识。
仅当文本中存在实体之间的明确关系时才进行抽取；若只描述单个实体、无关系，返回空结构：
{{"entities": [], "relations": []}}

【图谱 Schema】
{schema}

抽取要求：
1. 实体 type 必须严格使用上述节点标签，关系 relation 必须严格使用上述关系类型。
2. Herb/Formula 实体可带 attributes（属性名严格使用 schema 中列出的属性）。
3. 文本主要讲方剂时不抽取药材属性，主要讲药材时不抽取方剂属性。
4. 属性值为空时省略该键。

输出 JSON 格式：
```json
{{
  "entities": [
    {{"name": "四君子汤", "type": "Formula", "attributes": {{"effect": "益气健脾"}}}},
    {{"name": "人参", "type": "Herb"}}
  ],
  "relations": [
    {{"subject": "四君子汤", "subject_type": "Formula", "relation": "HAS_INGREDIENT", "object": "人参", "object_type": "Herb"}}
  ]
}}
```

输入文本：
{text}"""

    # 问题实体识别（问答链路用）
    QUESTION_ENTITY_EXTRACTION = """从以下中医问题中识别实体：

问题：{question}

实体类型仅限：Herb（中药材）、Formula（方剂）、Disease（疾病）、Symptom（症状）、Effect（功效）、Source（文献）。

以JSON返回：
```json
{{"entities": [{{"name": "黄芪", "type": "Herb"}}, {{"name": "气虚", "type": "Symptom"}}]}}
```

只返回JSON，不要其他内容。"""

    # Text2Cypher（只读查询生成）
    QUESTION_TO_CYPHER = """你是Neo4j Cypher查询专家。请将用户问题转换为只读Cypher查询。

【图谱 Schema】
{schema}

硬性约束：
1. 只允许读查询（MATCH/OPTIONAL MATCH/WHERE/RETURN/WITH/UNWIND/ORDER BY/LIMIT）。
2. 禁止 CREATE/MERGE/DELETE/SET/REMOVE/CALL 等任何写操作或过程调用。
3. 节点标签与关系类型只能使用上述 Schema 中列出的。
4. 必须带 LIMIT（不超过 25）。
5. 实体名精确匹配用 {{name: '...'}}，不确定时用 CONTAINS 模糊匹配。

示例：
- 问："四君子汤由哪些药组成？"
  cypher: "MATCH (f:Formula {{name: '四君子汤'}})-[:HAS_INGREDIENT]->(h:Herb) RETURN h.name LIMIT 25"
- 问："哪些方剂能治感冒？"
  cypher: "MATCH (f:Formula)-[:TREATS_DISEASE]->(d:Disease) WHERE d.name CONTAINS '感冒' RETURN f.name, d.name LIMIT 25"

用户问题：{question}

以JSON返回：
```json
{{"cypher": "...", "explanation": "..."}}
```"""

    # 问答生成
    TCM_QA_SYSTEM = """你是一个专业的中医知识问答助手。请基于提供的知识图谱信息回答用户问题。

回答要求：
1. 优先引用知识图谱中的信息，并保持准确。
2. 使用专业但易懂的中医术语。
3. 如果图谱信息不足，请明确说明并谨慎补充。

知识图谱查询结果：
{context}

用户问题：{question}

请提供专业、准确的回答。"""

    @classmethod
    def triple_extraction(cls, text: str) -> str:
        return cls.TRIPLE_EXTRACTION.format(schema=schema_prompt(), text=text)

    @classmethod
    def question_to_cypher(cls, question: str) -> str:
        return cls.QUESTION_TO_CYPHER.format(schema=schema_prompt(), question=question)

    @classmethod
    def question_entities(cls, question: str) -> str:
        return cls.QUESTION_ENTITY_EXTRACTION.format(question=question)

    @classmethod
    def qa(cls, context: str, question: str) -> str:
        return cls.TCM_QA_SYSTEM.format(context=context, question=question)
