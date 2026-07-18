<!-- 房源周边地图卡片 —— POI 分类 tabs + Leaflet 地图 + 右侧 POI 列表 -->
<template>
  <el-card shadow="never" class="property-map-card" v-if="hasCoords">
    <!-- 第一行：房源名称 + 地址 -->
    <div class="map-header">
      <h3 class="map-property-name">{{ propertyTitle }}</h3>
      <p class="map-property-address">📍 {{ propertyAddress }}</p>
    </div>

    <!-- 第二行：6 POI 分类 Tabs -->
    <div class="poi-tabs">
      <button
        v-for="cat in categories"
        :key="cat.key"
        class="poi-tab"
        :class="{ active: activeCategory === cat.key }"
        :disabled="loading"
        @click="switchCategory(cat.key)"
      >
        <span class="poi-tab-emoji">{{ cat.emoji }}</span>
        <span class="poi-tab-label">{{ cat.label }}</span>
      </button>
    </div>

    <!-- 地图 + 右侧 POI 列表 -->
    <div class="map-body">
      <div class="map-area" ref="mapContainer">
        <div v-if="loading" class="map-loading-overlay">
          <el-icon class="is-loading" :size="28"><Loading /></el-icon>
        </div>
      </div>

      <!-- 左下角地图控件：缩放 +/- + 回房源 -->
      <div class="map-controls">
        <button class="map-ctrl-btn" @click="zoomIn" title="放大">＋</button>
        <button class="map-ctrl-btn" @click="zoomOut" title="缩小">－</button>
        <button class="map-ctrl-btn map-ctrl-home" @click="resetView" title="回到房源位置">🏠</button>
      </div>

      <!-- 右下角地图商标 -->
      <div class="map-attribution">© OpenStreetMap contributors</div>

      <!-- 右侧 POI 列表 / 学校搜索结果 -->
      <div class="poi-sidebar" v-if="sidebarMode === 'poi' && currentPOIs.length > 0">
        <!-- 学校搜索框（仅大学 tab 显示） -->
        <div v-if="activeCategory === 'school'" class="school-search-box">
          <el-input
            v-model="schoolSearchQuery"
            placeholder="搜索学校名称..."
            size="small"
            clearable
            @input="onSchoolSearchInput"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        <div class="poi-sidebar-header">
          {{ activeCatLabel }} <span class="poi-count">{{ currentPOIs.length }}</span>
        </div>
        <div class="poi-sidebar-list">
          <div
            v-for="poi in currentPOIs"
            :key="poi.id"
            class="poi-item"
            :class="{ 'poi-item-active': selectedPoiId === poi.id }"
            @click="selectPoi(poi)"
          >
            <span class="poi-item-icon">{{ activeCatEmoji }}</span>
            <div class="poi-item-info">
              <span class="poi-item-name">{{ poi.name }}</span>
              <span v-if="poi.line" class="poi-item-line">{{ poi.line }}</span>
            </div>
            <span class="poi-item-dist">{{ formatDist(poi.distance) }}</span>
          </div>
        </div>
      </div>

      <!-- 学校搜索结果 -->
      <div class="poi-sidebar" v-else-if="sidebarMode === 'search'">
        <div class="school-search-box">
          <el-input
            v-model="schoolSearchQuery"
            placeholder="搜索学校名称..."
            size="small"
            clearable
            @input="onSchoolSearchInput"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        <div class="poi-sidebar-header">
          搜索结果 <span class="poi-count">{{ schoolSearchResults.length }}</span>
        </div>
        <div class="poi-sidebar-list" v-loading="schoolSearchLoading">
          <div v-if="schoolSearchResults.length === 0 && !schoolSearchLoading" class="poi-sidebar-empty" style="border:none;width:auto">
            未找到匹配学校
          </div>
          <div
            v-for="school in schoolSearchResults"
            :key="'s-' + school.id"
            class="poi-item"
            @click="selectSchoolResult(school)"
          >
            <span class="poi-item-icon">🎓</span>
            <div class="poi-item-info">
              <span class="poi-item-name">{{ school.name_cn || school.name }}</span>
              <span v-if="school.abbreviation" class="poi-item-line">{{ school.abbreviation }}</span>
            </div>
            <span class="poi-item-dist">{{ school.count }}套</span>
          </div>
        </div>
      </div>

      <div v-else-if="!loading && activeCategory" class="poi-sidebar-empty">
        附近暂无{{ activeCatLabel }}
      </div>
      <div v-else-if="!loading" class="poi-sidebar-empty poi-sidebar-hint">
        👆 点击上方标签查看周边设施
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { Loading, Search } from '@element-plus/icons-vue'
import { metersToKm, type OverpassPOI } from '@/services/overpass'
import { loadOSMTiles, type TileHandle } from '@/services/tileDetector'
import { propertyService, type MapPOIItem } from '@/services/property'
import api from '@/services/api'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

