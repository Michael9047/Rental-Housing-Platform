/** 数据台 API 客户端 */
import api from './api'

interface LandlordDashboard {
  properties: { total: number; available: number; rented: number; maintenance: number }
  bookings: { pending: number }
  repairs: { pending: number; in_progress: number }
  workers: { total: number; available: number }
}

interface BdDashboard {
  institutes: number
  total_properties: number
  pending_bookings: number
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
    return api.get('/landlord/dashboard').then((r) => r.data)
  },
  getBd(): Promise<BdDashboard> {
    return api.get('/bd/dashboard').then((r) => r.data)
  },
  getMaintenance(): Promise<MaintenanceDashboard> {
    return api.get('/maintenance/dashboard').then((r) => r.data)
  },
}
