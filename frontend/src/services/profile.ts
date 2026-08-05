// 个人中心统计摘要接口。
import api from './api'

export interface DashboardSummary {
  viewing_appointments: number
  payable_orders: number
  signed_contracts: number
  favorites: number
}

export const profileService = {
  getSummary(): Promise<DashboardSummary> {
    return api.get('/me/dashboard-summary').then((response) => response.data)
  },
}