// 修复 Leaflet 默认图标路径
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

// ── Props ──
const props = defineProps<{
  propertyId: number
  propertyLat: number
  propertyLng: number
  propertyTitle: string
  propertyAddress: string
  country?: string | null
}>()

const hasCoords = !isNaN(props.propertyLat) && !isNaN(props.propertyLng)

// ── 颜色 ──
const PROPERTY_COLOR = '#EF4444'  // 红色 ── 房源
const POI_COLOR      = '#3DA5A0'  // 青石绿 ── 周边设施

// ── POI 分类 ──
interface CatDef { key: string; label: string; emoji: string }
const categories: CatDef[] = [
  { key: 'school',          label: '大学',     emoji: '🎓' },
  { key: 'bus_station',     label: '公交车站', emoji: '🚌' },
  { key: 'subway_station',  label: '地铁站',   emoji: '🚇' },
  { key: 'supermarket',     label: '超市',     emoji: '🛒' },
  { key: 'restaurant',      label: '餐厅',     emoji: '🍽️' },
  { key: 'pharmacy',        label: '药房',     emoji: '💊' },
]

const activeCategory = ref('')
const currentPOIs = ref<OverpassPOI[]>([])
const loading = ref(false)

// 从后端预生成的 POI 数据（全部 6 大类），客户端筛选
const allMapPOIs = ref<Record<string, MapPOIItem[]>>({})
const mapPOIsLoaded = ref(false)

const activeCatLabel = computed(() => categories.find(c => c.key === activeCategory.value)?.label || '')
const activeCatEmoji = computed(() => categories.find(c => c.key === activeCategory.value)?.emoji || '')

// ── 学校搜索 ──
interface SchoolSearchResult {
  id: number
  name: string
  name_cn: string | null
  abbreviation: string | null
  latitude: number | null
  longitude: number | null
  count: number
}

const schoolSearchQuery = ref('')
const schoolSearchResults = ref<SchoolSearchResult[]>([])
const schoolSearchLoading = ref(false)
let schoolSearchTimer: ReturnType<typeof setTimeout> | null = null

/** 侧边栏当前显示模式：'poi' 显示视口 POI，'search' 显示学校搜索结果 */
const sidebarMode = computed<'poi' | 'search'>(() => {
  if (activeCategory.value === 'school' && schoolSearchQuery.value.trim()) {
    return 'search'
  }
  return 'poi'
})

function onSchoolSearchInput() {
  if (schoolSearchTimer) clearTimeout(schoolSearchTimer)
  const q = schoolSearchQuery.value.trim()
  if (!q) {
    schoolSearchResults.value = []
    return
  }
  schoolSearchTimer = setTimeout(() => fetchSchoolSearch(q), 300)
}

