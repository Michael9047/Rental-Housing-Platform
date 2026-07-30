/** 通知事件类型（新统一事件 + 旧类型兼容） */
export type NotificationEventType =
  // 新统一事件
  | 'contract_signed'
  | 'contract_expiring'
  | 'payment_pending'
  | 'payment_failed'
  | 'payment_processing'
  | 'payment_expiring_in_3_hours'
  | 'payment_succeeded'
  | 'booking_confirmed'
  | 'order_auto_cancelled'
  | 'payment_review'
  | 'refund_pending'
  | 'refunded'
  // 旧类型（向后兼容）
  | 'booking_created'
  | 'booking_approved'
  | 'booking_rejected'
  | 'booking_cancelled'
  | 'booking_completed'
  | 'payment_received'
  | 'payment_created'
  | 'payment_expired'
  | 'contract_generated'
  | 'auth_registration'
  | 'auth_password_reset'
  | 'repair_created'
  | 'repair_assigned'
  | 'repair_completed'
  | 'repair_status_change'
  | 'system'

/** 实体类型 */
export type EntityType = 'order' | 'payment' | 'contract' | 'booking' | 'property' | 'repair' | 'system'

/** 站内通知 */
export interface Notification {
  id: number
  user_id: number
  type: string
  title: string
  content: string | null
  is_read: boolean
  entity_type: EntityType | null
  entity_id: string | null
  order_id: number | null
  agreement_id: string | null
  property_id: number | null
  created_at: string
  updated_at: string
}

/** 未读数量 */
export interface UnreadCount {
  count: number
}

/** 投递记录 */
export interface DeliveryRecord {
  id: number
  user_id: number
  notification_id: number | null
  order_id: number | null
  channel: string
  event_type: string
  template_id: string | null
  recipient_masked: string | null
  idempotency_key: string
  provider_message_id: string | null
  status: string
  attempt_count: number
  queued_at: string | null
  sent_at: string | null
  delivered_at: string | null
  failed_at: string | null
  last_error_code: string | null
  created_at: string
}
