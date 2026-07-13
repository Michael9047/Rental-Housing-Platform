<!-- 通勤路线地图卡片 —— 四种模式切换 + Leaflet 地图 + polyline + 公交换乘标注 -->
<template>
  <el-card shadow="never" class="commute-card" v-if="hasCoords">
    <template #header>
      <span class="card-header-text">🚌 通勤路线 <span v-if="originName">— 从 {{ originName }} 出发</span></span>
    </template>

    <!-- 模式 tabs -->
    <div class="mode-tabs">
      <button
        v-for="m in modes"
        :key="m.key"
        class="mode-tab"
        :class="{ active: activeMode === m.key }"
        :disabled="loading"
        @click="switchMode(m.key)"
      >
        <span class="mode-emoji">{{ m.emoji }}</span>
        <span class="mode-label">{{ m.minutes }}分钟</span>
      </button>
    </div>

    <!-- 地图 -->
    <div class="route-map-container" ref="mapContainer">
      <div v-if="loading" class="map-loading-overlay">
        <el-icon class="is-loading" :size="28"><Loading /></el-icon>
      </div>
    </div>

    <!-- 底部摘要 -->
    <div class="route-summary" v-if="routeDetail">
      📍 全程 <strong>{{ routeDetail.dist_km }}km</strong> · 约 <strong>{{ routeDetail.duration_min }} 分钟</strong>
      <span v-if="routeDetail.source === 'haversine_fallback'" class="fallback-badge">估算值</span>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick, shallowRef } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { commuteService, type RouteDetailResponse, type RouteSegment } from '@/services/commute'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

// Fix Leaflet default icon paths
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

// ── Props ──
const props = defineProps<{
  originLat: number
  originLng: number
  originName?: string
  destLat: number
  destLng: number
  destTitle?: string
  country?: string | null
  city?: string | null
  /** 四种模式的时间（分钟），用于 tab 标签 */
  commuteMins?: { walk_min: number; bike_min: number; drive_min: number; transit_min: number }
}>()

const hasCoords = true // 由父组件 v-if 控制，组件内始终 true

// ── 模式 ──
interface ModeOption { key: string; emoji: string; minutes: number }
const modes = ref<ModeOption[]>([])
const activeMode = ref<string>('walking')
const routeDetail = ref<RouteDetailResponse | null>(null)
const loading = ref(false)

function buildModes() {
  const mins = props.commuteMins || { walk_min: 0, bike_min: 0, drive_min: 0, transit_min: 0 }
  modes.value = [
    { key: 'walking',   emoji: '🚶', minutes: mins.walk_min },
    { key: 'bicycling', emoji: '🚲', minutes: mins.bike_min },
    { key: 'driving',   emoji: '🚗', minutes: mins.drive_min },
    { key: 'transit',   emoji: '🚌', minutes: mins.transit_min },
  ]
}
buildModes()

// ── Leaflet 地图 ──
const mapContainer = ref<HTMLElement | null>(null)
let mapInstance: L.Map | null = null
let mapReady = false
const allLayers = shallowRef<L.Layer[]>([])

function initMap() {
  if (!mapContainer.value || mapReady) return
  mapInstance = L.map(mapContainer.value, {
    zoomControl: true,
    attributionControl: false,
  }).setView([30, 0], 2)

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
  }).addTo(mapInstance)
  mapReady = true
}

function clearLayers() {
  if (!mapInstance) return
  allLayers.value.forEach((l) => mapInstance!.removeLayer(l))
  allLayers.value = []
}

// ── 颜色方案 ──
const SEGMENT_COLORS: Record<string, { color: string; dash?: string; weight: number }> = {
  walking:   { color: '#94a3b8', dash: '12,8', weight: 3 },
  subway:    { color: '#f59e0b', weight: 4 },
  bus:       { color: '#3b82f6', weight: 4 },
  bicycling: { color: '#3b82f6', weight: 4 },
  driving:   { color: '#3b82f6', weight: 4 },
}

