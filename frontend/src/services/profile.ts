// Stub — PR #30 合入后替换
import api from './api'

export interface DashboardSummary {
  pending_viewings: number
  pending_payments: number
  signed_contracts: number
  favorites: number
}

export const profileService = {
  getSummary: () => api.get('/me/dashboard-summary').then(r => r.data),
  getOrders: () => api.get('/me/orders').then(r => r.data),
  getContracts: () => api.get('/me/contracts').then(r => r.data),
}
