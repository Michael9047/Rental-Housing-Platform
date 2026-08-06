/** 政策/协议服务 —— 获取政策文档、提交预订确认。 */
import api from './api'

export interface PolicyDocument {
  key: string
  title: string
  version: number
  content: string
  content_hash: string
}

export interface PolicyAcceptanceItem {
  key: string
  version: number
  content_hash: string
}

export interface BookingConfirmationResult {
  booking_id: number
  consent_count: number
  order_status: string
}

export const policyService = {
  /** 获取单个政策文档正文。 */
  get(key: string): Promise<PolicyDocument> {
    return api.get(`/bookings/policies/${key}`, { suppressGlobalError: true } as any).then((r) => r.data)
  },

  /** 确认预订并提交政策同意记录。 */
  confirmBooking(data: {
    unit_type_id: number
    move_in_date: string
    lease_months: number
    policy_acceptances: PolicyAcceptanceItem[]
  }): Promise<BookingConfirmationResult> {
    return api.post('/bookings/confirm', data).then((r) => r.data)
  },
}
