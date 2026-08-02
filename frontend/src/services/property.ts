import api from './api'
import type {
  Property,
  PropertyCreate,
  PropertyUpdate,
  PropertySearchResult,
  PropertySearchParams,
  PropertyListResponse,
  PropertyImage,
  RoomType,
} from '@/types/property'

// ── 租期价格类型（对应后端 LeasePricingService）──

/** 金额 */
export interface MoneyAmount {
  currency: string
  minor_units: number
  minor_unit_exponent: number
  decimal: string
}

/** 费用桶（local + cny） */
export interface FeeBucket {
  local: MoneyAmount
  cny: MoneyAmount
}

/** 费用集合 */
export interface PriceSet {
  deposit: FeeBucket
  service_fee: FeeBucket
  monthly_rent: FeeBucket
  amount_due_now: FeeBucket
  rent_total: FeeBucket
}

/** 租期选项 */
export interface LeaseOption {
  months: number
  end_date: string
  prices: PriceSet
}

/** 租期价格快照 */
export interface LeasePricing {
  property_id: number
  calculation_date: string
  move_in_date: string
  local_currency: string
  exchange_rate_to_cny: string
  exchange_rate_at: string
  exchange_rate_source: string
  options: LeaseOption[]
}

/** 预订日期可用性 */
export interface BookingDateAvailability {
  property_id: number
  timezone: string
  local_today: string
  available_from: string | null
  blocked_dates: string[]
}

/** 日期校验结果 */
export interface BookingDateValidation {
  available: boolean
  reason?: string | null
}

export interface PropertyPOI {
  content: string
  poi_data: Record<string, { name: string; distance: string }[]>
  generated_at: string
}

/** 地图小卡片 POI 预生成数据 */
export interface MapPOIItem {
  id: number | string
  name: string
  lat: number
  lng: number
  distance: number | null
  line: string | null
}

export interface MapPOIResponse {
  property_id: number
  generated_at: string | null
  search_radius_m: number
  categories: Record<string, MapPOIItem[]>
}

export interface GeocodeResult {
  address: string
  latitude: number
  longitude: number
  formatted_address?: string | null
  level?: string | null
  province?: string | null
  city?: string | null
  district?: string | null
}

