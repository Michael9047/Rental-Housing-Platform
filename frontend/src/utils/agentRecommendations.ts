// Agent 房源结果整理：按真实房源 ID 和规范化名称去重，保证推荐与对比列表清晰稳定。
import type { AgentRecommendation } from '@/types/agent'

/** 忽略大小写、空白和常见分隔符后得到可比较的房源名称。 */
export function normalizePropertyTitle(value: unknown): string {
  return String(value || '')
    .normalize('NFKC')
    .trim()
    .toLocaleLowerCase()
    .replace(/[\s·•—–_-]+/g, '')
}

/**
 * 推荐列表去重规则：同一房源 ID 只保留一次，完全同名的重复记录也只展示一次。
 */
export function uniqueAgentRecommendations(
  recommendations: AgentRecommendation[] | null | undefined,
): AgentRecommendation[] {
  const result: AgentRecommendation[] = []
  const seenIds = new Set<number>()
  const seenTitles = new Set<string>()

  for (const recommendation of recommendations || []) {
    const propertyId = Number(recommendation.property_id)
    const titleKey = normalizePropertyTitle(recommendation.property?.title)
    if (!Number.isInteger(propertyId) || propertyId <= 0 || seenIds.has(propertyId)) continue
    if (titleKey && seenTitles.has(titleKey)) continue
    seenIds.add(propertyId)
    if (titleKey) seenTitles.add(titleKey)
    result.push(recommendation)
  }

  return result
}

/** 普通搜索结果使用相同规则，避免左侧结果和 Agent 候选数量不一致。 */
export function uniquePropertiesByIdAndTitle<T extends { id: number; title?: string | null }>(
  properties: T[],
): T[] {
  const result: T[] = []
  const seenIds = new Set<number>()
  const seenTitles = new Set<string>()

  for (const property of properties) {
    const propertyId = Number(property.id)
    const titleKey = normalizePropertyTitle(property.title)
    if (!Number.isInteger(propertyId) || propertyId <= 0 || seenIds.has(propertyId)) continue
    if (titleKey && seenTitles.has(titleKey)) continue
    seenIds.add(propertyId)
    if (titleKey) seenTitles.add(titleKey)
    result.push(property)
  }

  return result
}
