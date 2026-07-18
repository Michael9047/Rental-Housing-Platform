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
    """结构化筛选条件。

    前端 filter bar 提供前 6 个基础字段；LLM 从自然语言中提取
    amenities / room_type / poi_requirements 等硬约束字段。
    """
    # ── 基础字段（前端 filter bar） ──
    country: str | None = None
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

    # ── 元数据（LLM 标注哪些是硬约束、哪些是软偏好） ──
    hard_filters: list[str] | None = None       # 标记为硬约束的字段名，如 ["amenities", "room_type"]
    soft_preferences: list[str] | None = None   # 标记为软偏好的字段名，如 ["price", "district"]


class AgentMessageRequest(BaseModel):
    """Agent 消息请求（extra="ignore" 保证旧前端发 mode 等字段不报错）"""
    message: str = Field(min_length=1, max_length=4000)
    filters: AgentFilters | None = None
    compare_property_ids: list[int] | None = None  # 前端候选清单勾选后传，触发对比意图

    model_config = ConfigDict(extra="ignore")


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


class ThinkingStep(BaseModel):
    """专家模式 Agent 执行步骤"""
    agent_id: str
    agent_name: str
    status: str  # "pending" | "running" | "success" | "error"
    summary: str = ""  # 简短摘要
    duration_ms: int = 0


class AgentMessageResponse(BaseModel):
    reply: str
    intent: str
    recommendations: list[AgentRecommendation] = []    # 全部匹配房源（"查看所有"展开用）
    top_picks: list[AgentRecommendation] = []          # 精选 Top 3（首屏卡片）
    cart_changed: bool = False
    ai_available: bool = True
    quick_replies: list[str] = []   # 后续建议 chips（点击即作为消息发送）
    links: list[AgentLink] = []     # 站内页面深链按钮
    thinking_steps: list[ThinkingStep] = []  # 专家模式 Agent 执行步骤


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
