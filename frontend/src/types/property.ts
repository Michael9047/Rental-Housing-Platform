// 公寓/户型前端类型：UnitType + Institute 是权威结构，旧 Property 字段仅作过渡兼容。
export type CanonicalPropertyType =
  | 'studio'
  | 'ensuite'
  | '1bed'
  | '2bed'
  | '3bed'
  | '4bed'
  | '5bed+'
  | 'shared'

/** 旧页面仍会读取这些拼写；新请求应优先发送 CanonicalPropertyType。 */
export type LegacyPropertyType = '1-bed' | '2-bed' | '3-bed' | 'house' | 'apartment'
export type PropertyType = CanonicalPropertyType | LegacyPropertyType

export type PropertyStatus =
  | 'available'
  | 'pending_review'
  | 'rented'
  | 'maintenance'
  | 'offline'
export type RentType = 'monthly' | 'quarterly' | 'yearly'
export type DepositType =
  | 'one_month'
  | 'one_three'
  | 'two_month'
  | 'three_month'
  | 'half_month'
  | 'free'
  | 'custom'

export interface RentalRules {
  cancellation_policy?: string | null
  check_out_rules?: string | null
  pet_policy?: string | null
  payment_rules?: string | null
  check_in_rules?: string | null
  room_change_rules?: string | null
  sublet_rules?: string | null
  early_termination_rules?: string | null
  renewal_rules?: string | null
  guest_policy?: string | null
  quiet_hours?: string | null
  smoking_policy?: string | null
  common_area_rules?: string | null
  maintenance_rules?: string | null
}

export interface PropertyImage {
  id: number
  /** UnitType 图片使用 property_id；公寓图片可能没有该字段。 */
  property_id?: number
  room_id?: number
  filename: string
  original_name?: string
  mime_type?: string
  file_size?: number
  sort_order: number
  is_primary: boolean
  created_at?: string
}

/**
 * UnitTypeRead 的前端展示模型。
 *
 * title/price_monthly/address 等字段由兼容层从 name/base_rent/institute_address
 * 派生；保留它们是为了让尚未迁移的展示组件继续工作。
 */
export interface Property {
  // UnitType 权威字段
  id: number
  business_id?: string | null
  uuid?: string | null
  institute_id: number
  name: string
  property_type?: PropertyType | null
  bedrooms: number
  bathrooms: number
  hall_count: number
  area_sqm: number | null
  base_rent: number
  deposit_amount?: number | null
  deposit_type?: DepositType | null
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
  has_vacancy: boolean
  total_count: number
  available_count: number
  status: PropertyStatus
  deleted_at?: string | null
  created_at: string
  updated_at: string

  // Institute 继承字段
  institute_name?: string | null
  institute_business_id?: string | null
  institute_address?: string | null
  country?: string | null
  city?: string | null
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
  safety_score?: number | null
  rent_period?: string | null
  representative_unit_type_id?: number | null
  unit_type_tags?: string[]
  unit_type_count?: number

  // main 公寓搜索卡字段
  name_cn?: string | null
  min_rent?: number | null
  max_rent?: number | null
  avg_bedrooms?: number | null
  primary_image?: PropertyImage | null

  // 旧 Property 展示兼容字段
  /** @deprecated 使用 name。 */
  title: string
  /** @deprecated 使用 base_rent。 */
  price_monthly: number
  /** @deprecated 使用 name。 */
  unit_type_name?: string | null
  /** @deprecated UnitType 不再表示实体房间。 */
  room_number?: string | null
  /** @deprecated 使用 min_stay_months。 */
  min_lease_months: number
  max_lease_months?: number | null
  service_fee_rate?: number | null
  /** @deprecated 使用 institute_address。 */
  address?: string | null
  landlord_id?: number
  floor?: number | null
  rent_type?: RentType
  version?: number
  rental_rules?: RentalRules | null

  images?: PropertyImage[]
  primary_image_url?: string | null
  similarity?: number | null
}

export interface PropertySearchResult extends Property {
  similarity: number | null
}

/** UnitTypeCreate 对应请求；兼容字段不会改变后端权威字段。 */
export interface PropertyCreate {
  institute_id: number
  name: string
  property_type?: CanonicalPropertyType | null
  bedrooms?: number
  bathrooms?: number
  hall_count?: number
  area_sqm?: number | null
  base_rent: number
  deposit_amount?: number | null
  deposit_type?: DepositType | null
  lease_start?: string | null
  lease_end?: string | null
  currency?: string | null
  special_offer?: string | null
  floor_pricing?: Record<string, number>[] | null
  amenities?: string[] | null
  image_urls?: string[] | null
  description?: string | null
  available_from?: string | null
  min_stay_months?: number
  has_vacancy?: boolean
  total_count?: number
  available_count?: number
  status?: PropertyStatus
}

export type PropertyUpdate = Partial<PropertyCreate> & { version?: number }

export interface PropertySearchParams {
  q?: string
  country?: string
  city?: string
  district?: string
  institute_id?: number
  institute_ids?: number[]
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
  near_lat?: number
  near_lng?: number
  near_distance_km?: number
}

export interface PropertyListResponse {
  items: Property[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

/** 旧房型接口兼容；新代码直接使用 Property（UnitType）。 */
export type RoomTypeEnum = CanonicalPropertyType
export type RoomTypeStatus = 'available' | 'rented' | 'maintenance'
export interface RoomType {
  id: number
  property_id: number
  name: string
  room_type: RoomTypeEnum
  bedrooms: number
  bathrooms: number
  price_monthly: number
  area_sqm: number | null
  floor: number | null
  available_count: number
  available_from: string | null
  min_stay_months: number
  deposit_amount: number | null
  deposit_type: string | null
  amenities: string[] | null
  description: string | null
  status: RoomTypeStatus
  created_at: string
  updated_at: string
}

/**
 * 展示标签允许后端新增户型字符串时安全回退到原值；
 * PropertyType 仍约束创建/搜索请求中的已知枚举。
 */
export const propertyTypeLabels: Record<string, string> = {
  studio: 'Studio 开间',
  ensuite: 'Ensuite 独卫套间',
  '1bed': '一室一厅',
  '2bed': '两室一厅',
  '3bed': '三室',
  '4bed': '四室',
  '5bed+': '五室及以上',
  shared: '合租单间',
  '1-bed': '一室一厅',
  '2-bed': '两室一厅',
  '3-bed': '三室',
  house: '整租住宅',
  apartment: '公寓',
}

export const roomTypeLabels: Record<RoomTypeEnum, string> = {
  studio: 'Studio 单人套间',
  ensuite: 'Ensuite 独卫套间',
  '1bed': '一室一厅',
  '2bed': '两室一厅',
  '3bed': '三室',
  '4bed': '四室',
  '5bed+': '五室及以上',
  shared: '合租单间',
}
