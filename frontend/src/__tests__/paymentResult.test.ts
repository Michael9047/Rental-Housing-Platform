// 支付结果状态映射测试。
import { describe, expect, it } from 'vitest'
import { paymentResultKind } from '@/utils/paymentResult'

describe('paymentResultKind', () => {
  it('支付后进入等待 BM 确认，而不是预订成功', () => {
    expect(paymentResultKind('paid')).toBe('awaiting_confirmation')
    expect(paymentResultKind({ order_status: 'paid', paid_at: '2026-08-12T10:00:00Z' } as never)).toBe('awaiting_confirmation')
  })

  it('房号确认后等待租客签署合同', () => {
    expect(paymentResultKind('contract_ready')).toBe('awaiting_signature')
  })

  it('只有合同签署后才显示预订成功', () => {
    expect(paymentResultKind('contract_signed')).toBe('success')
    expect(paymentResultKind('completed')).toBe('success')
  })
})
