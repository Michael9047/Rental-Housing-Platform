// 支付 API：金额和汇率只读取服务端支付快照。
import api from './api'

export interface Money { currency: string; minor_units: number; minor_unit_exponent: number; decimal: string }
export interface PaymentResponse {
  id: string; order_id: string; payment_attempt_id: string; booking_id: number; user_id: number; status: string; order_status: string | null; provider: string
  payment_method: string; settlement_currency: string; settlement_amount_minor: number
  cny_reference_amount_minor: number; property_currency: string; exchange_rate: string
  exchange_rate_source: string; exchange_rate_timestamp: string; expires_at: string
  checkout_url: string | null; transaction_id: string | null; paid_at: string | null
  snapshot: { order_number: string; property_id: number; property_name: string; property_address: string
    commencement_date: string; expiry_date: string; tenancy_months: number; tenant_name: string
    agreement_id: string; agreement_number: string; fees: { deposit: Money; service_fee: Money; tax: Money; current_total: Money } }
}
export interface PaymentResult extends PaymentResponse { property_image_url: string | null; booking_created_at: string; status_updated_at: string; failure_reason: string | null }
export type PaymentMethod = 'WECHAT_PAY' | 'ALIPAY' | 'CARD_CHECKOUT'
export interface PaymentMethodAvailability { method: PaymentMethod; available: boolean; test_mode: boolean; reason: string | null }
export interface TenantOrderItem {
  booking_id:number; order_id:string; agreement_id:string; agreement_number:string; property_id:number
  property_name:string; property_image_url:string|null; property_city:string; property_address:string
  lease_start_date:string|null; lease_end_date:string|null; lease_months:number|null
  settlement_currency:string; settlement_amount_minor:number; cny_reference_amount_minor:number
  property_currency:string; property_amount_minor:number; order_status:string; payment_status:string
  booking_status:string; status_label:string; created_at:string; expires_at:string
  remaining_payment_seconds:number; can_pay:boolean; payment_action_label:string|null; failure_reason:string|null
}
export interface TenantOrderDetail extends TenantOrderItem {
  applicant_name:string; applicant_phone_masked:string|null; applicant_email_masked:string|null
  property_type:string; property_country:string; property_description:string|null; monthly_rent_minor:number
  deposit_amount_minor:number; service_fee_amount_minor:number; tax_amount_minor:number
  exchange_rate:string; exchange_rate_source:string; exchange_rate_timestamp:string; status_updated_at:string
  paid_at:string|null; transaction_id_masked:string|null; webhook_confirmed:boolean; amounts_verified:boolean; inventory_reserved:boolean
}
export interface PaymentEligibility { booking_id:number; can_pay:boolean; order_status:string; payment_status:string; expires_at:string; reason:string|null; payment_id:string|null }

export const paymentService = {
  listMyOrders():Promise<TenantOrderItem[]> { return api.get('/payments/orders/my').then(r=>r.data.items) },
  getMyOrder(bookingId:number):Promise<TenantOrderDetail> { return api.get(`/payments/orders/my/${bookingId}`).then(r=>r.data) },
  validatePayment(bookingId:number):Promise<PaymentEligibility> { return api.post(`/payments/orders/my/${bookingId}/validate-payment`).then(r=>r.data) },
  createPayment(bookingId: number, idempotencyKey: string, paymentMethod: PaymentMethod = 'CARD_CHECKOUT'): Promise<PaymentResponse> {
    return api.post('/payments/create', { booking_id: bookingId, payment_method: paymentMethod }, { headers: { 'Idempotency-Key': idempotencyKey } }).then(r => r.data)
  },
  getAvailableMethods(): Promise<PaymentMethodAvailability[]> { return api.get('/payments/methods/availability').then(r => r.data) },
  getPayment(id: string): Promise<PaymentResponse> { return api.get(`/payments/${id}`).then(r => r.data) },
  getByBooking(id: number): Promise<PaymentResponse> { return api.get(`/payments/by-booking/${id}`).then(r => r.data) },
  getResult(id: number): Promise<PaymentResult> { return api.get(`/payments/result/by-booking/${id}`).then(r => r.data) },
}