function drawSegments(segments: RouteSegment[], mode: string) {
  if (!mapInstance) return
  const bounds: L.LatLngExpression[] = []
  const layers: L.Layer[] = []

  // 起点 marker
  if (segments.length > 0 && segments[0].polyline.length > 0) {
    const first = segments[0].polyline[0]
    const startMarker = L.circleMarker([first[0], first[1]], {
      radius: 8, color: '#22c55e', fillColor: '#22c55e', fillOpacity: 0.8, weight: 2,
    })
    startMarker.bindTooltip(props.originName || '起点', { direction: 'top', offset: [0, -8] })
    startMarker.addTo(mapInstance)
    layers.push(startMarker)
    bounds.push([first[0], first[1]])
  }

  // 终点 marker
  if (segments.length > 0) {
    const lastSeg = segments[segments.length - 1]
    if (lastSeg.polyline.length > 0) {
      const last = lastSeg.polyline[lastSeg.polyline.length - 1]
      const endMarker = L.circleMarker([last[0], last[1]], {
        radius: 8, color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.8, weight: 2,
      })
      endMarker.bindTooltip(props.destTitle || '房源', { direction: 'top', offset: [0, -8] })
      endMarker.addTo(mapInstance)
      layers.push(endMarker)
      bounds.push([last[0], last[1]])
    }
  }

  if (mode === 'transit') {
    // 公交模式 —— 每段不同颜色 + 换乘站标注
    for (let i = 0; i < segments.length; i++) {
      const seg = segments[i]
      if (seg.polyline.length < 2) continue
      const latlngs: [number, number][] = seg.polyline.map((p) => [p[0], p[1]])
      bounds.push(...latlngs)

      const style = SEGMENT_COLORS[seg.vehicle_type || 'walking'] || SEGMENT_COLORS.walking
      const poly = L.polyline(latlngs, {
        color: style.color,
        weight: style.weight,
        dashArray: style.dash || undefined,
        opacity: 0.85,
      })
      poly.addTo(mapInstance)
      layers.push(poly)

      // 换乘站标记（公交/地铁段的上车站）
      if (seg.line_name && seg.departure_stop) {
        const stopCoord = latlngs[0]
        let tooltip = seg.departure_stop
        if (seg.line_name) tooltip = `${seg.departure_stop}（${seg.line_name}）`
        if (seg.num_stops) tooltip += ` · ${seg.num_stops}站`
        const stopMarker = L.circleMarker(stopCoord, {
          radius: 5, color: style.color, fillColor: '#fff', fillOpacity: 1, weight: 2.5,
        })
        stopMarker.bindTooltip(tooltip, { direction: 'right', offset: [4, 0] })
        stopMarker.addTo(mapInstance)
        layers.push(stopMarker)
      }

      // 末段到达站也标注
      if (seg.line_name && seg.arrival_stop && i === segments.length - 1) {
        const arrCoord = latlngs[latlngs.length - 1]
        const arrMarker = L.circleMarker(arrCoord, {
          radius: 5, color: style.color, fillColor: '#fff', fillOpacity: 1, weight: 2.5,
        })
        arrMarker.bindTooltip(seg.arrival_stop, { direction: 'right', offset: [4, 0] })
        arrMarker.addTo(mapInstance)
        layers.push(arrMarker)
      }
    }
  } else {
    // 非公交模式 —— 单一蓝色 polyline
    const allCoords: [number, number][] = segments.flatMap((s) =>
      s.polyline.map((p) => [p[0], p[1]] as [number, number])
    )
    bounds.push(...allCoords)
    const style = SEGMENT_COLORS[mode] || SEGMENT_COLORS.walking
    const poly = L.polyline(allCoords, {
      color: style.color, weight: style.weight, opacity: 0.85,
    })
    poly.addTo(mapInstance)
    layers.push(poly)
  }

  allLayers.value = layers

  // 自适应视野
  if (bounds.length > 0) {
    mapInstance.fitBounds(bounds as L.LatLngBoundsExpression, { padding: [30, 30], maxZoom: 16 })
  }
}

// ── 切换模式 ──
async function switchMode(mode: string) {
  if (loading.value || activeMode.value === mode) return
  activeMode.value = mode
  await fetchRoute()
}

async function fetchRoute() {
  if (!mapReady) return
  loading.value = true
  routeDetail.value = null
  clearLayers()

  try {
    const result = await commuteService.getRouteDetail({
      origin_lat: props.originLat,
      origin_lng: props.originLng,
      dest_lat: props.destLat,
      dest_lng: props.destLng,
      mode: activeMode.value as 'walking' | 'bicycling' | 'driving' | 'transit',
      country: props.country || null,
      city: props.city || null,
    })
    routeDetail.value = result
    drawSegments(result.segments, result.mode)
  } catch {
    console.debug('路线详情获取失败')
  } finally {
    loading.value = false
  }
}

// ── 生命周期 ──
onMounted(() => {
  nextTick(() => {
    initMap()
    // 初始加载默认模式（walking）
    nextTick(() => fetchRoute())
  })
})

onUnmounted(() => {
  if (mapInstance) {
    mapInstance.remove()
    mapInstance = null
    mapReady = false
  }
})

// 当 props 变化时重新加载
watch(() => [props.originLat, props.originLng, props.destLat, props.destLng], () => {
  if (mapReady) fetchRoute()
})
</script>

<style scoped>
.commute-card {
  margin-bottom: 16px;
}

.card-header-text {
  font-size: 15px;
  font-weight: 600;
}

/* ── 模式 Tabs ── */
.mode-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.mode-tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 10px 4px;
  border: none;
  border-right: 1px solid var(--border);
  background: var(--bg-white);
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary);
  transition: all 0.15s;
}

.mode-tab:last-child {
  border-right: none;
}

.mode-tab:hover {
  background: var(--primary-light);
  color: var(--primary);
}

.mode-tab.active {
  background: var(--primary);
  color: #fff;
}

.mode-tab:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mode-emoji {
  font-size: 20px;
}

.mode-label {
  font-weight: 600;
}

/* ── 地图 ── */
.route-map-container {
  position: relative;
  height: 350px;
  border-radius: var(--radius);
  overflow: hidden;
  border: 1px solid var(--border);
}

.map-loading-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

/* ── 摘要 ── */
.route-summary {
  margin-top: 10px;
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.fallback-badge {
  font-size: 11px;
  background: #fef3c7;
  color: #92400e;
  padding: 1px 8px;
  border-radius: 10px;
}
</style>
