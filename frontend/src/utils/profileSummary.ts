/** 个人中心数据筛选工具 — 兼容占位 */

import type { Booking } from '@/types/booking'

/** 筛选待确认的看房预约 */
export function filterViewingAppointments(bookings: Booking[]): Booking[] {
  if (!Array.isArray(bookings)) return []
  return bookings.filter((b) => b.status === 'pending' || b.status === 'approved')
}
