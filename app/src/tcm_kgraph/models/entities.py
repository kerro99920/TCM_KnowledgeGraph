"""Domain entities for Traditional Chinese Medicine knowledge graph."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class MedicineCategory(str, Enum):
    """Categories of traditional Chinese medicines."""

    HERB = "herb"  # 草药
    MINERAL = "mineral"  # 矿物药
    ANIMAL = "animal"  # 动物药
    PROCESSED = "processed"  # 炮制品


class MedicineProperty(BaseModel):
    """Properties of a traditional Chinese medicine (四气五味)."""

    model_config = ConfigDict(frozen=True)

    nature: str | None = Field(default=None, description="药性 (寒/热/温/凉/平)")
    flavor: list[str] = Field(default_factory=list, description="药味 (酸/苦/甘/辛/咸)")
    meridians: list[str] = Field(default_factory=list, description="归经")
    toxicity: str | None = Field(default=None, description="毒性")


class Medicine(BaseModel):
    """Traditional Chinese Medicine (中药) entity."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = Field(default=None, description="Unique identifier")
    name: str = Field(description="药名")
    aliases: list[str] = Field(default_factory=list, description="别名")
    pinyin: str | None = Field(default=None, description="拼音名")
    latin_name: str | None = Field(default=None, description="拉丁名")
    english_name: str | None = Field(default=None, description="英文名")

    category: MedicineCategory | None = Field(default=None, description="药物分类")
    properties: MedicineProperty = Field(
        default_factory=MedicineProperty, description="药性"
    )

    source: str | None = Field(default=None, description="来源/基原")
    habitat: str | None = Field(default=None, description="产地")
    processing: str | None = Field(default=None, description="炮制方法")

    functions: list[str] = Field(default_factory=list, description="功效")
    indications: list[str] = Field(default_factory=list, description="主治")
    usage: str | None = Field(default=None, description="用法用量")
    contraindications: list[str] = Field(default_factory=list, description="禁忌")

    raw_text: str | None = Field(default=None, description="原始文本内容")
    source_url: str | None = Field(default=None, description="数据来源URL")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class Prescription(BaseModel):
    """Traditional Chinese Medicine Prescription (方剂) entity."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = Field(default=None, description="Unique identifier")
    name: str = Field(description="方剂名")
    aliases: list[str] = Field(default_factory=list, description="别名")
    pinyin: str | None = Field(default=None, description="拼音名")

    source_book: str | None = Field(default=None, description="出处/来源书籍")
    category: str | None = Field(default=None, description="方剂分类")

    composition: list[Annotated[dict[str, str], Field(description="组成药物")]] = Field(
        default_factory=list,
        description="组成 (药名, 用量)",
    )
    preparation: str | None = Field(default=None, description="制法")
    dosage: str | None = Field(default=None, description="用法用量")

    functions: list[str] = Field(default_factory=list, description="功效")
    indications: list[str] = Field(default_factory=list, description="主治")
    contraindications: list[str] = Field(default_factory=list, description="禁忌")

    formula_explanation: str | None = Field(default=None, description="方解")
    clinical_applications: list[str] = Field(default_factory=list, description="临床应用")
    modifications: list[str] = Field(default_factory=list, description="加减变化")

    raw_text: str | None = Field(default=None, description="原始文本内容")
    source_url: str | None = Field(default=None, description="数据来源URL")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class Disease(BaseModel):
    """Disease (疾病) entity."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = Field(default=None, description="Unique identifier")
    name: str = Field(description="疾病名称")
    aliases: list[str] = Field(default_factory=list, description="别名")
    category: str | None = Field(default=None, description="疾病分类")

    tcm_name: str | None = Field(default=None, description="中医病名")
    western_name: str | None = Field(default=None, description="西医病名")

    etiology: list[str] = Field(default_factory=list, description="病因")
    pathogenesis: str | None = Field(default=None, description="病机")
    symptoms: list[str] = Field(default_factory=list, description="症状")

    diagnosis: str | None = Field(default=None, description="诊断")
    treatment_principles: list[str] = Field(default_factory=list, description="治则治法")
    prevention: list[str] = Field(default_factory=list, description="预防")


class Symptom(BaseModel):
    """Symptom (症状) entity."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = Field(default=None, description="Unique identifier")
    name: str = Field(description="症状名称")
    aliases: list[str] = Field(default_factory=list, description="别名")

    description: str | None = Field(default=None, description="症状描述")
    body_part: str | None = Field(default=None, description="相关部位")
    severity: str | None = Field(default=None, description="严重程度")

    related_patterns: list[str] = Field(default_factory=list, description="相关证型")
