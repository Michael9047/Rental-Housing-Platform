export type BookingStatus = 'pending' | 'approved' | 'rejected' | 'cancelled' | 'completed'

export interface Booking {
  id: number
  tenant_id: number
  property_id: number
  landlord_id: number
  status: BookingStatus
  message: string | null
  scheduled_date: string | null
  created_at: string
  updated_at: string
}

export interface BookingCreate {
  property_id: number
  message?: string
  scheduled_date?: string
}

export type NotificationType = 'booking_created' | 'booking_approved' | 'booking_rejected' | 'booking_cancelled'

export interface Notification {
  id: number
  user_id: number
  type: NotificationType
  title: string
  content: string | null
  is_read: boolean
  created_at: string
  updated_at: string
}

export interface UnreadCount {
  count: number
}
