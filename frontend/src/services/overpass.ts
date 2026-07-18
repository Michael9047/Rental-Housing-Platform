/** POI 周边搜索 —— 国内高德 + 海外 Overpass 双引擎 */

export interface OverpassPOI {
  id: number
  lat: number
  lng: number
  name: string
  distance?: number
  line?: string  // 公交/地铁线路名
}

// ── 国内高德地图 POI 搜索 ──────────────────────────

/** 高德 POI 分类 → keywords */
const AMAP_CATEGORY_KEYWORDS: Record<string, string> = {
  school: '大学',
  bus_station: '公交站|公交车站',
  subway_station: '地铁站',
  supermarket: '超市|便利店',
  restaurant: '餐厅|饭店|快餐|咖啡厅',
  pharmacy: '药店|药房',
}

/** 高德周边搜索 API */
export async function fetchAmapPOIs(
  lat: number,
  lng: number,
  category: string,
  radiusMeters: number = 3000,
): Promise<OverpassPOI[]> {
  const keywords = AMAP_CATEGORY_KEYWORDS[category]
  if (!keywords) return []

  const key = (import.meta as any).env?.VITE_AMAP_WEB_KEY || 'd236c5d4b0bb068d9da00e0066a8f85c'

  try {
    // extensions=all 获取更丰富的信息（含线路名等）
    const url = `https://restapi.amap.com/v3/place/around?key=${key}&location=${lng},${lat}&keywords=${encodeURIComponent(keywords)}&radius=${radiusMeters}&offset=25&extensions=all`
    const resp = await fetch(url)
    if (!resp.ok) throw new Error(`Amap API ${resp.status}`)
    const data = await resp.json()
    if (data.status !== '1') throw new Error(`Amap error: ${data.info}`)

    const raw: OverpassPOI[] = (data.pois || []).map((p: any) => {
      const [plng, plat] = (p.location || '0,0').split(',').map(Number)
      const line = (isTransitCategory(category))
        ? extractAmapLine(p, category)
        : undefined
      return {
        id: parseInt(p.id) || Math.random() * 1e8,
        lat: plat,
        lng: plng,
        name: stripCategorySuffix(p.name || '', category),
        distance: parseInt(p.distance) || 0,
        line,
      }
    })
    return dedupeAndFilter(raw, category)
  } catch (err) {
    console.error('Amap POI query failed:', err)
    return []
  }
}

/** 是否需要提取线路信息 */
function isTransitCategory(cat: string): boolean {
  return cat === 'subway_station' || cat === 'bus_station'
}

/** 从高德 POI 返回中提取线路名 */
function extractAmapLine(p: any, category: string): string {
  // 高德 address 中常含线路信息，如 "1号线" 或 "1号线;3号线"
  const addr: string = p.address || ''

  if (category === 'subway_station') {
    // 匹配 "1号线"、"2号线"、"S1线" 等格式
    const m = addr.match(/[\d\w]+号?线/g)
    if (m) return [...new Set(m)].join(' / ')
  }
  if (category === 'bus_station') {
    // 公交站 address 常含线路号
    const m = addr.match(/[\d\w]+路/g)
    if (m) return [...new Set(m)].slice(0, 6).join(' / ')
  }
  return ''
}

/** 去掉名称中的分类后缀，如 "星海广场(地铁站)" → "星海广场" */
function stripCategorySuffix(name: string, category: string): string {
  return name.replace(/[（(](?:地铁站|公交站|公交车站|大学|学院)[）)]/g, '').trim()
}

// ── 海外 Overpass API POI 搜索 ──────────────────────

