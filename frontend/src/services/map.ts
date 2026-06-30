// 地图服务 - 视口框选查询、地图配置
import api from './api'

export interface MapBounds {
  sw_lat: number
  sw_lng: number
  ne_lat: number
  ne_lng: number
}

/** 地图房源轻量数据 */
export interface MapProperty {
  id: number
  title: string
  district: string
  address: string
  price_monthly: number
  bedrooms: number
  bathrooms: number
  property_type: string
  latitude: number
  longitude: number
  area_sqm: number | null
  primary_image_url?: string | null
}

export interface MapPropertiesResponse {
  count: number
  items: MapProperty[]
}

export interface MapConfig {
  amap_js_key: string
  center: [number, number]
  zoom: number
}

export const mapService = {
  /** 根据视口框选查询房源 */
  getPropertiesInBounds(bounds: MapBounds, limit = 500): Promise<MapPropertiesResponse> {
    return api.get('/map/properties', {
      params: {
        sw_lat: bounds.sw_lat,
        sw_lng: bounds.sw_lng,
        ne_lat: bounds.ne_lat,
        ne_lng: bounds.ne_lng,
        limit,
      },
    }).then((r) => r.data)
  },

  /** 获取地图配置（高德 key 等） */
  getConfig(): Promise<MapConfig> {
    return api.get('/map/config').then((r) => r.data)
  },
}
