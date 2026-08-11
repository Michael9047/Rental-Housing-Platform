// Agent 筛选同步工具：把普通空值与显式清除协议严格分开。
import type { AgentFilterField, AgentFilters } from '@/types/agent'

export const AGENT_FILTER_FIELDS = [
  'country',
  'currency',
  'city',
  'district',
  'institute_id',
  'institution',
  'price_min',
  'price_max',
  'bedrooms',
  'bathrooms',
  'property_type',
  'room_type',
  'amenities',
  'area_min',
  'area_max',
  'min_lease_months',
  'max_lease_months',
  'available_from',
  'female_only',
  'commute_mode',
  'commute_minutes',
  'poi_requirements',
] as const satisfies readonly AgentFilterField[]

function hasValue(value: unknown): boolean {
  return value !== null
    && value !== undefined
    && value !== ''
    && (!Array.isArray(value) || value.length > 0)
}

function cloneValue<T>(value: T): T {
  return Array.isArray(value) ? [...value] as T : value
}

/** 仅保留当前真实生效的条件；空值不会被编码成清除。 */
export function compactAgentFilters(source: Partial<Record<AgentFilterField, unknown>>): AgentFilters {
  const compacted: Partial<Record<AgentFilterField, unknown>> = {}
  for (const field of AGENT_FILTER_FIELDS) {
    const value = source[field]
    if (hasValue(value)) compacted[field] = cloneValue(value)
  }
  return compacted as AgentFilters
}

/**
 * 对比上一次已提交快照与当前搜索栏，生成独立 clear_fields。
 * 只有用户界面中真实发生的“有值 → 无值”才会进入该列表。
 */
export function deriveClearedFilterFields(
  previous: AgentFilters,
  current: AgentFilters,
): AgentFilterField[] {
  const previousValues = compactAgentFilters(previous)
  const currentValues = compactAgentFilters(current)
  return AGENT_FILTER_FIELDS.filter((field) => (
    hasValue(previousValues[field]) && !hasValue(currentValues[field])
  ))
}

/** 按服务端回包更新已提交快照，防止下一轮重复上报相同清除。 */
export function mergeAgentFilterSnapshot(
  base: AgentFilters,
  patch: Record<string, unknown> | null | undefined,
  clearedFields: readonly AgentFilterField[] = [],
): AgentFilters {
  const merged = compactAgentFilters(base) as Record<string, unknown>
  for (const field of clearedFields) delete merged[field]
  for (const field of AGENT_FILTER_FIELDS) {
    const value = patch?.[field]
    if (hasValue(value)) merged[field] = cloneValue(value)
  }
  return compactAgentFilters(merged)
}
