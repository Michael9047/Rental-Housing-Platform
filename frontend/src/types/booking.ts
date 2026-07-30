export type BookingStatus = 'pending' | 'approved' | 'rejected' | 'cancelled' | 'completed' | 'contract_ready' | 'contract_signed' | 'payment_pending'

// Matches backend: app/schemas/booking.py BookingRead
export interface Booking {
  id: number
  tenant_id: number
  property_id: number
  landlord_id: number
  status: BookingStatus
  message: string | null
  scheduled_date: string | null
  deposit_amount: number | null
  service_fee: number | null
  deposit_status: string | null
  payment_transaction_id: string | null
  lease_months: number | null
  total_rent: number | null
  application_data: any | null
  created_at: string
  updated_at: string
}

export interface BookingCreate {
  property_id: number
  message?: string
  scheduled_date?: string
  deposit_amount?: number
  service_fee?: number
  lease_months?: number
  total_rent?: number
  application_data?: any
}

export type NotificationType =
  | 'booking_created' | 'booking_approved' | 'booking_rejected' | 'booking_cancelled' | 'booking_completed'
  | 'payment_created' | 'payment_received' | 'payment_failed' | 'payment_expired'
  | 'contract_generated' | 'contract_signed' | 'system'

export interface Notification {
  id: number
  user_id: number
  type: NotificationType
  title: string
  content: string | null
  body?: string | null
  entity_type?: string | null
  entity_id?: string | null
  order_id?: string | null
  agreement_id?: string | null
  property_id?: number | null
  can_pay?: boolean
  payment_status?: string | null
  order_status?: string | null
  is_read: boolean
  created_at: string
  updated_at: string
}

export interface UnreadCount {
  count: number
}
