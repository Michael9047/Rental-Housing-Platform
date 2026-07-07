/** 数据台 API 客户端 */
import api from './api'

interface LandlordDashboard {
  properties: { total: number; available: number; rented: number; maintenance: number }
  bookings: { pending: number }
  repairs: { pending: number; in_progress: number }
  workers: { total: number; available: number }
}

interface MaintenanceDashboard {
  total_orders: number
  today_orders: number
  completed: number
  worker_status: string
  worker_rating: number
}

export const dashboardService = {
  getLandlord(): Promise<LandlordDashboard> {
    return api.get('/landlord/dashboard')
  },
  getMaintenance(): Promise<MaintenanceDashboard> {
    return api.get('/maintenance/dashboard')
  },
}
