import api from './api'

export interface Contract {
  id: string
  booking_id: number
  tenant_id: number
  property_id: number
  template_name: string
  agreement_number: string | null
  version: number
  template_version: string
  content_hash: string | null
  snapshot: ContractSnapshot | null
  generated_at: string | null
  content: string
  status: string
  signed_at: string | null
  file_path: string | null
  created_at: string
  updated_at: string
}

export interface ContractSection { number: number; title_zh: string; title_en: string; zh: string; en: string }
export interface ContractSnapshot {
  [key: string]: unknown
  sections: ContractSection[]
  agreement_number: string
  agreement_version: number
  content_hash: string
}
export interface SignaturePoint { x: number; y: number; pressure: number }
export interface ContractSignatureRecord { agreement_id: string; agreement_version: number; agreement_content_hash: string; tenant_user_id: number; tenant_name: string; signed_at: string; property_timezone: string; consent_text_version: string; signature_hash: string; pdf_status: 'pending' | 'ready' | 'failed' }
export type ContractCategory = 'pending_effective' | 'effective' | 'expiring_soon' | 'invalid'
export interface TenantContractItem {
  agreement_id:string; agreement_number:string; agreement_version:number; agreement_content_hash:string
  order_id:string; booking_id:number; property_id:number; tenant_user_id:number; signed_at:string
  lease_start_date:string|null; lease_end_date:string|null; lease_months:number|null; property_timezone:string
  property_name:string; property_address:string; property_image_url:string|null
  payment_status:string; booking_status:string; reservation_status:string; agreement_status:string
  category:ContractCategory; category_label:string; status_labels:string[]; invalid_reason:string|null
  settlement_currency:string|null; settlement_amount_minor:number|null; payment_expires_at:string|null
  remaining_payment_seconds:number|null; remaining_contract_days:number|null; can_pay:boolean
  waiting_for_move_in:boolean; signed_pdf_available:boolean
}
export interface TenantContractDetail extends TenantContractItem { content:string; snapshot:ContractSnapshot; signature_url:string }

export const contractService = {
  listMine(): Promise<TenantContractItem[]> { return api.get('/contracts/my').then(r=>r.data.items) },
  getMine(contractId:string): Promise<TenantContractDetail> { return api.get(`/contracts/my/${contractId}`).then(r=>r.data) },
  getSignature(contractId:string): Promise<Blob> { return api.get(`/contracts/my/${contractId}/signature`, { responseType: 'blob' }).then(r=>r.data) },
  getSignedDownloadLink(contractId:string): Promise<{url?:string;expires_at?:string;code?:string;message?:string}> { return api.get(`/contracts/my/${contractId}/signed-download-link`).then(r=>r.data) },
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

  confirmSignature(contractId: string, data: { agreement_version: number; agreement_content_hash: string; tenant_name: string; consent_text_version: string; idempotency_key: string; strokes: SignaturePoint[][]; name_confirmed: boolean; electronic_signature_consent: boolean }): Promise<ContractSignatureRecord> {
    return api.post(`/contracts/${contractId}/sign`, data).then((r) => r.data)
  },

  download(contractId: string): Promise<Blob> {
    return api.get(`/contracts/${contractId}/download`, { responseType: 'blob' }).then((r) => r.data)
  },
}
