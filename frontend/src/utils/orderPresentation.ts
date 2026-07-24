// Stub — PR #30 合入后替换为完整实现
export function remainingPaymentSeconds(expiresAt: string, now: Date): number {
  if (!expiresAt) return 0
  const remaining = (new Date(expiresAt).getTime() - now.getTime()) / 1000
  return Math.max(0, Math.floor(remaining))
}
export function formatOrderStatus(status: string): string { return status }
