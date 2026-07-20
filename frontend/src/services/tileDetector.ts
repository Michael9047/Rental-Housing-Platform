// 地图瓦片加载 —— IP 地理位置预判 + tileerror 兜底
// 每次页面加载实时检测 IP，国内走高德、海外走 OSM；tileerror 自动切备用源

import L from 'leaflet'

/** OSM 官方瓦片源（GeoDNS 自动路由，国内可能分配到莫斯科 Yandex 节点） */
const OSM_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
/** OSM 法国 Humanitarian（国内实测最快 OSM 镜像） */
const OSMFR_HOT_URL = 'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png'
/** 高德矢量瓦片 —— 国内极速，GCJ-02 坐标系，无需 Key */
const AMAP_URL = 'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}'
/** 连续 tileerror 阈值 */
const ERROR_THRESHOLD = 2

/** 内存缓存：同一页面内多个地图组件共享检测结果，避免重复请求 */
let regionCache: 'CN' | 'OS' | null = null

export interface TileHandle {
  destroy(): void
}

// ── IP 地理位置检测 ──────────────────────────────

/**
 * 判断用户是否在中国境内（基于当下网络环境，每次页面加载实时检测）。
 * 仅内存缓存——同一页面内多次调用共享结果，刷新页面重新检测。
 * 不依赖浏览器语言（留学生中文系统不能说明地理位置）。
 */
async function detectRegion(): Promise<'CN' | 'OS'> {
  if (regionCache) return regionCache

  try {
    const res = await fetch('https://ip-api.com/json/?fields=countryCode', {
      signal: AbortSignal.timeout(3000),
    })
    const data = await res.json()
    const region: 'CN' | 'OS' = data.countryCode === 'CN' ? 'CN' : 'OS'
    regionCache = region
    return region
  } catch {
    // IP 查询失败 → 走 OSM + tileerror 回退 HOT
    return 'OS'
  }
}

/** 清除内存缓存（tileerror 触发自动调用，以便同一页面内重试 OSM） */
function clearRegionCache() {
  regionCache = null
}

// ── 瓦片图层工厂 ──────────────────────────────────

/** 高德瓦片（国内用户），带 tileerror 回退 OSM */
function createAmapLayer(map: L.Map): TileHandle {
  let currentLayer = L.tileLayer(AMAP_URL, {
    maxZoom: 18,
    subdomains: ['1', '2', '3', '4'],
    crossOrigin: 'anonymous' as any,
  } as any)

  let errorCount = 0
  let switched = false

  function onError() {
    if (switched) return
    errorCount++
    if (errorCount >= ERROR_THRESHOLD) {
      switched = true
      // 高德连续失败 → 清缓存，下次刷新页面会重新检测
      clearRegionCache()
      map.removeLayer(currentLayer)
      // 切到 OSM 主源 + HOT 回退
      const fallback = createOSMLayerWithFallback(map)
      // 偷梁换柱：把 fallback 的 destroy 也挂上
      currentLayer = fallback as any
    }
  }

  function onLoad() {
    if (!switched) errorCount = 0
  }

  currentLayer.on('tileerror', onError)
  currentLayer.on('tileload', onLoad)
  currentLayer.addTo(map)

  return {
    destroy() {
      currentLayer.off('tileerror', onError)
      currentLayer.off('tileload', onLoad)
      try { map.removeLayer(currentLayer) } catch { /* ignore */ }
    },
  }
}

/** OSM 主源 + tileerror 回退法国 Humanitarian */
function createOSMLayerWithFallback(map: L.Map): TileHandle {
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
      currentLayer = L.tileLayer(OSMFR_HOT_URL, {
        maxZoom: 20,
        subdomains: 'abc',
        crossOrigin: 'anonymous' as any,
      } as any)
      currentLayer.addTo(map)
    }
  }

  function onLoad() {
    if (!switched) errorCount = 0
  }

  currentLayer.on('tileerror', onError)
  currentLayer.on('tileload', onLoad)
  currentLayer.addTo(map)

  return {
    destroy() {
      currentLayer.off('tileerror', onError)
      currentLayer.off('tileload', onLoad)
      try { map.removeLayer(currentLayer) } catch { /* ignore */ }
    },
  }
}

// ── 公共入口 ─────────────────────────────────────

/**
 * 根据用户地理位置加载最优瓦片源。
 * 每次调用实时检测 IP：国内 → 高德，海外 / IP 未知 → OSM 主源。
 * tileerror 自动切备用源。
 */
export async function loadTiles(map: L.Map): Promise<TileHandle> {
  const region = await detectRegion()

  if (region === 'CN') {
    return createAmapLayer(map)
  }
  return createOSMLayerWithFallback(map)
}

/** @deprecated 使用 loadTiles 代替 */
export function loadOSMTiles(map: L.Map): TileHandle {
  return createOSMLayerWithFallback(map)
}
