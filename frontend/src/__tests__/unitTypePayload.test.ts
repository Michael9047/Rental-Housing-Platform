// 户型提交载荷校验测试。
import { describe, expect, it } from 'vitest'
import { validateUnitTypePayload } from '@/utils/unitTypePayload'

describe('validateUnitTypePayload', () => {
  it('requires property type', () => {
    expect(validateUnitTypePayload({ total_count: 1, available_count: 1 })).toBe('请选择户型类型')
  })
  it('rejects available inventory above total', () => {
    expect(validateUnitTypePayload({ property_type: 'studio', total_count: 1, available_count: 2 })).toContain('总套数')
  })
})