async function fetchSchoolSearch(q: string) {
  schoolSearchLoading.value = true
  try {
    const resp = await api.get('/search/suggestions', { params: { q, limit: 10 } })
    schoolSearchResults.value = resp.data.matching_schools || []
  } catch {
    schoolSearchResults.value = []
  } finally {
    schoolSearchLoading.value = false
  }
}

/** 点击搜索结果 → 飞到学校位置 */
function selectSchoolResult(school: SchoolSearchResult) {
  if (!map || school.latitude == null || school.longitude == null) return

  // 在目标位置放一个临时高亮标记
  const tempIcon = L.divIcon({
    className: 'custom-poi-icon',
    html: `<div style="
      background:#FF6B35;width:40px;height:40px;
      border-radius:50%;border:4px solid #fff;
      box-shadow:0 4px 16px rgba(255,107,53,0.5);
      display:flex;align-items:center;justify-content:center;
      font-size:20px;line-height:1;
      animation: poiBounce 0.5s ease-out;
    ">🎓</div>`,
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    popupAnchor: [0, -20],
  })

  const tempMarker = L.marker([school.latitude, school.longitude], { icon: tempIcon })
    .bindTooltip(school.name_cn || school.name, {
      permanent: true,
      direction: 'bottom',
      offset: [0, 24],
      className: 'poi-highlight-label',
    })
    .addTo(map)

  map.flyTo([school.latitude, school.longitude], 15, { duration: 0.8 })

  // 3 秒后移除临时标记
  setTimeout(() => {
    if (map) map.removeLayer(tempMarker)
  }, 5000)
}

// ── divIcon 工厂 ──
function makeDivIcon(emoji: string, bg: string, size: number): L.DivIcon {
  return L.divIcon({
    className: 'custom-poi-icon',
    html: `<div style="
      background:${bg};width:${size}px;height:${size}px;
      border-radius:50%;border:3px solid #fff;
      box-shadow:0 2px 6px rgba(0,0,0,0.3);
      display:flex;align-items:center;justify-content:center;
      font-size:${size * 0.5}px;line-height:1;
    ">${emoji}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  })
}

const propIcon = makeDivIcon('🏠', PROPERTY_COLOR, 36)
function poiIcon() { return makeDivIcon(activeCatEmoji.value, POI_COLOR, 28) }

// 高亮态图标（放大 + CSS bounce 动画）
function highlightedPoiIcon(): L.DivIcon {
  const emoji = activeCatEmoji.value
  return L.divIcon({
    className: 'custom-poi-icon poi-icon-bounce',
    html: `<div style="
      background:${POI_COLOR};width:44px;height:44px;
      border-radius:50%;border:3px solid #fff;
      box-shadow:0 4px 14px rgba(0,0,0,0.4);
      display:flex;align-items:center;justify-content:center;
      font-size:22px;line-height:1;
      animation: poiBounce 0.5s ease-out;
    ">${emoji}</div>`,
    iconSize: [44, 44],
    iconAnchor: [22, 22],
    popupAnchor: [0, -22],
  })
}

// ── Leaflet ──
const mapContainer = ref<HTMLElement | null>(null)
let map: L.Map | null = null
let tileHandle: TileHandle | null = null
let ready = false
let propMarker: L.Marker | null = null

// POI id → marker 映射（用于侧栏点击时定位并高亮对应标记）
const poiMarkerMap = new Map<number, L.Marker>()
// 当前选中的 POI id
const selectedPoiId = ref<number | null>(null)
// 上一个被高亮的标记（用于恢复）
let prevHighlighted: L.Marker | null = null


// 地图移动防抖定时器
let moveTimer: ReturnType<typeof setTimeout> | null = null

