// BM 订单详情状态文案：保留后端原始流程状态，避免将进行中订单误判为已取消。
export interface AdminOrderStatusPresentation {
  label: string
  description: string
  type: 'success' | 'warning' | 'danger' | 'info' | 'primary'
  step: number
}

const STATUS_PRESENTATION: Record<string, AdminOrderStatusPresentation> = {
  payment_pending: { label: '等待支付', description: '订单已创建，等待租客完成支付。', type: 'warning', step: 1 },
  payment_processing: { label: '支付处理中', description: '支付结果正在确认，请勿重复操作。', type: 'warning', step: 1 },
  payment_failed: { label: '支付失败', description: '本次支付未完成，租客可在有效期内重试。', type: 'danger', step: 1 },
  paid: { label: '已支付 · 待确认房号', description: '预订金已到账，等待 BM 确认实际房号并生成合同。', type: 'primary', step: 2 },
  contract_ready: { label: '合同待签署', description: '房号已确认，合同已经生成并等待租客签署。', type: 'warning', step: 3 },
  contract_signed: { label: '已生效', description: '预订金、房号和合同均已确认，当前租约正在生效。', type: 'success', step: 4 },
  completed: { label: '已完成', description: '该订单已经完成全部流程。', type: 'success', step: 4 },
  cancelled: { label: '已取消', description: '该订单已经取消。', type: 'info', step: 0 },
  rejected: { label: '未通过', description: '该订单未通过审核。', type: 'danger', step: 0 },
  payment_expired: { label: '支付已过期', description: '订单未在支付期限内完成付款。', type: 'info', step: 0 },
  refund_pending: { label: '退款处理中', description: '退款申请正在处理。', type: 'warning', step: 0 },
  refunded: { label: '已退款', description: '该订单款项已退回。', type: 'info', step: 0 },
  payment_review: { label: '支付待核验', description: '支付结果需要人工核验。', type: 'warning', step: 1 },
}

export function adminOrderStatusPresentation(status: string): AdminOrderStatusPresentation {
  return STATUS_PRESENTATION[status] || {
    label: status || '状态未知',
    description: '订单状态正在同步，请稍后刷新。',
    type: 'info',
    step: 0,
  }
}
