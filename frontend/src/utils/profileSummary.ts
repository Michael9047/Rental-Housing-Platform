// 个人中心预约摘要筛选工具。
import type { Booking } from '@/types/booking'
import type { TenantOrderItem } from '@/services/payment'

export function filterViewingAppointments(
  bookings: Booking[],
  orders: TenantOrderItem[],
): Booking[] {
  const convertedBookingIds = new Set(orders.map((order) => order.booking_id))
  return bookings.filter((booking) => (
    !convertedBookingIds.has(booking.id)
    && ['pending', 'approved', 'rejected', 'cancelled', 'completed'].includes(booking.status)
  ))
}