function initMap() {
  if (!mapContainer.value || ready) return
  map = L.map(mapContainer.value, {
    zoomControl: false,
    attributionControl: false,
  }).setView([props.propertyLat, props.propertyLng], 15)

  // 全球统一 OSM 瓦片，事件驱动回退（tileerror → 法国镜像）
  tileHandle = loadOSMTiles(map)

  propMarker = L.marker([props.propertyLat, props.propertyLng], { icon: propIcon })
    .bindTooltip(props.propertyTitle, { direction: 'top', offset: [0, -22] })
    .addTo(map)

  // 视口变化时本地筛选 POI（150ms 防抖，即时响应，零网络请求）
  map.on('moveend', onMapMoveEnd)

  // 确保容器尺寸正确后再刷新地图
  setTimeout(() => {
    map?.invalidateSize()
  }, 200)

  ready = true
}

function clearPOIs() {
  poiMarkerMap.forEach(m => map!.removeLayer(m))
  poiMarkerMap.clear()
  restoreHighlighted()
  selectedPoiId.value = null
}

function renderPOIs(pois: OverpassPOI[]) {
  if (!map || !ready) return
  clearPOIs()
  const icon = poiIcon()
  for (const p of pois) {
    const m = L.marker([p.lat, p.lng], { icon })
      .bindTooltip(p.name, { direction: 'top', offset: [0, -18] })
      .addTo(map)
    poiMarkerMap.set(p.id, m)
  }
}

function zoomIn()  { map?.zoomIn() }
function zoomOut() { map?.zoomOut() }
function resetView() {
  map?.setView([props.propertyLat, props.propertyLng], 15, { animate: true })
  // 回到房源位置后，若有已选分类则重新筛选当前视野
  if (activeCategory.value) {
    setTimeout(() => filterLocalPOIs(), 400) // 等动画结束
  }
}

// ── POI 选中 → 地图标记弹跳 + 放大 + 显示名称 ──

/** 恢复上一个高亮标记为普通状态 */
function restoreHighlighted() {
  if (!prevHighlighted || !map) return
  try {
    prevHighlighted.setIcon(poiIcon())
    prevHighlighted.unbindTooltip()
    prevHighlighted.bindTooltip(
      (prevHighlighted as any)._poiName || '',
      { direction: 'top', offset: [0, -18] },
    )
  } catch { /* marker may have been removed */ }
  prevHighlighted = null
}

/** 侧栏点击 POI → 飞行到位置 + 高亮对应标记 */
function selectPoi(poi: OverpassPOI) {
  if (!map) return

  // 恢复上一个
  restoreHighlighted()

  // 选中状态
  selectedPoiId.value = poi.id

  // 飞行到 POI 位置
  map.flyTo([poi.lat, poi.lng], Math.max(map.getZoom(), 16), { duration: 0.7 })

  // 等飞行动画结束后高亮标记
  setTimeout(() => {
    const marker = poiMarkerMap.get(poi.id)
    if (!marker || !map || selectedPoiId.value !== poi.id) return

    // 保存原始名称以便恢复
    ;(marker as any)._poiName = poi.name

    // 移除旧 tooltip，换大图标
    marker.unbindTooltip()
    marker.setIcon(highlightedPoiIcon())

    // 永久显示名称标签在图标下方
    marker.bindTooltip(poi.name, {
      permanent: true,
      direction: 'bottom',
      offset: [0, 28],
      className: 'poi-highlight-label',
    })
    marker.openTooltip()

    prevHighlighted = marker
  }, 500) // 等待 flyTo 动画接近完成
}

// ── 分类切换 ──
async function switchCategory(key: string) {
  if (loading.value) return
  if (activeCategory.value === key) {
    activeCategory.value = ''
    currentPOIs.value = []
    clearPOIs()
    return
  }
  activeCategory.value = key
  filterLocalPOIs()
}

