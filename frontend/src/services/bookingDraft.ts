/** 预订流程草稿服务 —— 对应后端 /bookings/drafts/{unit_type_id} */
import api from './api'

export interface BookingDraft {
  id: number
  user_id: number
  unit_type_id: number
  current_step: string
  move_in_date: string | null
  lease_months: number | null
  personal_info: Record<string, any> | null
  emergency_contact: Record<string, any> | null
  created_at: string
  updated_at: string
}

export interface BookingDraftSavePayload {
  move_in_date?: string
  lease_months?: number
  current_step?: string
  personal_info?: Record<string, any>
  emergency_contact?: Record<string, any>
}

export const bookingDraftService = {
  /** 获取服务端草稿。 */
  get(propertyId: number, silent = false): Promise<BookingDraft> {
    return api.get(`/bookings/drafts/${propertyId}`, { suppressGlobalError: silent } as any).then((r) => r.data)
  },

  /** 保存（创建或更新）服务端草稿。 */
  save(propertyId: number, data: BookingDraftSavePayload): Promise<BookingDraft> {
    return api.put(`/bookings/drafts/${propertyId}`, data).then((r) => r.data)
  },
}