export const propertyService = {
  list(params?: { page?: number; page_size?: number; district?: string; status?: string; landlord_id?: number; keyword?: string; property_type?: string; price_min?: number; price_max?: number }): Promise<PropertyListResponse> {
    return api.get('/unit-types', { params }).then((r) => r.data)
  },

  listRecycleBin(params?: { page?: number; page_size?: number; landlord_id?: number }): Promise<PropertyListResponse> {
    return api.get('/unit-types/recycle-bin', { params }).then((r) => r.data)
  },

  restore(id: number | string): Promise<Property> {
    return api.post(`/unit-types/${id}/restore`).then((r) => r.data)
  },

  batchUpdateStatus(ids: number[], status: string): Promise<{ success: number; failed: number; errors?: any[] }> {
    return api.post('/unit-types/batch/status', { ids, status }).then((r) => r.data)
  },

  batchDelete(ids: number[]): Promise<{ success: number; failed: number }> {
    return api.post('/unit-types/batch/delete', { ids }).then((r) => r.data)
  },

  hardDelete(id: number | string): Promise<void> {
    return api.delete(`/unit-types/${id}/hard`)
  },

  batchRestore(ids: number[]): Promise<{ success: number; failed: number }> {
    return api.post('/unit-types/batch/restore', { ids }).then((r) => r.data)
  },

  batchHardDelete(ids: number[]): Promise<{ success: number; failed: number }> {
    return api.post('/unit-types/batch/hard-delete', { ids }).then((r) => r.data)
  },

  search(params: PropertySearchParams): Promise<PropertySearchResult[]> {
    return api.get('/unit-types/search', { params: { ...params, _t: Date.now() } }).then((r) => r.data)
  },

  getById(id: number | string): Promise<Property> {
    return api.get(`/unit-types/${id}`).then((r) => r.data)
  },

  create(data: PropertyCreate): Promise<Property> {
    return api.post('/unit-types', data).then((r) => r.data)
  },

  update(id: number | string, data: PropertyUpdate): Promise<Property> {
    return api.patch(`/unit-types/${id}`, data).then((r) => r.data)
  },

  geocodeAddress(address: string, city?: string): Promise<GeocodeResult> {
    return api.post('/geo/geocode', { address, city }).then((r) => ({
      ...r.data,
      latitude: Number(r.data.latitude),
      longitude: Number(r.data.longitude),
    }))
  },

  delete(id: number | string): Promise<void> {
    return api.delete(`/unit-types/${id}`)
  },

  // Image management
  listImages(propertyId: number | string): Promise<PropertyImage[]> {
    return api.get(`/unit-types/${propertyId}/images`).then((r) => r.data)
  },

  uploadImages(propertyId: number | string, files: File[]): Promise<PropertyImage[]> {
    const formData = new FormData()
    files.forEach((f) => formData.append('files', f))
    return api.post(`/unit-types/${propertyId}/images`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },

  deleteImage(propertyId: number | string, imageId: number | string): Promise<void> {
    return api.delete(`/unit-types/${propertyId}/images/${imageId}`)
  },

  setPrimaryImage(propertyId: number | string, imageId: number | string): Promise<PropertyImage> {
    return api.patch(`/unit-types/${propertyId}/images/${imageId}/primary`).then((r) => r.data)
  },

  // POI
  getPropertyPOI(propertyId: number | string): Promise<PropertyPOI | null> {
    return api.get(`/pois/${propertyId}`).then((r) => r.data).catch(() => null)
  },

  /** 地图小卡片 POI 预生成数据（6 大类，含 lat/lng） */
  getMapPOIs(propertyId: number | string): Promise<MapPOIResponse | null> {
    return api.get(`/pois/${propertyId}/map`).then((r) => r.data).catch(() => null)
  },

  // ---- ML ----
  /** AI 深度解析房源描述 */
  parseDescription(rawText: string): Promise<import('@/types/admin').ParsedProperty> {
    return api.post('/ml/parse', { raw_text: rawText }).then((r) => r.data)
  },

  /** 智能租金预估 */
  estimateRent(params: {
    area_sqm?: number
    bedrooms?: number
    bathrooms?: number
    district?: string
    property_type?: string
    deposit_amount?: number
    service_fee_rate?: number
  }): Promise<import('@/types/admin').RentEstimate> {
    return api.get('/ml/rent-estimate', { params }).then((r) => r.data)
  },

  /** 获取某个楼栋下的所有房型 */
  listRoomTypes(propertyId: number): Promise<RoomType[]> {
    return api.get(`/unit-types/${propertyId}/room-types`).then((r) => r.data)
  },

  // ── 预订管线：日历可用性 + 日期校验 + 租期价格 ──

  getBookingDateAvailability(unitTypeId: number, year: number, month: number): Promise<{
    property_id: number; timezone: string; local_today: string;
    available_from: string | null; blocked_dates: string[];
  }> {
    return api.get(`/unit-types/${unitTypeId}/booking-availability`, { params: { year, month } }).then((r) => r.data)
  },

  validateBookingDate(unitTypeId: number, moveInDate: string): Promise<{ available: boolean; reason?: string | null }> {
    return api.post(`/unit-types/${unitTypeId}/validate-booking-date`, { move_in_date: moveInDate }).then((r) => r.data)
  },

  getLeasePricing(unitTypeId: number, moveInDate: string): Promise<any> {
    return api.get(`/unit-types/${unitTypeId}/lease-pricing`, { params: { move_in_date: moveInDate } }).then((r) => r.data)
  },

  // ---- 修改历史 ----
  /** 获取房源操作审计日志（修改历史） */
  getHistory(propertyId: number | string, params?: { skip?: number; limit?: number }): Promise<PropertyHistoryItem[]> {
    return api.get(`/unit-types/${propertyId}/history`, { params }).then((r) => r.data)
  },

  /** 获取当前房东所有房源的最新操作记录（按时间倒序） */
  getRecentAudit(limit = 20): Promise<PropertyHistoryItem[]> {
    return api.get('/unit-types/audit/recent', { params: { limit } }).then((r) => r.data)
  },

  /** 撤销某条审计日志对应的房源操作 */
  revertAudit(propertyId: number, auditLogId: number): Promise<{ message: string; property_id: number; reverted_action: string }> {
    return api.post(`/unit-types/${propertyId}/revert/${auditLogId}`).then((r) => r.data)
  },

  /** 删除单条审计日志 */
  deleteAuditLog(auditLogId: number): Promise<void> {
    return api.delete(`/unit-types/audit/${auditLogId}`)
  },

  /** 批量删除审计日志 */
  batchDeleteAuditLogs(ids: number[]): Promise<{ deleted: number }> {
    return api.post('/unit-types/audit/batch-delete', { ids }).then((r) => r.data)
  },

  /** 一键清空当前用户所有房源审计日志 */
  clearAuditLogs(): Promise<{ deleted: number }> {
    return api.post('/unit-types/audit/clear').then((r) => r.data)
  },

  // ── 预订流程相关 ──

  /** 获取房源的可预订日期（日历视图）。 */
  getBookingDateAvailability(propertyId: number, year: number, month: number): Promise<BookingDateAvailability> {
    return api.get(`/properties/${propertyId}/booking-availability`, { params: { year, month } }).then((r) => r.data)
  },

  /** 校验单个日期是否可入住。 */
  validateBookingDate(propertyId: number, date: string): Promise<BookingDateValidation> {
    return api.get(`/properties/${propertyId}/validate-booking-date`, { params: { date } }).then((r) => r.data)
  },

  /** 获取房源指定入住日期的租期价格选项。 */
  getLeasePricing(propertyId: number, moveInDate: string): Promise<LeasePricing> {
    return api.get(`/properties/${propertyId}/lease-pricing`, { params: { move_in_date: moveInDate } }).then((r) => r.data)
  },
}

export interface PropertyHistoryItem {
  id: number
  user_id: number | null
  username?: string | null
  action: string
  resource_id: number | null
  details: Record<string, any> | null
  ip_address: string | null
  created_at: string
  property_title?: string | null
  property_address?: string | null
  institute_name?: string | null
}
