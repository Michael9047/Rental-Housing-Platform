/** 对比 Agent 类型定义 */

export type ComparePriority = 'balanced' | 'budget' | 'commute' | 'space' | 'safety'

export interface CompareSessionCreate {
  property_ids: number[]
  priority?: ComparePriority
}

export interface CompareSessionResponse {
  id: number
  user_id: number
  property_ids: number[]
  priority: ComparePriority
  status: 'active' | 'completed'
  result_cache: CompareResultCache | null
  created_at: string
  messages: CompareMessage[]
}

export interface CompareResultCache {
  scores: Record<number, DimensionScores>
  property_data: Record<number, EnrichedPropertyData>
  reply: string
}

export interface CompareMessage {
  id: number
  role: 'user' | 'assistant' | 'tool'
  content: string | null
  tool_calls: Record<string, unknown> | null
  created_at: string
}

export interface CompareMessageRequest {
  message: string
  priority?: ComparePriority | null
}

export interface CompareMessageResponse {
  reply: string
  scores: Record<number, DimensionScores>
  tool_trail: ToolCallRecord[]
  property_data: Record<number, EnrichedPropertyData>
}

export interface DimensionScores {
  total: number
  breakdown: Record<string, number>
}

export interface EnrichedPropertyData {
  property_id: number
  title: string
  district: string
  price_monthly: number
  area_sqm: number | null
  bedrooms: number
  bathrooms: number
  property_type: string
  amenities: string[]
  deposit_amount: number | null
  deposit_type: string | null
  service_fee_rate: number | null
  min_lease_months: number
  floor: number | null
  image_count: number
  transit_display: string | null
  rating: number | null
  review_count: number
  safety_score: number | null
}

export interface ToolCallRecord {
  tool: string
  arguments: Record<string, unknown>
  result: string
}
