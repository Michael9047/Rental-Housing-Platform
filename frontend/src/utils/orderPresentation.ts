/** 订单展示工具 — 兼容占位（Order 表已删除） */

/** 计算支付剩余秒数 */
export function remainingPaymentSeconds(payment: any): number {
  if (!payment?.payment_expires_at) return 0
  const diff = new Date(payment.payment_expires_at).getTime() - Date.now()
  return Math.max(0, Math.floor(diff / 1000))
}

/** 支付结果文本映射 */
export const PAYMENT_RESULT_MESSAGES: Record<string, string> = {
  success: '支付成功',
  failed: '支付失败',
  expired: '支付已过期',
  pending: '处理中',
}
