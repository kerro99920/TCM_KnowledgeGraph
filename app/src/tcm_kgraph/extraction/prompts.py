"""Prompt templates for LLM-based information extraction."""


class ExtractionPrompts:
    """Collection of prompt templates for TCM entity and relation extraction."""

    SYSTEM_PROMPT = """你是一个专业的中医知识图谱信息抽取助手。你的任务是从中医药文本中提取结构化的实体和关系信息。

请严格按照要求的JSON格式输出，不要添加任何额外的文字说明。"""

    MEDICINE_EXTRACTION = """请从以下中药文本中提取结构化信息：

{text}

请提取以下字段，并以JSON格式返回：
- name: 药名（必填）
- aliases: 别名列表
- pinyin: 拼音名
- nature: 药性（寒/热/温/凉/平）
- flavors: 药味列表（酸/苦/甘/辛/咸等）
- meridians: 归经列表
- functions: 功效列表
- indications: 主治列表
- usage: 用法用量
- contraindications: 禁忌列表
- source: 来源/基原

输出格式示例：
```json
{{
  "name": "黄芪",
  "aliases": ["黄耆", "绵芪"],
  "pinyin": "Huang Qi",
  "nature": "温",
  "flavors": ["甘"],
  "meridians": ["肺经", "脾经"],
  "functions": ["补气升阳", "固表止汗", "利水消肿", "生津养血", "托毒生肌"],
  "indications": ["气虚乏力", "食少便溏", "中气下陷", "久泻脱肛"],
  "usage": "9-30g",
  "contraindications": ["表实邪盛", "气滞湿阻", "食积停滞"],
  "source": "豆科植物蒙古黄芪或膜荚黄芪的干燥根"
}}
```"""

    PRESCRIPTION_EXTRACTION = """请从以下方剂文本中提取结构化信息：

{text}

请提取以下字段，并以JSON格式返回：
- name: 方剂名（必填）
- aliases: 别名列表
- pinyin: 拼音名
- source_book: 出处/来源书籍
- composition: 组成列表，每个元素包含 medicine_name（药名）和 dosage（剂量）
- functions: 功效列表
- indications: 主治列表
- dosage: 用法用量
- contraindications: 禁忌列表
- formula_explanation: 方解

输出格式示例：
```json
{{
  "name": "四君子汤",
  "aliases": [],
  "pinyin": "Si Jun Zi Tang",
  "source_book": "《太平惠民和剂局方》",
  "composition": [
    {{"medicine_name": "人参", "dosage": "10g"}},
    {{"medicine_name": "白术", "dosage": "9g"}},
    {{"medicine_name": "茯苓", "dosage": "9g"}},
    {{"medicine_name": "甘草", "dosage": "6g"}}
  ],
  "functions": ["益气健脾"],
  "indications": ["脾胃气虚证", "面色萎白", "语声低微", "食少便溏"],
  "dosage": "水煎服",
  "contraindications": ["阴虚内热者慎用"],
  "formula_explanation": "方中人参甘温，益气补中为君；白术健脾燥湿为臣..."
}}
```"""

    RELATION_EXTRACTION = """请从以下中医文本中提取实体关系：

{text}

请识别以下类型的关系：
1. 治疗关系：中药/方剂 -> 治疗 -> 疾病/症状
2. 组成关系：方剂 -> 包含 -> 中药
3. 归经关系：中药 -> 归 -> 经络
4. 配伍关系：中药 -> 配伍 -> 中药（相须/相使/相畏/相杀/相恶/相反）
5. 禁忌关系：中药/方剂 -> 禁用于 -> 证候/人群

请以JSON格式返回关系列表：
```json
{{
  "relations": [
    {{
      "source": "黄芪",
      "source_type": "Medicine",
      "relation": "TREATS",
      "target": "气虚乏力",
      "target_type": "Symptom",
      "properties": {{}}
    }},
    {{
      "source": "四君子汤",
      "source_type": "Prescription",
      "relation": "CONTAINS",
      "target": "人参",
      "target_type": "Medicine",
      "properties": {{"dosage": "10g", "role": "君药"}}
    }}
  ]
}}
```"""

    ENTITY_LINKING = """请将以下中医术语标准化并链接到标准实体：

术语列表：
{terms}

对于每个术语，请识别其类型并提供标准名称：
- Medicine（中药）
- Prescription（方剂）
- Disease（疾病）
- Symptom（症状）
- Meridian（经络）
- Syndrome（证候）

输出格式：
```json
{{
  "entities": [
    {{
      "original": "参",
      "standard_name": "人参",
      "type": "Medicine",
      "confidence": 0.95
    }},
    {{
      "original": "四君子",
      "standard_name": "四君子汤",
      "type": "Prescription",
      "confidence": 0.98
    }}
  ]
}}
```"""

    QUESTION_TO_CYPHER = """你是一个Neo4j Cypher查询专家。请将用户的自然语言问题转换为Cypher查询。

知识图谱结构：
- 节点类型：Medicine（中药）, Prescription（方剂）, Disease（疾病）, Symptom（症状）
- 关系类型：
  - TREATS: 中药/方剂 -> 疾病/症状
  - CONTAINS: 方剂 -> 中药（属性：dosage剂量, role角色）
  - ENTERS_MERIDIAN: 中药 -> 经络
  - CONTRAINDICATED_WITH: 中药 -> 中药（配伍禁忌）

用户问题：{question}

请返回Cypher查询和解释：
```json
{{
  "cypher": "MATCH (m:Medicine) WHERE m.name = '黄芪' RETURN m",
  "explanation": "查找名为黄芪的中药实体"
}}
```"""

    TCM_QA_SYSTEM = """你是一个专业的中医知识问答助手。请基于提供的知识图谱信息回答用户问题。

回答要求：
1. 准确引用知识图谱中的信息
2. 使用专业但易懂的中医术语
3. 如有需要，提供额外的解释说明
4. 如果信息不足，请明确说明

知识图谱查询结果：
{context}

用户问题：{question}

请提供专业、准确的回答。"""
