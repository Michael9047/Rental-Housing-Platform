// 租房 Agent 前后端协议类型：以 UnitType 为推荐与候选清单的最小实体。
import type { PropertySearchResult, PropertyType } from '@/types/property'

export interface AgentSession {
  session_id: number
  session_uuid: string
  cart_id: number
  title: string | null
}

/** Agent 历史会话侧栏摘要。 */
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

/** 后端持久化的一条 Agent 消息，结构化推荐结果位于 metadata。 */
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

/** 用户主动保存、可跨会话复用的长期偏好。 */
export interface AgentMemory {
  preferences: AgentFilters
  updated_at?: string | null
}

/**
 * Agent 使用的筛选上下文。
 *
 * Institute/UnitType 搜索使用 city、institute_id 等 main 字段；institution
 * 保留自然语言学校/机构名称，供后端查询理解使用。
 */
export interface AgentFilters {
  country?: string | null
  currency?: string | null
  city?: string | null
  district?: string | null
  institute_id?: number | null
  institution?: string | null
  price_min?: number | null
  price_max?: number | null
  bedrooms?: number | null
  bathrooms?: number | null
  property_type?: PropertyType | null
  room_type?: string | null
  amenities?: string[] | null
  area_min?: number | null
  area_max?: number | null
  min_lease_months?: number | null
  max_lease_months?: number | null
  available_from?: string | null
  female_only?: boolean | null
  commute_mode?: string | null
  commute_minutes?: number | null
  poi_requirements?: Array<{ type: string; max_distance_m?: number }> | null
}

/** 可通过明确协议清除的 Agent 筛选字段。 */
export type AgentFilterField = keyof AgentFilters

/** 服务端对本轮消息与当前找房任务关系的判断。 */
export type AgentTaskRelation = 'continue' | 'new' | 'clarify'

/** 前端对任务边界自动判断的可选覆盖方式。 */
export type AgentTaskMode = 'auto' | 'continue' | 'new'

/** 找房任务边界元数据；用于安全切换筛选上下文与本地对比选择。 */
export interface AgentTaskBoundary {
  relation: AgentTaskRelation
  task_id: string
  reason: string
  reset_fields: AgentFilterField[]
  clarification_question?: string | null
}

/** 渐进选房选项：点击后把 patch 合并进当前筛选上下文。 */
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
  /** 搜索页当前条件；本轮自然语言中的明确条件可以覆盖它。 */
  context_filters?: AgentFilters | null
  /** 唯一的显式清除通道；filters/context_filters 内的 null 不代表清除。 */
  clear_fields?: AgentFilterField[]
  /** 这里始终传 UnitType ID，不能传 Building/Institute ID。 */
  compare_property_ids?: number[]
  mode?: string | null
  task_mode?: AgentTaskMode
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
  /** UnitType ID，也是候选清单与独立对比使用的 ID。 */
  property_id: number
  rank?: number
  match_reason: string
  pros: string[]
  cons: string[]
  /** main 的 PropertySearchResult 实际承载 UnitType + Institute 继承字段。 */
  property: PropertySearchResult
  poi_distances?: Record<string, number> | null
  source_metadata?: Record<string, unknown>
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

/** 回复中附带的站内页面深链。 */
export interface AgentLink {
  label: string
  to: string
}

export interface FaqChip {
  id: string
  chip: string
}

/** 可展示的执行状态摘要，不包含模型思维链。 */
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
  /** 后端未截断前的真实匹配数量。 */
  recommendation_total: number
  recommendations: AgentRecommendation[]
  top_picks: AgentRecommendation[]
  cart_changed: boolean
  ai_available: boolean
  quick_replies: string[]
  links: AgentLink[]
  thinking_steps: ThinkingStep[]
  guided_options: GuidedOption[]
  raw_intent: string
  stage: string
  sources: AgentSource[]
  relaxation_trace: Record<string, unknown>[]
  query_rewrite: QueryRewriteInfo | null
  reference_resolution: ReferenceResolutionInfo | null
  state_summary: AgentStateSummary | null
  /** 本轮从用户消息/本轮筛选变化中提取出的需求。 */
  turn_summary?: AgentStateSummary | null
  /** 本轮与当前找房任务的关系；旧后端可能不返回。 */
  task_boundary?: AgentTaskBoundary | null
  /** 可安全同步回普通搜索栏的新增或更新条件，不承载清除语义。 */
  filter_patch: Record<string, unknown>
  /** 服务端确认本轮应从会话和普通搜索栏删除的条件。 */
  cleared_filters: AgentFilterField[]
}

/** SSE 的 status/result 元数据事件。 */
export interface AgentStreamMeta extends Partial<AgentMessageResponse> {
  event?: 'status' | 'result'
  status?: 'understanding' | 'searching' | 'comparing' | 'generating' | string
  message?: string
}

export interface CartItem {
  id: number
  /** UnitType ID。 */
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

export type ComparePriority = 'balanced' | 'budget' | 'commute' | 'space' | 'safety'

export interface CompareItem {
  /** UnitType ID。 */
  property_id: number
  title: string
  pros: string[]
  cons: string[]
  /** main 旧响应仍可能包含确定性评分字段。 */
  score?: number
  score_breakdown?: Record<string, number> | null
  best_for: string
  commute: string | null
  commute_meters?: number | null
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

/** 前端聊天气泡状态。 */
export interface AgentChatMessage {
  id?: number
  role: 'user' | 'assistant'
  content: string
  topPicks?: AgentRecommendation[]
  allRecommendations?: AgentRecommendation[]
  recommendations?: AgentRecommendation[]
  recommendationTotal?: number
  aiAvailable?: boolean
  quickReplies?: string[]
  links?: AgentLink[]
  thinkingSteps?: ThinkingStep[]
  guidedOptions?: GuidedOption[]
  stateSummary?: AgentStateSummary | null
  turnSummary?: AgentStateSummary | null
  taskBoundary?: AgentTaskBoundary | null
  queryRewrite?: QueryRewriteInfo | null
  sources?: AgentSource[]
  filterPatch?: Record<string, unknown>
  clearedFilters?: AgentFilterField[]
  streaming?: boolean
  isWelcome?: boolean
}
