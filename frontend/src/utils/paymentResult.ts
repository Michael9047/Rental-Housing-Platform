/**
 * 支付结果工具函数 — 提供给 BookingResult.vue 等支付结果页使用。
 */
import type { PaymentResult } from '@/services/payment'

export type PaymentResultKind = 'success' | 'failed' | 'expired' | 'review' | 'refunded' | 'cancelled' | 'pending' | 'unknown'

/** 支付结果归类 — 可接受 PaymentResult 对象或原始状态字符串 */
export function paymentResultKind(
  result: PaymentResult | null | string
): PaymentResultKind {
  if (!result) return 'unknown'
  const s = typeof result === 'string' ? result : (result.order_status || result.status)
  if (!s) return 'unknown'
  if (s === 'paid' || (typeof result !== 'string' && result.paid_at)) return 'success'
  if (s === 'refunded') return 'refunded'
  if (s === 'cancelled') return 'cancelled'
  if (s === 'payment_expired') return 'expired'
  if (s === 'payment_failed') return 'failed'
  if (s === 'payment_review' || s === 'refund_pending') return 'review'
  if (s === 'payment_pending' || s === 'payment_processing') return 'pending'
  return 'unknown'
}

/** 是否允许重试支付 — 接受状态字符串、过期时间和当前时间 */
export function canRetryPayment(
  statusOrResult: PaymentResult | string | null,
  expiresAt?: string,
  nowMs?: number
): boolean {
  const s = typeof statusOrResult === 'string'
    ? statusOrResult
    : (statusOrResult?.order_status || statusOrResult?.status || '')
  if (s !== 'payment_failed') return false
  if (expiresAt && nowMs) {
    const expires = Date.parse(expiresAt)
    if (expires <= nowMs) return false
  }
  return true
}
