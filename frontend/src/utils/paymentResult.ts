/** 支付结果展示工具 — 兼容占位 */

export function formatPaymentResult(payment: any): string {
  if (!payment) return '未知'
  const status = payment.status || payment.trade_state || ''
  const map: Record<string, string> = {
    success: '支付成功',
    failed: '支付失败',
    expired: '已过期',
    pending: '处理中',
    processing: '处理中',
    closed: '已关闭',
  }
  return map[status] || status || '未知'
}
