// AI 搜房 API 服务
import api from './api'
import type { PropertySearchResult } from '@/types/property'

/** 解析阶段：缺失字段信息 */
export interface MissingField {
  field: string
  label: string
  hint: string
}

/** 解析阶段：完整性报告 */
export interface CompletenessReport {
  is_complete: boolean
  missing_fields: MissingField[]
  summary: string
}

/** 解析阶段：提取的搜索参数 */
export interface ParsedSearchParams {
  district: string | null
  price_min: number | null
  price_max: number | null
  bedrooms: number | null
  property_type: string | null
  keywords: string | null
}

/** 解析阶段：完整响应 */
export interface ParseResponse {
  params: ParsedSearchParams
  completeness: CompletenessReport
}

/** 搜索阶段：请求参数 */
export interface AiSearchRequest {
  query: string
  district?: string | null
  price_min?: number | null
  price_max?: number | null
  bedrooms?: number | null
  property_type?: string | null
  keywords?: string | null
  limit?: number
}

/** 搜索阶段：完整响应 */
export interface AiSearchResponse {
  summary: string
  top_ids: number[]
  results: PropertySearchResult[]
  total_count: number
  search_params: AiSearchRequest
}

export const aiSearchService = {
  /** 第一步：解析自然语言描述 */
  parse(query: string): Promise<ParseResponse> {
    return api.post('/ai-search/parse', { query }).then((r) => r.data)
  },

  /** 第二步：执行检索 + 生成摘要 */
  search(params: AiSearchRequest): Promise<AiSearchResponse> {
    return api.post('/ai-search/search', params).then((r) => r.data)
  },
}