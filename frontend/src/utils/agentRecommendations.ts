// Agent 推荐结果整理：按 UnitType ID 去重，并避免同一公寓内的重复户型卡片。
import type { AgentRecommendation } from '@/types/agent'

export const AGENT_RECOMMENDATION_DISPLAY_LIMIT = 20

/** 忽略大小写、空白和常见分隔符后生成稳定比较键。 */
export function normalizeRecommendationLabel(value: unknown): string {
  return String(value || '')
    .normalize('NFKC')
    .trim()
    .toLocaleLowerCase()
    .replace(/[\s·•—–_-]+/g, '')
}

function recommendationNameKey(recommendation: AgentRecommendation): string {
  const property = recommendation.property
  if (!property || typeof property !== 'object') return ''
  const institute = normalizeRecommendationLabel(
    property.institute_id || property.institute_name || property.institute_address,
  )
  const unitType = normalizeRecommendationLabel(
    property.name || property.title || property.unit_type_name,
  )
  return institute && unitType ? `${institute}:${unitType}` : ''
}

/**
 * 推荐列表首先按 UnitType ID 去重；名称去重只在同一 Institute 内生效。
 * 不会把不同公寓都叫 “Studio” 的户型错误合并。
 */
export function uniqueAgentRecommendations(
  recommendations: AgentRecommendation[] | null | undefined,
): AgentRecommendation[] {
  const result: AgentRecommendation[] = []
  const seenIds = new Set<number>()
  const seenNames = new Set<string>()

  for (const recommendation of recommendations || []) {
    if (!recommendation || typeof recommendation !== 'object') continue
    const unitTypeId = Number(recommendation.property_id)
    if (
      !Number.isInteger(unitTypeId)
      || unitTypeId <= 0
      || seenIds.has(unitTypeId)
      || !recommendation.property
      || typeof recommendation.property !== 'object'
    ) continue

    const nameKey = recommendationNameKey(recommendation)
    if (nameKey && seenNames.has(nameKey)) continue

    seenIds.add(unitTypeId)
    if (nameKey) seenNames.add(nameKey)
    result.push(recommendation)
  }

  return result
}

/** 每轮最多渲染 20 张卡片；真实总数由 recommendation_total 单独展示。 */
export function visibleAgentRecommendations(
  recommendations: AgentRecommendation[] | null | undefined,
): AgentRecommendation[] {
  return uniqueAgentRecommendations(recommendations)
    .slice(0, AGENT_RECOMMENDATION_DISPLAY_LIMIT)
}

/** 普通搜索结果按自身 ID 去重；名称仅作为同一公寓内的兜底判定。 */
export function uniquePropertiesByIdAndInstitute<T extends {
  id: number
  name?: string | null
  title?: string | null
  institute_id?: number | null
  institute_name?: string | null
}>(properties: T[]): T[] {
  const result: T[] = []
  const seenIds = new Set<number>()
  const seenNames = new Set<string>()

  for (const property of properties) {
    const id = Number(property.id)
    if (!Number.isInteger(id) || id <= 0 || seenIds.has(id)) continue
    const institute = normalizeRecommendationLabel(property.institute_id || property.institute_name)
    const name = normalizeRecommendationLabel(property.name || property.title)
    const nameKey = institute && name ? `${institute}:${name}` : ''
    if (nameKey && seenNames.has(nameKey)) continue
    seenIds.add(id)
    if (nameKey) seenNames.add(nameKey)
    result.push(property)
  }

  return result
}

/** 兼容参考版调用名；实现仍遵守 main 的 Institute + UnitType 去重边界。 */
export const uniquePropertiesByIdAndTitle = uniquePropertiesByIdAndInstitute
