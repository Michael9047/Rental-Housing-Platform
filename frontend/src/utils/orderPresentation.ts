// 订单展示层时间计算工具。
export function remainingPaymentSeconds(expiresAt: string, now = Date.now()): number {
  const expiresAtMs = Date.parse(expiresAt)
  if (!Number.isFinite(expiresAtMs)) return 0
  return Math.max(0, Math.floor((expiresAtMs - now) / 1000))
}
