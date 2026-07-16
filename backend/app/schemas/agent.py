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


class AgentSessionSummary(BaseModel):
    """会话列表项（左侧对话列表用）"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None = None
    created_at: datetime
    updated_at: datetime


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
    # 追问面板提交：字段名 -> 原始 option.value（如 "3000"、"__any__"）。
    # 和 filters 分开是因为 filters 是严格类型的可见筛选栏，装不下 "__any__" 这种哨兵值。
    slot_answers: dict[str, str] | None = None


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


class ElicitOption(BaseModel):
    """引导追问的可选项（"__any__" 表示不限）"""
    label: str
    value: str


class ElicitGroup(BaseModel):
    """追问面板里的一个维度（如"预算"），渲染成一行可点选项"""
    field: str            # district / price_max / bedrooms / property_type
    label: str
    question: str
    options: list[ElicitOption] = []


class AgentElicit(BaseModel):
    """引导式追问：把所有缺失维度一次性摆成多组面板（而非一次问一个），可跨维度选完再统一发送"""
    groups: list[ElicitGroup] = []
    allow_custom: bool = True


class AgentMessageResponse(BaseModel):
    message_id: int | None = None      # 本轮 AI 回复的消息 id，用于点赞/点踩
    reply: str
    intent: str
    recommendations: list[AgentRecommendation] = []
    cart_changed: bool = False
    ai_available: bool = True
    quick_replies: list[str] = []      # 后续建议 chips（点击即作为消息发送）
    links: list[AgentLink] = []        # 站内页面深链按钮
    elicit: AgentElicit | None = None  # intent=elicit 时的追问面板


class AgentHistoryMessage(BaseModel):
    """历史消息回放（切换会话时用）"""
    id: int | None = None
    role: str
    content: str
    recommendations: list[AgentRecommendation] = []
    elicit: AgentElicit | None = None
    feedback: str | None = None        # "up" / "down" / None
    intent: str | None = None          # assistant 消息的意图，前端据此决定气泡样式（如 FAQ 卡片）
    created_at: datetime


class MessageFeedbackRequest(BaseModel):
    feedback: str | None = Field(default=None, pattern="^(up|down)$")


class MessageFeedbackResponse(BaseModel):
    message_id: int
    feedback: str | None = None


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
