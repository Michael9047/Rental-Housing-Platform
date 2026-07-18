// 地图瓦片加载 —— 全球统一 OpenStreetMap，事件驱动回退
// 替代此前的高德/OSM 双引擎 + 定时轮询方案，与 CommuteRoute / MapSearch / Search 对齐

import L from 'leaflet'

/** 主瓦片源 */
const OSM_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
/** 备用瓦片源（法国镜像，国内可访问） */
const OSMFR_URL = 'https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png'
/** 连续 tileerror 阈值，超过后切到备用源 */
const ERROR_THRESHOLD = 3

export interface TileHandle {
  /** 移除瓦片图层并解绑事件 */
  destroy(): void
}

/**
 * 加载 OSM 瓦片到 Leaflet 地图实例。
 * 主源连续 tileerror ≥ 阈值时自动切到法国镜像，事件驱动、零轮询延迟。
 */
export function loadOSMTiles(map: L.Map): TileHandle {
  let currentLayer = L.tileLayer(OSM_URL, {
    maxZoom: 19,
    crossOrigin: 'anonymous' as any,
  } as any)

  let errorCount = 0
  let switched = false

  function onError() {
    if (switched) return
    errorCount++
    if (errorCount >= ERROR_THRESHOLD) {
      switched = true
      map.removeLayer(currentLayer)
      currentLayer = L.tileLayer(OSMFR_URL, {
        maxZoom: 20,
        subdomains: 'abc',
        crossOrigin: 'anonymous' as any,
      } as any)
      currentLayer.addTo(map)
    }
  }

  function onLoad() {
    // 只要有一张瓦片成功加载，就说明主源可用，重置计数
    if (!switched) errorCount = 0
  }

  currentLayer.on('tileerror', onError)
  currentLayer.on('tileload', onLoad)
  currentLayer.addTo(map)

  return {
    destroy() {
      currentLayer.off('tileerror', onError)
      currentLayer.off('tileload', onLoad)
      try { map.removeLayer(currentLayer) } catch { /* 地图可能已销毁 */ }
    },
  }
}
