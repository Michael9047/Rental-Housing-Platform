// 通勤时间计算服务 —— 调用后端路线规划 API
import api from './api'

/** 目标房源 */
export interface CommuteDest {
  id: number | string
  lat: number
  lng: number
}

/** 后端返回的单个通勤结果 */
export interface CommuteItem {
  dest_id: number | string
  dist_km: number
  walk_min: number
  bike_min: number
  drive_min: number
  transit_min: number
  source: string
}

/** 批量通勤计算请求 */
export interface CommuteCalculateRequest {
  origin_lat: number
  origin_lng: number
  destinations: CommuteDest[]
  country?: string | null
  city?: string | null
}

/** 批量通勤计算响应 */
export interface CommuteCalculateResponse {
  results: CommuteItem[]
  source: string
}

// ── 路线详情（单条路线 + polyline）──────────────────────────────────────

/** 路线段 */
export interface RouteSegment {
  polyline: number[][]          // [[lat, lng], ...]
  distance_m: number
  duration_s: number
  line_name: string | null       // 公交线路名
  vehicle_type: string | null    // "walking" | "subway" | "bus"
  departure_stop: string | null  // 上车站
  arrival_stop: string | null    // 下车站
  num_stops: number | null       // 途经站数
}

/** 路线详情请求 */
export interface RouteDetailRequest {
  origin_lat: number
  origin_lng: number
  dest_lat: number
  dest_lng: number
  mode: 'walking' | 'bicycling' | 'driving' | 'transit'
  country?: string | null
  city?: string | null
}

/** 路线详情响应 */
export interface RouteDetailResponse {
  mode: string
  dist_km: number
  duration_min: number
  segments: RouteSegment[]
  source: string
}

export const commuteService = {
  /** 批量计算从起点（学校）到多个房源的通勤时间（四种模式） */
  calculate(request: CommuteCalculateRequest): Promise<CommuteCalculateResponse> {
    return api.post('/commute/calculate', request).then((r) => r.data)
  },

  /** 获取单条路线详情（含 polyline，公交含换乘信息） */
  getRouteDetail(request: RouteDetailRequest): Promise<RouteDetailResponse> {
    return api.post('/commute/route', request).then((r) => r.data)
  },
}
