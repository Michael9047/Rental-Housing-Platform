// Stub — PR #30 合入后替换为完整实现
export function remainingPaymentSeconds(expiresAt: string, now: Date | number): number {
  if (!expiresAt) return 0
  const nowMs = typeof now === 'number' ? now : now.getTime()
  const remaining = (new Date(expiresAt).getTime() - nowMs) / 1000
  return Math.max(0, Math.floor(remaining))
}
export function formatOrderStatus(status: string): string { return status }
