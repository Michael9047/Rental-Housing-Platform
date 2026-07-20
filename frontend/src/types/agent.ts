// Matches backend: app/schemas/agent.py
import type { PropertySearchResult, PropertyType } from '@/types/property'

export interface AgentSession {
  session_id: number
  session_uuid: string
  cart_id: number
  title: string | null
}

export interface AgentFilters {
  country?: string | null
  district?: string | null
  price_min?: number | null
  price_max?: number | null
  bedrooms?: number | null
  property_type?: PropertyType | null
}

export interface AgentMessageRequest {
  message: string
  filters?: AgentFilters | null
  compare_property_ids?: number[]  // 候选清单勾选后传，触发对比意图
}

export type AgentIntent =
  | 'recommend'
  | 'add_to_cart'
  | 'remove_from_cart'
  | 'compare_cart'
  | 'faq'
  | 'general'

export interface AgentRecommendation {
  property_id: number
  match_reason: string
  pros: string[]
  cons: string[]
  property: PropertySearchResult
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

/** 专家模式：单个 Agent 执行步骤 */
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
}
