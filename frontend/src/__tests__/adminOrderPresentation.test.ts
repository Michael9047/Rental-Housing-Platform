// BM 订单状态展示测试，防止进行中订单再次被错误标记为已取消。
import { describe, expect, it } from 'vitest'
import { adminOrderStatusPresentation } from '@/utils/adminOrderPresentation'

describe('adminOrderStatusPresentation', () => {
  it('将已签署合同展示为已生效', () => {
    expect(adminOrderStatusPresentation('contract_signed')).toMatchObject({
      label: '已生效',
      type: 'success',
      step: 4,
    })
  })

  it('不会把其他进行中状态展示为已取消', () => {
    for (const status of ['payment_pending', 'payment_processing', 'paid', 'contract_ready']) {
      expect(adminOrderStatusPresentation(status).label).not.toBe('已取消')
    }
  })

  it('只将 cancelled 映射为已取消', () => {
    expect(adminOrderStatusPresentation('cancelled').label).toBe('已取消')
  })
})
