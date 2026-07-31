import api from './api'

export interface Building {
  id: number; name: string; name_cn?: string | null; abbreviation?: string | null
  address?: string | null
  // 结构化地址
  country?: string | null; city?: string | null
  district?: string | null; street?: string | null
  postal_code?: string | null; npc?: string | null
  contact_phone?: string | null; contact_email?: string | null
  website_url?: string | null
  description?: string | null; status: string; created_by: number
  created_at?: string | null
  latitude?: number | null; longitude?: number | null
  business_id?: string | null
  // 建筑属性
  building_type?: string | null; total_floors?: number | null
  year_built?: number | null; total_units?: number | null
  has_elevator?: boolean
  // 功能
  amenities?: string[] | null
  female_only?: boolean; couples_allowed?: boolean
  // BM
  bm_id?: number | null; bm_wechat?: string | null; bm_wechat_qr?: string | null
  // 图片
  images?: Array<{id:number;filename:string;original_name:string;sort_order:number;is_primary:boolean}>
}

export const buildingService = {
  list(params?: { skip?: number; limit?: number }): Promise<Building[]> {
    return api.get('/buildings', { params }).then(r => r.data)
  },
  create(data: { name: string; address?: string; contact_phone?: string; description?: string }): Promise<Building> {
    return api.post('/buildings', data).then(r => r.data)
  },
  get(id: number): Promise<Building> {
    return api.get(`/buildings/${id}`).then(r => r.data)
  },
  update(id: number, data: Partial<Building>): Promise<Building> {
    return api.patch(`/buildings/${id}`, data).then(r => r.data)
  },
  remove(id: number): Promise<void> {
    return api.delete(`/buildings/${id}`)
  },
}
