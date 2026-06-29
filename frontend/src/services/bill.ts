import api from './api'

/** 账单响应（对齐后端 bills 表结构） */
export interface BillResponse {
  id: number
  user_id: number
  booking_id: number
  property_id: number
  bill_type: 'deposit' | 'rent'
  amount: number
  status: 'unpaid' | 'paid'
  due_date: string | null
  paid_at: string | null
  created_at: string
}

/** 分页查询参数 */
export interface BillListParams {
  type?: 'deposit' | 'rent'
  status?: 'unpaid' | 'paid'
  skip?: number
  limit?: number
}

/** 分页响应 */
export interface PaginatedBills {
  items: BillResponse[]
  total: number
  skip: number
  limit: number
}

export const billService = {
  /** 获取单条账单详情 */
  getById(id: number): Promise<BillResponse> {
    return api.get(`/bills/${id}`).then((r) => r.data)
  },

  /** 分页查询账单列表 */
  list(params?: BillListParams): Promise<PaginatedBills> {
    return api.get('/bills', { params }).then((r) => r.data)
  },
}
