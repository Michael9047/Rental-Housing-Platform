"""对比 Agent 请求/响应 Schema"""
from datetime import datetime

from pydantic import BaseModel, Field


# ── 创建会话 ──────────────────────────────────────────────────────

class CompareSessionCreate(BaseModel):
    # 兼容字段名；每个值始终是 UnitType.id。
    property_ids: list[int] = Field(..., min_length=2, max_length=5)
    priority: str = Field("balanced", pattern=r"^(balanced|budget|commute|space|safety)$")


class CompareSessionResponse(BaseModel):
    id: int
    user_id: int
    property_ids: list[int]
    priority: str
    status: str
    result_cache: dict | None = None
    created_at: datetime
    messages: list["CompareMessageRead"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CompareMessageRead(BaseModel):
    id: int
    role: str
    content: str | None = None
    tool_calls: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── 发送消息 ──────────────────────────────────────────────────────

class CompareMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    priority: str | None = Field(None, pattern=r"^(balanced|budget|commute|space|safety)?$")


class CompareMessageResponse(BaseModel):
    reply: str
    scores: dict[int, dict] = Field(default_factory=dict)
    tool_trail: list[dict] = Field(default_factory=list)
    property_data: dict[int, dict] = Field(default_factory=dict)
