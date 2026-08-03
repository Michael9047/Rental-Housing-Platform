// 匹配后端 schemas/unit_type.py UnitTypeRead（两层层结构：Institute → UnitType）
export type PropertyType = 'studio' | 'ensuite' | '1bed' | '2bed' | '3bed' | '4bed' | '5bed+' | 'shared'
export type PropertyStatus = 'available' | 'rented' | 'maintenance'
export type DepositType = 'one_month' | 'one_three' | 'two_month' | 'three_month' | 'half_month' | 'free' | 'custom'

<<<<<<< HEAD
/** 租房规则（前端展示用） */
export interface RentalRules {
  cancellation_policy?: string
  check_out_rules?: string
  pet_policy?: string
  payment_rules?: string
  check_in_rules?: string
  room_change_rules?: string
  sublet_rules?: string
  early_termination_rules?: string
  renewal_rules?: string
  guest_policy?: string
  quiet_hours?: string
  smoking_policy?: string
  common_area_rules?: string
  maintenance_rules?: string
}

=======
/** 房源实体 = UnitType + Institute 继承字段（代替旧 Property） */
>>>>>>> merge/pr33-pr35
export interface Property {
  // UnitType 自身
  id: number
  business_id?: string | null
  uuid?: string | null
  institute_id: number
  name: string
  /** @deprecated 兼容旧代码 — 等同于 name */
  title: string
  property_type?: PropertyType | null
  bedrooms: number
  bathrooms: number
  hall_count: number
  area_sqm: number | null
  base_rent: number
  /** @deprecated 兼容旧代码 — 等同于 base_rent */
  price_monthly: number
  /** @deprecated 兼容旧代码 — 等同于 name */
  unit_type_name?: string | null
  /** @deprecated 兼容旧代码 — 房间号（UnitType 不再有房间概念） */
  room_number?: string | null
  deposit_amount?: number | null
  deposit_type?: DepositType | null
<<<<<<< HEAD
  rental_rules?: RentalRules | null
  version: number
=======
  lease_start?: string | null
  lease_end?: string | null
  lease_start_date?: string | null
  lease_end_date?: string | null
  currency?: string | null
  special_offer?: string | null
  floor_pricing?: Record<string, number>[] | null
  amenities?: string[] | null
  image_urls?: string[] | null
  description?: string | null
  available_from?: string | null
  min_stay_months: number
  /** 兼容旧 booking 组件 — 等同于 min_stay_months */
  min_lease_months: number
  /** 兼容旧 booking 组件 — 留空表示无上限 */
  max_lease_months?: number | null
  /** 兼容旧 booking 组件 — 默认为 0 */
  service_fee_rate?: number | null
  has_vacancy: boolean
  total_count: number
  available_count: number
  status: PropertyStatus
>>>>>>> merge/pr33-pr35
  deleted_at?: string | null
  created_at: string
  updated_at: string

  // Institute 继承
  institute_name?: string | null
  institute_business_id?: string | null
  institute_address?: string | null
  /** @deprecated 兼容旧代码 — 等同于 institute_address */
  address?: string | null
  /** @deprecated 兼容旧代码 — 等同于 district（或 institute_name） */
  district?: string | null
  country?: string | null
  city?: string | null
  district?: string | null
  district?: string | null
  latitude?: number | null
  longitude?: number | null
  contact_phone?: string | null
  contact_email?: string | null
  logo_url?: string | null
  female_only?: boolean
  couples_allowed?: boolean
  building_type?: string | null
  total_floors?: number | null
  year_built?: number | null
  has_elevator?: boolean
  website_url?: string | null

  // 兼容
  images?: PropertyImage[]
  primary_image_url?: string | null
  similarity?: number | null
}

export interface PropertySearchResult extends Property {
  similarity: number | null
}

export interface PropertySearchParams {
  q?: string
  country?: string
  city?: string
  district?: string
  institute_id?: number
  price_min?: number
  price_max?: number
  bedrooms?: number
  bathrooms?: number
  property_type?: PropertyType
  amenities?: string[]
  available_from?: string
  area_min?: number
  area_max?: number
  sort_by?: string
  limit?: number
  status?: string
  /** 近距搜索：中心点纬度 */
  near_lat?: number
  /** 近距搜索：中心点经度 */
  near_lng?: number
  /** 近距搜索：半径(km) */
  near_distance_km?: number
}

export interface PropertyListResponse {
  items: Property[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface PropertyImage {
  id: number
  property_id?: number
  room_id?: number
  filename: string
  original_name: string
  mime_type: string
  file_size: number
  sort_order: number
  is_primary: boolean
  created_at: string
}

// ── 户型分类标签 ──
export const propertyTypeLabels: Record<string, string> = {
  studio: 'Studio 开间',
  ensuite: 'Ensuite 独卫套间',
  '1bed': '一室一厅',
  '2bed': '两室一厅',
  '3bed': '三室',
  '4bed': '四室',
  '5bed+': '五室及以上',
  shared: '合租单间',
}
