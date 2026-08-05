import api from './api'

export interface TenantProfile {
  id: number
  user_id: number
  is_default: boolean
  label: string | null
  chinese_name: string | null
  given_name_pinyin: string | null
  surname_pinyin: string | null
  birth_date: string | null
  gender: string | null
  phone: string | null
  email: string | null
  nationality: string | null
  school_name: string | null
  enrollment_grade: string | null
  major_english: string | null
  enrollment_level: string | null
  enrollment_term: string | null
  student_classification: string | null
  preferred_name: string | null
  is_international: boolean
  visa_type: string | null
  visa_expiry: string | null
  citizenship_country: string | null
  disability_needs: string | null
  dietary_needs: string | null
  gender_identity: string | null
  created_at: string
  updated_at: string
}

export type TenantCreateData = Partial<Omit<TenantProfile, 'id' | 'user_id' | 'is_default' | 'created_at' | 'updated_at'>>
export type TenantUpdateData = Partial<TenantCreateData>

export const tenantService = {
  /** 获取当前用户的所有租客档案 */
  listMine(): Promise<TenantProfile[]> {
    return api.get('/tenants/my').then((r) => r.data)
  },

  /** 新建租客档案 */
  create(data: TenantCreateData): Promise<TenantProfile> {
    return api.post('/tenants/my', data).then((r) => r.data)
  },

  /** 获取单个租客档案 */
  get(id: number): Promise<TenantProfile> {
    return api.get(`/tenants/my/${id}`).then((r) => r.data)
  },

  /** 更新租客档案 */
  update(id: number, data: TenantUpdateData): Promise<TenantProfile> {
    return api.patch(`/tenants/my/${id}`, data).then((r) => r.data)
  },

  /** 删除租客档案 */
  delete(id: number): Promise<void> {
    return api.delete(`/tenants/my/${id}`)
  },

  /** 设为默认租客 */
  setDefault(id: number): Promise<TenantProfile> {
    return api.post(`/tenants/my/${id}/default`).then((r) => r.data)
  },
}
