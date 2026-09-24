import { describe, expect, it } from 'vitest'
import {
  compactAgentFilters,
  deriveClearedFilterFields,
  mergeAgentFilterSnapshot,
} from '@/utils/agentFilterSync'

describe('Agent 筛选清除协议', () => {
  it('普通 null 只从上下文省略，不会伪造清除值', () => {
    expect(compactAgentFilters({
      city: 'London',
      district: null,
      price_max: null,
      amenities: [],
    })).toEqual({ city: 'London' })
  })

  it('只把搜索栏真实发生的有值到无值变化编码为 clear_fields', () => {
    expect(deriveClearedFilterFields(
      { district: 'Camden', price_max: 1800, property_type: 'studio' },
      { district: null, price_max: 1800, property_type: undefined },
    )).toEqual(['district', 'property_type'])
  })

  it('按 cleared_filters 删除快照并合并服务端确认的新条件', () => {
    expect(mergeAgentFilterSnapshot(
      { district: 'Camden', price_max: 1800, property_type: 'studio' },
      { city: 'London', price_max: 2000, district: null },
      ['district', 'property_type'],
    )).toEqual({ city: 'London', price_max: 2000 })
  })
})
