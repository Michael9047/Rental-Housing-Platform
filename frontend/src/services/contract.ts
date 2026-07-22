import api from './api'

export interface ContractPropertySnapshot {
  id?: number
  title?: string
  description?: string | null
  address?: string
  district?: string
  country?: string
  property_type?: string
  price_monthly?: number
  area_sqm?: number | null
  bedrooms?: number
  bathrooms?: number
  floor?: number | null
  room_number?: string | null
  amenities?: string[]
  available_from?: string | null
  min_lease_months?: number
  max_lease_months?: number | null
  rent_type?: string
  deposit_amount?: number | null
  deposit_type?: string | null
  service_fee_rate?: number | null
  property_updated_at?: string | null
  captured_at?: string
  source?: string
}

export interface Contract {
  id: string
  booking_id: number
  tenant_id: number
  property_id: number
  template_name: string
  content: string
  property_snapshot: ContractPropertySnapshot | null
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

  sign(contractId: string): Promise<Contract> {
    return api.post(`/contracts/${contractId}/sign`).then((r) => r.data)
  },

  download(contractId: string): Promise<string> {
    return api.get(`/contracts/${contractId}/download`).then((r) => r.data)
  },
}
