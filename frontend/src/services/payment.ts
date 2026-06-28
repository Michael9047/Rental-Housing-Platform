import api from './api'

export interface PaymentResponse {
  id: string
  booking_id: number
  user_id: number
  amount: number
  out_trade_no: string | null
  prepay_id: string | null
  transaction_id: string | null
  status: string
  payment_method: string
  trade_state: string | null
  trade_state_desc: string | null
  paid_at: string | null
  created_at: string
  updated_at: string
}

export interface PaymentCreate {
  booking_id: number
  amount: number
}

export const paymentService = {
  createPayment(data: PaymentCreate): Promise<PaymentResponse> {
    return api.post('/payments/create', data).then((r) => r.data)
  },

  getPayment(paymentId: string): Promise<PaymentResponse> {
    return api.get(`/payments/${paymentId}`).then((r) => r.data)
  },

  paymentCallback(paymentId: string): Promise<PaymentResponse> {
    return api.post(`/payments/${paymentId}/callback`).then((r) => r.data)
  },
}