/** 从本地预生成数据中按视野筛选（零网络请求） */
function filterLocalPOIs() {
  if (!activeCategory.value || !map) return
  loading.value = true
  currentPOIs.value = []

  // 延迟一帧让 UI 响应，避免阻塞
  requestAnimationFrame(() => {
    try {
      const catPOIs = allMapPOIs.value[activeCategory.value] || []
      if (catPOIs.length === 0) {
        currentPOIs.value = []
        clearPOIs()
        return
      }

      const bounds = map!.getBounds()
      // 视野内 + 搜索半径内双重过滤
      const inView: OverpassPOI[] = []
      for (const p of catPOIs) {
        if (bounds.contains(L.latLng(p.lat, p.lng))) {
          inView.push({
            id: typeof p.id === 'string' ? parseInt(p.id) || Math.random() * 1e8 : p.id,
            lat: p.lat,
            lng: p.lng,
            name: p.name,
            distance: p.distance ?? undefined,
            line: p.line ?? undefined,
          })
        }
      }
      currentPOIs.value = inView.sort((a, b) => (a.distance ?? 0) - (b.distance ?? 0))
      renderPOIs(currentPOIs.value)
    } finally {
      loading.value = false
    }
  })
}

/** 视口变化时自动刷新（本地筛选，即时响应） */
function onMapMoveEnd() {
  if (!activeCategory.value) return
  if (moveTimer) clearTimeout(moveTimer)
  moveTimer = setTimeout(() => filterLocalPOIs(), 150) // 150ms 防抖，本地筛选很快
}

// ── 从后端加载预生成 POI ──

async function loadAllMapPOIs() {
  try {
    const data = await propertyService.getMapPOIs(props.propertyId)
    if (data && data.categories) {
      allMapPOIs.value = data.categories
      mapPOIsLoaded.value = true
      return
    }
  } catch {
    // 后端数据不可用，回退到前端直接调 API（兼容存量房源未预生成的情况）
  }

  // 回退：首次访问时后端实时生成并返回，重试一次
  try {
    const data = await propertyService.getMapPOIs(props.propertyId)
    if (data && data.categories) {
      allMapPOIs.value = data.categories
      mapPOIsLoaded.value = true
      return
    }
  } catch {
    mapPOIsLoaded.value = false
  }
}

function formatDist(m?: number) { return m != null ? metersToKm(m) : '' }

// ── 生命周期 ──
onMounted(() => {
  nextTick(() => {
    initMap()
    loadAllMapPOIs()
  })
})
onUnmounted(() => {
  if (moveTimer) clearTimeout(moveTimer)
  if (schoolSearchTimer) clearTimeout(schoolSearchTimer)
  tileHandle?.destroy()
  if (map) { map.remove(); map = null; ready = false }
})
</script>

<style scoped>
.property-map-card { margin-bottom: 16px; }

/* ── 头部 ── */
.map-header { margin-bottom: 12px; }
.map-property-name { font-size: 16px; font-weight: 700; color: var(--text-primary); margin: 0 0 4px; }
.map-property-address { font-size: 13px; color: var(--text-secondary); margin: 0; }

