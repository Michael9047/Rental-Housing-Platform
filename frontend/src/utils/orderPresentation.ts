// Stub — PR #30 合入后替换为完整实现
export function remainingPaymentSeconds(expiresAt: string, now: Date | number): number {
  if (!expiresAt) return 0
  const nowMs = typeof now === 'number' ? now : now.getTime()
  const remaining = (new Date(expiresAt).getTime() - nowMs) / 1000
  return Math.max(0, Math.floor(remaining))
}
export function formatOrderStatus(status: string): string { return status }

// 预订状态只看预订流程本身（是否已批准/推进），与支付 webhook 是否确认无关。
// booking_status（如 confirmed/not_confirmed）依赖支付全链路确认，不适合作为「预订成功」的判定。
const RESERVATION_FAILED = new Set(['rejected', 'cancelled', 'payment_expired'])
export function reservationLabel(status: string): string {
  if (!status) return '未知'
  if (status === 'pending') return '待确认'
  if (RESERVATION_FAILED.has(status)) return '预订未成功'
  return '预订成功'
}
