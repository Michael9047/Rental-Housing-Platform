"""对比 Agent 请求/响应 Schema"""
from datetime import datetime

from pydantic import BaseModel, Field


# ── 创建会话 ──────────────────────────────────────────────────────

class CompareSessionCreate(BaseModel):
    property_ids: list[int] = Field(..., min_length=2, max_length=10)
    priority: str = Field("balanced", pattern=r"^(balanced|budget|commute|space|safety)$")


class CompareSessionResponse(BaseModel):
    id: int
    user_id: int
    property_ids: list[int]
    priority: str
    status: str
    result_cache: dict | None = None
    created_at: datetime
    messages: list["CompareMessageRead"] = []

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
    scores: dict[int, dict] = {}         # {property_id: {total: int, breakdown: {dim: int}}}
    tool_trail: list[dict] = []          # 调试/审计：工具调用轨迹
    property_data: dict[int, dict] = {}  # {property_id: EnrichedPropertyData}
