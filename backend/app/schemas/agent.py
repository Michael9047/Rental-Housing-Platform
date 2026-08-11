"""租房推荐 Agent —— 请求/响应 schema"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.property import PropertySearchResult


AgentFilterField = Literal[
    "country",
    "currency",
    "city",
    "district",
    "price_min",
    "price_max",
    "bedrooms",
    "property_type",
    "amenities",
    "room_type",
    "bathrooms",
    "area_min",
    "area_max",
    "min_lease_months",
    "max_lease_months",
    "available_from",
    "poi_requirements",
    "commute_mode",
    "commute_minutes",
    "institution",
    "institute_id",
    "female_only",
]


# ── 会话 ──────────────────────────────────────────────────────────

class AgentSessionResponse(BaseModel):
    session_id: int
    session_uuid: str
    cart_id: int
    title: str | None = None


class AgentSessionSummary(BaseModel):
    """Agent 对话记录列表项。"""

    session_id: int
    session_uuid: str
    title: str | None = None
    status: str
    message_count: int = 0
    last_message: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentSessionListResponse(BaseModel):
    items: list[AgentSessionSummary] = Field(default_factory=list)
    total: int = 0


class AgentHistoryMessage(BaseModel):
    """可回放的一条 Agent 历史消息。"""

    id: int
    session_id: int
    role: str
    content: str
    metadata: dict | None = None
    created_at: datetime


class AgentHistoryResponse(BaseModel):
    items: list[AgentHistoryMessage] = Field(default_factory=list)
    has_more: bool = False


# ── 消息 ──────────────────────────────────────────────────────────

class AgentFilters(BaseModel):
    """结构化筛选条件。

    前端 filter bar 提供前 6 个基础字段；LLM 从自然语言中提取
    amenities / room_type / poi_requirements 等硬约束字段。
    """
    # ── 基础字段（前端 filter bar） ──
    country: str | None = None
    currency: str | None = None
    city: str | None = None
    district: str | None = None
    price_min: float | None = Field(default=None, ge=0)
    price_max: float | None = Field(default=None, ge=0)
    bedrooms: int | None = Field(default=None, ge=0)
    property_type: str | None = None

    # ── 硬约束字段（LLM 从 NL 提取 + 前端可选） ──
    amenities: list[str] | None = None          # 设施硬要求，如 ["宠物友好", "独立厨房"]
    room_type: str | None = None                # 房型：studio/ensuite/1bed/2bed/3bed+/shared
    bathrooms: int | None = Field(default=None, ge=0)  # 卫生间数
    area_min: float | None = Field(default=None, ge=0)  # 最小面积
    area_max: float | None = Field(default=None, ge=0)  # 最大面积
    min_lease_months: int | None = Field(default=None, ge=1)  # 最短租期
    max_lease_months: int | None = Field(default=None, ge=1)  # 最长租期
    available_from: str | None = None           # 可入住时间（YYYYMM 格式）

    # ── 周边配套硬约束（LLM 提取） ──
    poi_requirements: list[dict] | None = None  # [{"type": "地铁站", "max_distance_m": 500}, ...]

    # ── 通勤硬约束（LLM 提取） ──
    commute_mode: str | None = None             # walking/bicycling/driving/transit
    commute_minutes: int | None = None          # 通勤时间上限（分钟）

    # ── 机构/学校 ──
    institution: str | None = None              # 大学/机构名
    institute_id: int | None = Field(default=None, ge=1)  # 精确公寓 ID（Institute.id）
    female_only: bool | None = None              # 是否仅限女生

    # ── 元数据（LLM 标注哪些是硬约束、哪些是软偏好） ──
    hard_filters: list[str] | None = None       # 标记为硬约束的字段名，如 ["amenities", "room_type"]
    soft_preferences: list[str] | None = None   # 标记为软偏好的字段名，如 ["price", "district"]


class AgentMessageRequest(BaseModel):
    """Agent 消息请求（extra="ignore" 保证旧前端发 mode 等字段不报错）"""
    message: str = Field(min_length=1, max_length=20_000)
    filters: AgentFilters | None = None
    # 搜索页当前筛选条件；本轮自然语言或 filters 中的值优先覆盖。
    context_filters: AgentFilters | None = None
    # 唯一合法的显式清除通道；filters/context_filters 中的 null 仅表示未提供。
    clear_fields: list[AgentFilterField] = Field(default_factory=list, max_length=23)
    compare_property_ids: list[int] | None = None  # 前端候选清单勾选后传，触发对比意图
    mode: str | None = "auto"
    # 自动判断任务边界；显式 continue/new 供前端或用户确认后覆盖规则判断。
    task_mode: Literal["auto", "continue", "new"] = "auto"

    model_config = ConfigDict(extra="ignore")


class AgentMemoryResponse(BaseModel):
    """用户显式保存、可跨会话复用的长期偏好。"""

    preferences: AgentFilters = Field(default_factory=AgentFilters)
    updated_at: datetime | None = None


class AgentMemoryUpdateRequest(BaseModel):
    """显式保存长期偏好；replace=false 时只覆盖传入字段。"""

    preferences: AgentFilters
    replace: bool = False


class AgentRecommendation(BaseModel):
    # 兼容字段名；值始终是 UnitType.id，不是 Institute.id。
    property_id: int
    rank: int = 0
    match_reason: str = ""
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    property: PropertySearchResult
    source_metadata: dict = Field(default_factory=dict)


class AgentLink(BaseModel):
    """回复中附带的站内页面深链"""
    label: str
    to: str


class ThinkingStep(BaseModel):
    """专家模式 Agent 执行步骤"""
    agent_id: str
    agent_name: str
    status: str  # "pending" | "running" | "success" | "error"
    summary: str = ""  # 简短摘要
    duration_ms: int = 0


class GuidedOption(BaseModel):
    """渐进选房引导 chip。"""

    label: str = ""
    message: str = ""
    filter_patch: dict | None = None
    kind: str = ""
    icon: str = ""


class AgentStateSummary(BaseModel):
    """当前会话已确认的筛选状态。"""

    stage: str = "explore"
    filters: dict = Field(default_factory=dict)
    chips: list[dict[str, str]] = Field(default_factory=list)


class AgentTaskBoundary(BaseModel):
    """本轮与当前找房任务的关系及状态重置说明。"""

    relation: Literal["continue", "new", "clarify"] = "continue"
    task_id: str
    reason: str = ""
    reset_fields: list[str] = Field(default_factory=list)
    clarification_question: str | None = None


class AgentMessageResponse(BaseModel):
    reply: str
    intent: str
    recommendations: list[AgentRecommendation] = Field(default_factory=list)    # 最多展示 20 个匹配户型
    recommendation_total: int = 0                                                # 未截断的真实匹配总数
    top_picks: list[AgentRecommendation] = Field(default_factory=list)          # 精选 Top 3
    cart_changed: bool = False
    ai_available: bool = True
    quick_replies: list[str] = Field(default_factory=list)
    links: list[AgentLink] = Field(default_factory=list)
    thinking_steps: list[ThinkingStep] = Field(default_factory=list)
    guided_options: list[GuidedOption] = Field(default_factory=list)
    state_summary: AgentStateSummary | None = None
    turn_summary: AgentStateSummary | None = None
    filter_patch: dict = Field(default_factory=dict)
    # 服务端确认本轮已清除的字段，前端据此同步删除普通搜索栏条件。
    cleared_filters: list[AgentFilterField] = Field(default_factory=list)
    query_rewrite: dict | None = None
    sources: list[dict[str, str]] = Field(default_factory=list)
    task_boundary: AgentTaskBoundary | None = None


class FaqChip(BaseModel):
    """FAQ 快捷入口 chip"""
    id: str
    chip: str


# ── 购物车 ────────────────────────────────────────────────────────

class CartItemAddRequest(BaseModel):
    # 兼容字段名；值始终是 UnitType.id。
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
    items: list[CartItemRead] = Field(default_factory=list)


# ── 对比 ──────────────────────────────────────────────────────────

class CompareRequest(BaseModel):
    """对比请求。property_ids 为空/缺省时对比整个购物车。

    priority 决定加权评分的权重：balanced 均衡 / budget 预算优先 /
    commute 通勤优先 / space 空间优先 / safety 安全优先（非法值按 balanced 处理）。
    """
    # 兼容字段名；每个值都是 UnitType.id。独立对比限制为 2-5 项。
    property_ids: list[int] | None = Field(default=None, min_length=2, max_length=5)
    priority: str | None = None


class CompareItem(BaseModel):
    property_id: int
    title: str = ""
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    score: int = 0                                  # 系统确定性加权得分（非 LLM 打分）
    score_breakdown: dict[str, int] | None = None   # 分项：price/commute/space/rating/safety
    best_for: str = ""
    commute: str | None = None                      # 如 "最近交通站点约500m"
    rating: float | None = None                     # 机构真实评价均分（1-5）
    review_count: int = 0
    safety_score: float | None = None                # 公寓周边安全评分（0-5）
    property: PropertySearchResult | None = None


class CompareResponse(BaseModel):
    summary: str
    items: list[CompareItem]
    recommendation: str
    ai_available: bool = True
    priority: str = "balanced"
