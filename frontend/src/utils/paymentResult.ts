// 支付结果页状态归类工具。
export type PaymentResultKind = 'success' | 'pending' | 'cancelled'

const SUCCESS_STATUSES = new Set(['paid', 'payment_succeeded', 'confirmed'])
const CANCELLED_STATUSES = new Set(['cancelled', 'payment_expired', 'expired', 'refunded'])
const RETRYABLE_STATUSES = new Set(['payment_pending', 'payment_failed', 'pending'])

export function paymentResultKind(status: string): PaymentResultKind {
  if (SUCCESS_STATUSES.has(status)) return 'success'
  if (CANCELLED_STATUSES.has(status)) return 'cancelled'
  return 'pending'
}

export function canRetryPayment(status: string, expiresAt: string, now = Date.now()): boolean {
  const expiresAtMs = Date.parse(expiresAt)
  return RETRYABLE_STATUSES.has(status) && Number.isFinite(expiresAtMs) && expiresAtMs > now
}
