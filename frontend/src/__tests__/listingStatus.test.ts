// 生命周期状态展示规则测试。
import { describe, expect, it } from 'vitest'
import { listingPrimaryAction, listingStatusLabel, parentVisibilityHint } from '@/utils/listingStatus'

describe('listingStatus', () => {
  it('maps status labels and primary actions', () => {
    expect(listingStatusLabel('building', 'offline')).toBe('已下架')
    expect(listingStatusLabel('unitType', 'available')).toBe('可租')
    expect(listingPrimaryAction('active')).toBe('offline')
    expect(listingPrimaryAction('offline')).toBe('publish')
  })

  it('explains parent masking without changing child status', () => {
    expect(parentVisibilityHint('offline')).toBe('公寓已下架，前台不可见')
    expect(parentVisibilityHint('active')).toBe('')
  })
})
