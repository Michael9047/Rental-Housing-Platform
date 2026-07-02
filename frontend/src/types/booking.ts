export type BookingStatus = 'pending' | 'approved' | 'rejected' | 'cancelled' | 'completed'

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
  contract_real_name: string | null
  contract_id_card_no: string | null
  contract_phone: string | null
  lease_start_date: string | null
  lease_end_date: string | null
  contract_extra_terms: string | null
  contract_info_status: 'missing' | 'pending_landlord' | 'confirmed' | string
  contract_landlord_confirmed_at: string | null
  created_at: string
  updated_at: string
}

export interface BookingCreate {
  property_id: number
  message?: string
  scheduled_date?: string
}

export interface BookingContractInfoUpdate {
  contract_real_name: string
  contract_id_card_no: string
  contract_phone: string
  lease_start_date: string
  lease_end_date: string
  contract_extra_terms?: string
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