/** Overpass POI 分类 → 查询片段 */
const OVERPASS_CATEGORY_QUERIES: Record<string, string> = {
  school: `
    node["amenity"="university"](around:{{radius}},{{lat}},{{lng}});
    way["amenity"="university"](around:{{radius}},{{lat}},{{lng}});
  `,
  bus_station: `
    node["highway"="bus_stop"](around:{{radius}},{{lat}},{{lng}});
    node["amenity"="bus_station"](around:{{radius}},{{lat}},{{lng}});
  `,
  subway_station: `
    node["railway"="station"]["station"="subway"](around:{{radius}},{{lat}},{{lng}});
    node["station"="subway"](around:{{radius}},{{lat}},{{lng}});
    node["railway"="subway_entrance"](around:{{radius}},{{lat}},{{lng}});
  `,
  supermarket: `
    node["shop"~"supermarket|convenience"](around:{{radius}},{{lat}},{{lng}});
    way["shop"~"supermarket|convenience"](around:{{radius}},{{lat}},{{lng}});
  `,
  restaurant: `
    node["amenity"~"restaurant|fast_food|cafe"](around:{{radius}},{{lat}},{{lng}});
    way["amenity"~"restaurant|fast_food|cafe"](around:{{radius}},{{lat}},{{lng}});
  `,
  pharmacy: `
    node["amenity"="pharmacy"](around:{{radius}},{{lat}},{{lng}});
    way["amenity"="pharmacy"](around:{{radius}},{{lat}},{{lng}});
  `,
}

/** 俄罗斯 Overpass 镜像（国内可访问） */
const OVERPASS_ENDPOINT = 'https://maps.mail.ru/osm/tools/overpass/api/interpreter'

function extractOSMName(tags: Record<string, string>): string {
  return (
    tags['name'] ||
    tags['name:zh'] ||
    tags['name:en'] ||
    tags['official_name'] ||
    tags['brand'] ||
    tags['operator'] ||
    '未知'
  )
}

export async function fetchOverpassPOIs(
  lat: number,
  lng: number,
  category: string,
  radiusMeters: number = 3000,
): Promise<OverpassPOI[]> {
  const queryBody = OVERPASS_CATEGORY_QUERIES[category]
  if (!queryBody) return []

  const filled = queryBody
    .replace(/\{\{radius\}\}/g, String(radiusMeters))
    .replace(/\{\{lat\}\}/g, String(lat))
    .replace(/\{\{lng\}\}/g, String(lng))

  const overpassQuery = `[out:json][timeout:15];(${filled});out center 100;`

  try {
    const resp = await fetch(OVERPASS_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: overpassQuery,
    })
    if (!resp.ok) throw new Error(`Overpass API ${resp.status}`)
    const data = await resp.json()

    const raw: OverpassPOI[] = (data.elements || [])
      .filter((el: any) => el.tags && (el.lat || el.center))
      .map((el: any) => {
        const elLat = el.lat ?? el.center?.lat
        const elLng = el.lon ?? el.center?.lon
        const tags = el.tags || {}
        const name = extractOSMName(tags)
        const dist = haversineDistance(lat, lng, elLat, elLng)
        let line: string | undefined
        if (category === 'subway_station') {
          line = tags['line'] || tags['route_ref'] || tags['ref'] || ''
          if (!line) line = undefined
        }
        if (category === 'bus_station') {
          line = tags['route_ref'] || tags['line'] || tags['ref'] || ''
          if (!line) line = undefined
        }
        return { id: el.id, lat: elLat, lng: elLng, name, distance: Math.round(dist), line }
      })
    return dedupeAndFilter(raw, category)
  } catch (err) {
    console.error('Overpass POI query failed:', err)
    return []
  }
}

// ── 统一入口（自动选引擎） ─────────────────────────

/**
 * 查询附近 POI —— 国内用高德，海外用 Overpass
 */
export async function fetchNearbyPOIs(
  lat: number,
  lng: number,
  category: string,
  radiusMeters: number = 3000,
  country?: string,
): Promise<OverpassPOI[]> {
  if (country === 'CN') {
    return fetchAmapPOIs(lat, lng, category, radiusMeters)
  }
  return fetchOverpassPOIs(lat, lng, category, radiusMeters)
}

