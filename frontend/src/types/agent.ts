// Matches backend: app/schemas/agent.py
import type { PropertySearchResult, PropertyType } from '@/types/property'

export interface AgentSession {
  session_id: number
  session_uuid: string
  cart_id: number
  title: string | null
}

/** Agent 对话记录列表项。 */
export interface AgentSessionSummary {
  session_id: number
  session_uuid: string
  title: string | null
  status: string
  message_count: number
  last_message: string | null
  created_at: string
  updated_at: string
}

export interface AgentSessionListResponse {
  items: AgentSessionSummary[]
  total: number
}

/** 从历史会话回放的消息；结构化结果保存在 metadata 中。 */
export interface AgentHistoryMessage {
  id: number
  session_id: number
  role: 'user' | 'assistant'
  content: string
  metadata: Record<string, unknown> | null
  created_at: string
}

export interface AgentHistoryResponse {
  items: AgentHistoryMessage[]
  has_more: boolean
}

/** 跨会话长期记忆。 */
export interface AgentMemory {
  preferences: AgentFilters
  updated_at?: string | null
}

export interface AgentFilters {
  country?: string | null
  currency?: string | null
  district?: string | null
  price_min?: number | null
  price_max?: number | null
  bedrooms?: number | null
  property_type?: PropertyType | null
  /** 设施硬要求（引导 chip「要独立卫浴」注入） */
  amenities?: string[] | null
  bathrooms?: number | null
  room_type?: string | null
  institution?: string | null
  commute_mode?: string | null
  commute_minutes?: number | null
  area_min?: number | null
  area_max?: number | null
  min_lease_months?: number | null
  max_lease_months?: number | null
  available_from?: string | null
  female_only?: boolean | null
  /** 渐进选房累积的周边偏好：[{type: "transit"}, ...] */
  poi_requirements?: { type: string; max_distance_m?: number }[] | null
}

/** 渐进选房引导 chip：点击后 filter_patch 并入累积 filters 再重发 */
export interface GuidedOption {
  label: string
  message: string
  filter_patch?: Record<string, unknown> | null
  kind: string
  icon: string
}

export interface AgentMessageRequest {
  message: string
  filters?: AgentFilters | null
  /** 普通搜索页当前条件；自然语言本轮修改可以覆盖这些上下文。 */
  context_filters?: AgentFilters | null
  compare_property_ids?: number[]  // 候选清单勾选后传，触发对比意图
  /** 兼容旧页面模式值；当前智能主链路由后端统一归一化。 */
  mode?: string | null
}

export type AgentIntent =
  | 'recommend'
  | 'search'
  | 'add_to_cart'
  | 'remove_from_cart'
  | 'manage_cart'
  | 'compare'
  | 'compare_cart'
  | 'faq'
  | 'general'

export interface AgentRecommendation {
  property_id: number
  rank: number
  final_score: number
  score_breakdown: Record<string, number>
  match_reason: string
  pros: string[]
  cons: string[]
  property: PropertySearchResult
  /** 周边设施最近距离（米）：{"transit":350, "supermarket":200} */
  poi_distances?: Record<string, number> | null
  /** 后端事实来源与缺失字段，Grounded Answer 使用 */
  source_metadata: Record<string, unknown>
}

export interface AgentSource {
  label: string
  status: 'verified' | 'missing' | string
}

export interface QueryRewriteInfo {
  original: string
  rewritten: string
  kind: 'exact' | 'relative' | 'reference' | 'exploratory' | string
  used_llm: boolean
}

export interface AgentStateChip {
  key: string
  label: string
}

export interface AgentStateSummary {
  stage: string
  filters: Record<string, unknown>
  chips: AgentStateChip[]
}

export interface ReferenceResolutionInfo {
  resolved_ids: number[]
  labels: string[]
  unresolved: string[]
}

/** 回复中附带的站内页面深链 */
export interface AgentLink {
  label: string
  to: string
}

/** FAQ 快捷入口 chip */
export interface FaqChip {
  id: string
  chip: string
}

