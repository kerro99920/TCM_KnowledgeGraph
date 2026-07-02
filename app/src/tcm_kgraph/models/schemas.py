"""API 请求/响应模型。"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """健康检查状态。"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: HealthStatus = Field(description="整体状态")
    version: str = Field(description="应用版本")
    timestamp: datetime = Field(default_factory=datetime.now)
    components: dict[str, HealthStatus] = Field(default_factory=dict, description="组件状态")


class SearchRequest(BaseModel):
    """名称模糊检索请求。"""

    query: str = Field(min_length=1, max_length=200, description="检索关键词")
    entity_types: list[str] | None = Field(default=None, description="限定标签范围")
    limit: int = Field(default=10, ge=1, le=100)


class SearchResult(BaseModel):
    """单条检索结果。"""

    entity_type: str
    entity_id: str
    name: str
    score: float = Field(ge=0, le=1)


class EntityResponse(BaseModel):
    """实体详情响应。"""

    entity_type: str
    entity_id: str
    data: dict[str, Any]
    related_entities: list[dict[str, Any]] = Field(default_factory=list)


class GraphQueryRequest(BaseModel):
    """只读 Cypher 查询请求。"""

    cypher: str = Field(min_length=1, description="Cypher 语句（仅只读）")
    parameters: dict[str, Any] = Field(default_factory=dict)


class GraphQueryResponse(BaseModel):
    """Cypher 查询响应。"""

    raw_results: list[dict[str, Any]] = Field(default_factory=list)
    executed_cypher: str | None = Field(default=None, description="实际执行的语句（含 LIMIT 兜底）")


class MessageRole(str, Enum):
    """对话角色。"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """单条对话消息。"""

    role: MessageRole
    content: str


class ChatRequest(BaseModel):
    """问答请求。"""

    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """问答响应。"""

    message: str
    sources: list[dict[str, Any]] = Field(default_factory=list, description="图谱来源实体")
    graph_query: str | None = Field(default=None, description="实际执行的 Cypher")
    intent: str | None = Field(default=None, description="识别的问题意图")
