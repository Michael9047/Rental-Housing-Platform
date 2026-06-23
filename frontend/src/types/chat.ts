export interface ChatSession {
  id: number
  session_id: string
  title: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: number
  session_id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  metadata?: {
    matched_properties?: MatchedProperty[]
    search_params?: Record<string, unknown>
  }
  created_at: string
}

export interface MatchedProperty {
  id: number
  title: string
  district: string
  address: string
  price_monthly: number
  bedrooms: number
  bathrooms: number
  area_sqm: number | null
  property_type: string
  similarity: number | null
}

export interface SSEEvent {
  type: 'matched' | 'content' | 'done' | 'error'
  properties?: MatchedProperty[]
  content?: string
  error?: string
}
