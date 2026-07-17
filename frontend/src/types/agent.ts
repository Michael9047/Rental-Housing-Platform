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
  /** 追问面板提交：字段名 -> 选中的 option.value（如 "3000"、"__any__"） */
  slot_answers?: Record<string, string> | null
}

export type AgentIntent =
  | 'recommend'
  | 'elicit'
  | 'add_to_cart'
  | 'remove_from_cart'
  | 'compare_cart'
  | 'faq'
  | 'general'

/** 会话列表项（气泡左侧对话列表） */
export interface AgentSessionSummary {
  id: number
  title: string | null
  created_at: string
  updated_at: string
}

/** 引导追问的可选项（值为 "__any__" 表示不限） */
export interface ElicitOption {
  label: string
  value: string
}

/** 追问面板里的一个维度（如"预算"），渲染成一行可点选项 */
export interface ElicitGroup {
  field: string
  label: string
  question: string
  options: ElicitOption[]
}

/** 引导式追问：把所有缺失维度一次性摆成多组面板，可跨维度多选后统一发送 */
export interface AgentElicit {
  groups: ElicitGroup[]
  allow_custom: boolean
}

/** 消息反馈：点赞 / 点踩 / 未表态 */
export type MessageFeedback = 'up' | 'down' | null

/** 历史消息（切换会话时回放） */
export interface AgentHistoryMessage {
  id: number | null
  role: 'user' | 'assistant'
  content: string
  recommendations: AgentRecommendation[]
  elicit: AgentElicit | null
  feedback: MessageFeedback
  /** assistant 消息的意图，决定气泡样式（如 FAQ 卡片） */
  intent: AgentIntent | null
  created_at: string
}

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

export interface AgentMessageResponse {
  /** 本轮 AI 回复的消息 id，用于点赞/点踩 */
  message_id: number | null
  reply: string
  intent: AgentIntent
  recommendations: AgentRecommendation[]
  cart_changed: boolean
  ai_available: boolean
  quick_replies: string[]
  links: AgentLink[]
  /** intent=elicit 时的追问面板 */
  elicit: AgentElicit | null
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
  /** 后端消息 id；本地生成的欢迎语等没有 id，不能点赞/点踩 */
  id?: number | null
  role: 'user' | 'assistant'
  content: string
  /** 该条 AI 消息附带的推荐房源，内联渲染成横条 */
  recommendations?: AgentRecommendation[]
  /** 该轮是否有 AI 分析（用于横条上的降级提示） */
  aiAvailable?: boolean
  /** 后续建议 chips（点击即作为消息发送） */
  quickReplies?: string[]
  /** 站内页面深链按钮 */
  links?: AgentLink[]
  /** 引导追问的面板（渲染成输入框上方的多组可点选项） */
  elicit?: AgentElicit | null
  /** 用户对这条 AI 回复的点赞/点踩 */
  feedback?: MessageFeedback
  /** 这条 AI 消息的意图，决定气泡样式（如 FAQ 卡片） */
  intent?: AgentIntent | null
  /** 仅本地欢迎语消息为 true：下方渲染一排功能入口卡片 */
  isWelcome?: boolean
}
