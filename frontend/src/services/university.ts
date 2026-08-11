// 大学搜索服务：统一处理热门列表与名称自动补全请求。
import api from './api'

export interface UniversityOption {
  id: number
  name: string
  name_cn?: string | null
  abbreviation?: string | null
  city?: string | null
  country?: string | null
  latitude?: number | null
  longitude?: number | null
}

export const universityService = {
  search(query = '', limit = 20): Promise<UniversityOption[]> {
    const q = query.trim()
    return api.get<UniversityOption[]>('/universities', {
      params: { ...(q ? { q } : {}), limit },
    }).then((response) => response.data || [])
  },
}