/** 公交/地铁站聚类半径（米），该范围内的多个出入口视为同一站 */
const TRANSIT_CLUSTER_RADIUS: Record<string, number> = {
  subway_station: 300,
  bus_station: 200,
}

/** 去重 + 过滤无效名称 + 公交/地铁站距离聚类 */
function dedupeAndFilter(pois: OverpassPOI[], category: string): OverpassPOI[] {
  const seen = new Map<string, OverpassPOI>()

  for (const p of pois) {
    // 过滤空名、未知
    if (!p.name || p.name === '未知' || p.name.trim() === '') continue

    const key = p.name
    const existing = seen.get(key)

    if (!existing) {
      seen.set(key, p)
    } else {
      // 同名：保留距离更近的；合并线路信息
      if ((p.distance ?? Infinity) < (existing.distance ?? Infinity)) {
        // 新更近 → 替换，但保留原线路信息
        if (existing.line && p.line) {
          p.line = [...new Set([...existing.line.split(' / '), ...p.line.split(' / ')])].join(' / ')
        } else if (existing.line) {
          p.line = existing.line
        }
        seen.set(key, p)
      } else {
        // 原更近 → 保留原，合并线路
        if (p.line) {
          const merged = existing.line
            ? [...new Set([...existing.line.split(' / '), ...p.line.split(' / ')])].join(' / ')
            : p.line
          existing.line = merged
        }
      }
    }
  }

  let result = Array.from(seen.values())

  // ── 公交/地铁站按距离聚类去重（同一站的多个出入口）──
  const clusterRadius = TRANSIT_CLUSTER_RADIUS[category]
  if (clusterRadius) {
    result = clusterByProximity(result, clusterRadius)
  }

  return result.sort((a, b) => (a.distance ?? 0) - (b.distance ?? 0))
}

/**
 * 基于距离的聚类去重：同类别 POI 在阈值距离内时只保留最近的一个。
 * 算法：贪心扫描，已按距离升序排列的列表，每个点检查是否落在已有聚类内。
 */
function clusterByProximity(pois: OverpassPOI[], radiusM: number): OverpassPOI[] {
  // 按距离升序
  const sorted = [...pois].sort((a, b) => (a.distance ?? 0) - (b.distance ?? 0))
  const clusters: { center: OverpassPOI; members: OverpassPOI[] }[] = []

  for (const p of sorted) {
    let matched = false
    for (const cluster of clusters) {
      const d = haversineDistance(
        cluster.center.lat, cluster.center.lng,
        p.lat, p.lng,
      )
      if (d <= radiusM) {
        // 落入已有聚类 → 合并线路信息到聚类中心
        cluster.members.push(p)
        if (p.line) {
          const merged = cluster.center.line
            ? [...new Set([...cluster.center.line.split(' / '), ...p.line.split(' / ')])].join(' / ')
            : p.line
          cluster.center.line = merged
        }
        // 如果新点更近，替换聚类中心
        if ((p.distance ?? Infinity) < (cluster.center.distance ?? Infinity)) {
          // 交换中心与成员：将旧中心降格为成员，新点升级为中心
          cluster.members.push(cluster.center)
          cluster.center = p
        }
        matched = true
        break
      }
    }
    if (!matched) {
      clusters.push({ center: p, members: [] })
    }
  }

  return clusters.map(c => c.center)
}

// ── 距离工具 ──────────────────────────────────────

function haversineDistance(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371000
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLng = ((lng2 - lng1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLng / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export function metersToKm(m: number): string {
  if (m < 1000) return `${m}m`
  return `${(m / 1000).toFixed(1)}km`
}

export function metersToMiles(m: number): string {
  const miles = m / 1609.344
  if (miles < 0.1) return `${Math.round(m)}m`
  return `${miles.toFixed(1)}mi`
}
