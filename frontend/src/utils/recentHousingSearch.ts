// 最近房源搜索上下文：为首页推荐保存最少的位置数据。
export const RECENT_HOUSING_SEARCH_KEY = 'recent_housing_search_context'

export interface RecentHousingSearchContext {
  kind: 'school' | 'district' | 'city'
  schoolId?: number
  schoolName?: string
  latitude?: number
  longitude?: number
  radiusKm?: number
  city?: string
  district?: string
  country?: string
  savedAt: number
}

export type RecommendationQuery = Record<string, string | number>

function cleanText(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined
}

export function saveRecentHousingSearch(context: Omit<RecentHousingSearchContext, 'savedAt'>): void {
  try {
    localStorage.setItem(RECENT_HOUSING_SEARCH_KEY, JSON.stringify({
      ...context,
      schoolName: cleanText(context.schoolName),
      city: cleanText(context.city),
      district: cleanText(context.district),
      country: cleanText(context.country),
      savedAt: Date.now(),
    }))
  } catch {
    // 浏览器禁用本地存储时不影响正常搜索。
  }
}

export function loadRecentHousingSearch(): RecentHousingSearchContext | null {
  try {
    const raw = localStorage.getItem(RECENT_HOUSING_SEARCH_KEY)
    if (!raw) return null
    const value = JSON.parse(raw) as Partial<RecentHousingSearchContext>
    if (value.kind !== 'school' && value.kind !== 'district' && value.kind !== 'city') return null
    const city = cleanText(value.city)
    const district = cleanText(value.district)
    const hasCoordinates = Number.isFinite(value.latitude) && Number.isFinite(value.longitude)
    if (value.kind === 'school' && !hasCoordinates && !city) return null
    if (value.kind === 'city' && !city) return null
    if (value.kind === 'district' && !district) return null
    return {
      ...value,
      kind: value.kind,
      city,
      district,
      schoolName: cleanText(value.schoolName),
      country: cleanText(value.country),
      savedAt: typeof value.savedAt === 'number' ? value.savedAt : 0,
    }
  } catch {
    return null
  }
}

/** 生成“学校附近 → 城市 → 默认”的推荐降级查询。 */
export function buildRecommendationQueries(
  context: RecentHousingSearchContext | null,
  limit = 18,
): RecommendationQuery[] {
  const queries: RecommendationQuery[] = []
  if (
    context?.kind === 'school'
    && Number.isFinite(context.latitude)
    && Number.isFinite(context.longitude)
  ) {
    queries.push({
      near_lat: context.latitude as number,
      near_lng: context.longitude as number,
      near_distance_km: context.radiusKm || 5,
      limit,
    })
  }
  if (context?.kind === 'district' && context.district) {
    queries.push({
      district: context.district,
      ...(context.country ? { country: context.country } : {}),
      limit,
    })
  }
  if (context?.city) {
    queries.push({
      city: context.city,
      ...(context.country ? { country: context.country } : {}),
      limit,
    })
  }
  queries.push({ limit })
  return queries
}