/* ── Tabs ── */
.poi-tabs { display: flex; gap: 0; margin-bottom: 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; }
.poi-tab {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 4px;
  padding: 8px 2px; border: none; border-right: 1px solid var(--border-light);
  background: var(--bg-white); cursor: pointer; font-size: 12px;
  color: var(--text-secondary); transition: all 0.15s;
}
.poi-tab:last-child { border-right: none; }
.poi-tab:hover:not(:disabled) { background: var(--primary-light); color: var(--primary); }
.poi-tab.active { background: var(--primary); color: #fff; }
.poi-tab:disabled { opacity: 0.6; cursor: not-allowed; }
.poi-tab-emoji { font-size: 15px; }
.poi-tab-label { font-weight: 500; }

/* ── 地图 + 侧栏 ── */
.map-body { display: flex; gap: 0; height: 370px; border-radius: var(--radius); overflow: hidden; border: 1px solid var(--border); position: relative; }
.map-area { flex: 1; position: relative; min-width: 0; }
.map-loading-overlay {
  position: absolute; inset: 0; background: rgba(255,255,255,0.6);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
  font-size: 28px; color: var(--primary);
}

/* ── 左下角控件 ── */
.map-controls {
  position: absolute; left: 10px; bottom: 10px;
  display: flex; flex-direction: column; gap: 4px; z-index: 800;
}
.map-ctrl-btn {
  width: 32px; height: 32px; background: var(--bg-white);
  border: 1px solid var(--border); border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; font-size: 16px; font-weight: 600;
  color: var(--text-primary); box-shadow: var(--shadow-sm);
  transition: all 0.15s; padding: 0; line-height: 1;
}
.map-ctrl-btn:hover { background: var(--primary-light); border-color: var(--primary); color: var(--primary); }
.map-ctrl-home { font-size: 15px; }

/* ── 学校搜索框 ── */
.school-search-box { padding: 8px 10px; border-bottom: 1px solid var(--border-light); }

/* ── 右侧 POI 列表 ── */
.poi-sidebar { width: 220px; flex-shrink: 0; display: flex; flex-direction: column; border-left: 1px solid var(--border); background: var(--bg-white); }
.poi-sidebar-header {
  font-size: 13px; font-weight: 600; color: var(--text-primary);
  padding: 10px 12px; border-bottom: 1px solid var(--border-light);
  display: flex; align-items: center; justify-content: space-between;
}
.poi-count { font-size: 11px; color: var(--text-muted); background: var(--bg); padding: 1px 8px; border-radius: 10px; }
.poi-sidebar-list { flex: 1; overflow-y: auto; padding: 4px 0; }
.poi-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  cursor: pointer; transition: background 0.15s;
  border-bottom: 1px solid var(--border-light);
}
.poi-item:last-child { border-bottom: none; }
.poi-item:hover { background: var(--primary-light); }
.poi-item-icon { font-size: 16px; flex-shrink: 0; }
.poi-item-info { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.poi-item-name { font-size: 12px; color: var(--text-primary); font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.poi-item-line { font-size: 10px; color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.poi-item-dist { font-size: 11px; color: var(--text-muted); flex-shrink: 0; }
.poi-sidebar-empty, .poi-sidebar-hint {
  width: 220px; flex-shrink: 0; display: flex; align-items: center; justify-content: center;
  font-size: 13px; color: var(--text-muted); border-left: 1px solid var(--border); background: var(--bg-white);
}
.poi-sidebar-hint { color: #c0c4cc; font-size: 12px; }

/* ── POI 列表项选中态 ── */
.poi-item-active {
  background: var(--primary-light) !important;
  border-left: 3px solid var(--primary);
  padding-left: 9px !important; /* 12px - 3px border */
}

/* ── POI 图标弹跳动画 ── */
@keyframes poiBounce {
  0%   { transform: scale(0.6); opacity: 0.5; }
  40%  { transform: scale(1.4); }
  60%  { transform: scale(0.85); }
  80%  { transform: scale(1.1); }
  100% { transform: scale(1); }
}

/* ── 高亮 POI 名称标签（图标下方，不重叠）── */
:deep(.poi-highlight-label) {
  font-size: 12px !important;
  font-weight: 600 !important;
  color: #333 !important;
  background: rgba(255, 255, 255, 0.92) !important;
  border: 1px solid var(--border) !important;
  border-radius: 4px !important;
  padding: 2px 8px !important;
  white-space: nowrap !important;
  box-shadow: 0 1px 4px rgba(0,0,0,0.12) !important;
}

/* 移除 Leaflet 默认 tooltip 小三角（与标签风格统一） */
:deep(.poi-highlight-label::before) {
  display: none !important;
}

/* ── 地图商标（右下角）── */
.map-attribution {
  position: absolute;
  right: 6px;
  bottom: 4px;
  z-index: 800;
  font-size: 10px;
  color: #666;
  background: rgba(255, 255, 255, 0.8);
  padding: 1px 6px;
  border-radius: 3px;
  pointer-events: none;
  user-select: none;
  line-height: 1.6;
}
</style>
