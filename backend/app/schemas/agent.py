"""租房推荐 Agent —— 请求/响应 schema"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.property import PropertySearchResult


# ── 会话 ──────────────────────────────────────────────────────────

class AgentSessionResponse(BaseModel):
    session_id: int
    session_uuid: str
    cart_id: int
    title: str | None = None


# ── 消息 ──────────────────────────────────────────────────────────

class AgentFilters(BaseModel):
    country: str | None = None
    district: str | None = None
    price_min: float | None = Field(default=None, ge=0)
    price_max: float | None = Field(default=None, ge=0)
    bedrooms: int | None = Field(default=None, ge=0)
    property_type: str | None = None


class AgentMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    filters: AgentFilters | None = None


class AgentRecommendation(BaseModel):
    property_id: int
    match_reason: str = ""
    pros: list[str] = []
    cons: list[str] = []
    property: PropertySearchResult


class AgentLink(BaseModel):
    """回复中附带的站内页面深链"""
    label: str
    to: str


class AgentMessageResponse(BaseModel):
    reply: str
    intent: str
    recommendations: list[AgentRecommendation] = []
    cart_changed: bool = False
    ai_available: bool = True
    quick_replies: list[str] = []   # 后续建议 chips（点击即作为消息发送）
    links: list[AgentLink] = []     # 站内页面深链按钮


class FaqChip(BaseModel):
    """FAQ 快捷入口 chip"""
    id: str
    chip: str


# ── 购物车 ────────────────────────────────────────────────────────

class CartItemAddRequest(BaseModel):
    property_id: int
    reason: str | None = None


class CartItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    reason: str | None = None
    created_at: datetime
    property: PropertySearchResult


class CartRead(BaseModel):
    id: int
    session_id: int | None = None
    items: list[CartItemRead] = []


# ── 对比 ──────────────────────────────────────────────────────────

class CompareRequest(BaseModel):
    """对比请求。property_ids 为空/缺省时对比整个购物车。

    priority 决定加权评分的权重：balanced 均衡 / budget 预算优先 /
    commute 通勤优先 / space 空间优先（非法值按 balanced 处理）。
    """
    property_ids: list[int] | None = None
    priority: str | None = None


class CompareItem(BaseModel):
    property_id: int
    title: str = ""
    pros: list[str] = []
    cons: list[str] = []
    score: int = 0                                  # 系统确定性加权得分（非 LLM 打分）
    score_breakdown: dict[str, int] | None = None   # 分项：price/commute/space/rating
    best_for: str = ""
    commute: str | None = None                      # 如 "最近交通站点约500m"
    rating: float | None = None                     # 机构真实评价均分（1-5）
    review_count: int = 0
    property: PropertySearchResult | None = None


class CompareResponse(BaseModel):
    summary: str
    items: list[CompareItem]
    recommendation: str
    ai_available: bool = True
    priority: str = "balanced"
