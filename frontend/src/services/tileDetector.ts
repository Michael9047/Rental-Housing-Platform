// 地图瓦片服务：国内房源使用高德，海外房源使用 Google
import L from 'leaflet'

const AMAP_URL = 'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x={x}&y={y}&z={z}'
const GM_TILE_URL = 'https://mt{s}.google.com/vt/lyrs=m&hl=zh-CN&x={x}&y={y}&z={z}'
const THRESHOLD = 3

export type TileProvider = 'amap' | 'google'

/** 根据房源国家选择地图源；国家缺失时按海外房源处理。 */
export function getTileProvider(country?: string | null): TileProvider {
  const normalized = country?.trim().toUpperCase()
  return ['CN', 'CHN', 'CHINA', '中国', '中华人民共和国'].includes(normalized || '')
    ? 'amap'
    : 'google'
}

export interface TileHandle {
  destroy(): void
  attribution: string
}

function _layer(
  map: L.Map,
  primaryUrl: string, primaryOpts: Record<string, any>,
  fallbackUrl: string, fallbackOpts: Record<string, any>,
): TileHandle {
  let cur = L.tileLayer(primaryUrl, primaryOpts as any)
  const fb = L.tileLayer(fallbackUrl, fallbackOpts as any)
  let errs = 0
  let done = false

  function onErr() {
    if (done) return
    if (++errs >= THRESHOLD) {
      done = true
      map.removeLayer(cur)
      cur = fb
      cur.addTo(map)
    }
  }
  cur.on('tileerror', onErr)
  cur.on('tileload', () => { errs = 0 })
  cur.addTo(map)

  return {
    attribution: (primaryOpts.attribution as string) || '',
    destroy() {
      try { cur.off('tileerror', onErr); map.removeLayer(cur) } catch { /* ok */ }
    },
  }
}

export async function loadTiles(map: L.Map, country?: string | null): Promise<TileHandle> {
  const amapOpts = {
    maxZoom: 18,
    subdomains: ['1', '2', '3', '4'],
    attribution: '© 高德地图',
  }
  const gmOpts = {
    maxZoom: 20,
    subdomains: ['0', '1', '2', '3'],
    attribution: '© Google',
  }

  if (getTileProvider(country) === 'amap') {
    return _layer(map, AMAP_URL, amapOpts, GM_TILE_URL, gmOpts)
  }
  return _layer(map, GM_TILE_URL, gmOpts, AMAP_URL, amapOpts)
}