/** 可验证的处理动作摘要；不包含模型思维链。 */
export interface ThinkingStep {
  agent_id: string
  agent_name: string
  status: 'pending' | 'running' | 'success' | 'error'
  summary: string
  duration_ms: number
}

export interface AgentMessageResponse {
  reply: string
  intent: AgentIntent
  recommendations: AgentRecommendation[]   // 全部匹配房源（"查看所有"展开使用）
  top_picks: AgentRecommendation[]          // 精选 Top 3（首屏卡片）
  cart_changed: boolean
  ai_available: boolean
  quick_replies: string[]
  links: AgentLink[]
  thinking_steps: ThinkingStep[]
  /** 渐进选房引导 chips（点击携带 filter_patch 收窄） */
  guided_options: GuidedOption[]
  raw_intent: string
  stage: string
  sources: AgentSource[]
  relaxation_trace: Record<string, unknown>[]
  query_rewrite: QueryRewriteInfo | null
  reference_resolution: ReferenceResolutionInfo | null
  state_summary: AgentStateSummary | null
  /** 本轮可安全同步到普通搜索栏的明确条件；null 表示清除。 */
  filter_patch: Record<string, unknown>
}

export interface AgentStreamMeta extends Partial<AgentMessageResponse> {
  event?: 'status' | 'result'
}

export interface CartItem {
  id: number
  property_id: number
  reason: string | null
  created_at: string
  property: PropertySearchResult
}

export interface Cart {
  id: number
  session_id: number | null
  items: CartItem[]
}

/** 对比优先级：决定加权评分的权重 */
export type ComparePriority = 'balanced' | 'budget' | 'commute' | 'space'

export interface CompareItem {
  property_id: number
  title: string
  pros: string[]
  cons: string[]
  /** 系统确定性加权得分（非 LLM 打分，可复现） */
  score: number
  /** 分项得分：price/commute/space/rating */
  score_breakdown: Record<string, number> | null
  best_for: string
  /** 如 "最近交通站点约500m"（来自 POI 数据） */
  commute: string | null
  /** 机构真实评价均分（1-5），无评价为 null */
  rating: number | null
  review_count: number
  property: PropertySearchResult | null
}

export interface CompareResponse {
  summary: string
  items: CompareItem[]
  recommendation: string
  ai_available: boolean
  priority: ComparePriority
}

/** 聊天气泡（前端本地状态） */
export interface AgentChatMessage {
  /** 后端消息 ID；本地欢迎语和发送中的消息没有 ID。 */
  id?: number
  role: 'user' | 'assistant'
  content: string
  /** 精选 Top 3 房源（首屏横向卡片） */
  topPicks?: AgentRecommendation[]
  /** 全部匹配房源（"查看所有"按钮跳转搜索页使用） */
  allRecommendations?: AgentRecommendation[]
  /** 该条 AI 消息附带的推荐房源，内联渲染成横条 */
  recommendations?: AgentRecommendation[]
  /** 该轮是否有 AI 分析（用于横条上的降级提示） */
  aiAvailable?: boolean
  /** 后续建议 chips（点击即作为消息发送） */
  quickReplies?: string[]
  /** 站内页面深链按钮 */
  links?: AgentLink[]
  /** 专家模式思考步骤 */
  thinkingSteps?: ThinkingStep[]
  /** 渐进收窄/零结果放宽建议 */
  guidedOptions?: GuidedOption[]
  /** 当前会话已记住的条件 */
  stateSummary?: AgentStateSummary | null
  /** 本轮查询改写摘要 */
  queryRewrite?: QueryRewriteInfo | null
  /** 回答使用的数据来源 */
  sources?: AgentSource[]
  /** 该轮已同步或可同步到普通搜索栏的条件。 */
  filterPatch?: Record<string, unknown>
  /** 是否仍在接收流式文本 */
  streaming?: boolean
  /** 固定欢迎语标识，历史回放时不会重复写入后端。 */
  isWelcome?: boolean
}
