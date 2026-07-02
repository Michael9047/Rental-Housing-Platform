import api from './api'

export interface Contract {
  id: string
  booking_id: number
  tenant_id: number
  property_id: number
  template_name: string
  content: string
  status: string
  signed_at: string | null
  file_path: string | null
  created_at: string
  updated_at: string
}

export const contractService = {
  generate(bookingId: number): Promise<Contract> {
    return api.post(`/contracts/${bookingId}/generate`).then((r) => r.data)
  },

  get(contractId: string): Promise<Contract> {
    return api.get(`/contracts/${contractId}`).then((r) => r.data)
  },

  getByBooking(bookingId: number): Promise<Contract> {
    return api.get(`/contracts/by-booking/${bookingId}`).then((r) => r.data)
  },

  getByBookingOptional(bookingId: number): Promise<Contract | null> {
    return api
      .get(`/contracts/by-booking/${bookingId}`, { validateStatus: (status) => status === 200 || status === 404 })
      .then((r) => (r.status === 404 ? null : r.data))
  },

  sign(contractId: string): Promise<Contract> {
    return api.post(`/contracts/${contractId}/sign`).then((r) => r.data)
  },

  download(contractId: string): Promise<string> {
    return api.get(`/contracts/${contractId}/download`).then((r) => r.data)
  },
}
