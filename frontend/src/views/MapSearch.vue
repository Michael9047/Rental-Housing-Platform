<template>
  <div class="map-page">
    <!-- 搜索栏 -->
    <div class="map-search-bar">
      <el-input
        v-model="searchText"
        placeholder="输入城市名快速定位，例如：北京、上海、东京、Paris"
        size="large"
        clearable
        @keyup.enter="searchLocation"
        class="search-input"
      >
        <template #prefix>🔍</template>
      </el-input>
      <el-button type="primary" size="large" @click="searchLocation">搜索</el-button>
      <el-button size="large" @click="resetMap">🌍 全国视图</el-button>
      <el-select v-model="mapCountry" placeholder="选择国家" size="large" style="width: 150px" clearable @change="onCountryFilterChange">
        <el-option label="🇨🇳 中国大陆" value="CN" />
        <el-option label="🇸🇬 新加坡" value="SG" />
        <el-option label="🇬🇧 英国" value="GB" />
        <el-option label="🇺🇸 美国" value="US" />
        <el-option label="🇦🇺 澳大利亚" value="AU" />
      </el-select>
      <el-tag v-if="loading" type="warning" size="large" class="loading-tag">加载中...</el-tag>
    </div>

    <!-- 地图主体 -->
    <div class="map-container">
      <div id="map" class="map-box"></div>

      <!-- 房源统计 & 展开按钮 -->
      <div class="map-stats" v-if="viewportProperties.length > 0">
        <span>当前区域 <strong>{{ viewportProperties.length }}</strong> 套房源</span>
        <el-button size="small" text type="primary" @click="showList = !showList">
          {{ showList ? '收起列表 ▲' : '展开列表 ▼' }}
        </el-button>
      </div>

      <!-- 无结果提示 -->
      <div class="map-stats empty" v-if="!loading && viewportProperties.length === 0">
        <span>当前区域暂无房源，试试缩小地图或移动位置</span>
      </div>

      <!-- 侧边列表 -->
      <transition name="slide">
        <div v-if="showList && viewportProperties.length > 0" class="property-drawer">
          <div
            v-for="p in viewportProperties"
            :key="p.id"
            class="drawer-item"
            @click="flyToProperty(p)"
          >
            <div class="drawer-img">
              <img
                v-if="p.primary_image_url"
                :src="p.primary_image_url"
                alt=""
              />
              <div v-else class="drawer-img-placeholder">🏠</div>
            </div>
            <div class="drawer-info">
              <span class="drawer-title">{{ p.title }}</span>
              <span class="drawer-addr">📍 {{ p.district }} · {{ p.address }}</span>
              <span class="drawer-price">
                ¥{{ numberFormat(p.price_monthly) }}/月 · {{ p.bedrooms }}室{{ p.bathrooms }}卫
              </span>
            </div>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { mapService } from '@/services/map'
import type { MapProperty, MapBounds } from '@/services/map'

// ==================== 修复 Leaflet 默认图标 ====================
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
})

// ==================== 状态 ====================
const searchText = ref('')
const showList = ref(true)
const loading = ref(false)
const mapCountry = ref<string | undefined>(undefined)
const viewportProperties = ref<MapProperty[]>([])

let map: L.Map | null = null
let markerLayer = L.layerGroup()
let clusterLayer = L.layerGroup()
let debounceTimer: ReturnType<typeof setTimeout> | null = null

// 默认中心：北京
const defaultCenter: [number, number] = [39.9042, 116.4074]
const defaultZoom = 5

// ==================== 工具函数 ====================
function numberFormat(n: number) {
  return n?.toLocaleString('zh-CN') || '0'
}

/** 从地图获取带 padding 的 bounds */
function getPaddedBounds(paddingRatio = 0.2): MapBounds {
  if (!map) {
    return { sw_lat: 18, sw_lng: 73, ne_lat: 54, ne_lng: 135 }
  }
  const b = map.getBounds()
  const latPad = (b.getNorth() - b.getSouth()) * paddingRatio
  const lngPad = (b.getEast() - b.getWest()) * paddingRatio
  return {
    sw_lat: Math.max(-90, b.getSouth() - latPad),
    sw_lng: Math.max(-180, b.getWest() - lngPad),
    ne_lat: Math.min(90, b.getNorth() + latPad),
    ne_lng: Math.min(180, b.getEast() + lngPad),
  }
}

// ==================== 数据加载 ====================
async function loadPropertiesInViewport() {
  if (!map) return
  loading.value = true
  try {
    const bounds = getPaddedBounds()
    const res = await mapService.getPropertiesInBounds(bounds, mapCountry.value)
    viewportProperties.value = res.items
  } catch {
    viewportProperties.value = []
  } finally {
    loading.value = false
    nextTick(() => renderMarkers())
  }
}

/** 防抖版加载 */
function debouncedLoad() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    loadPropertiesInViewport()
  }, 300)
}

// ==================== 标记渲染（含手动聚合） ====================
function renderMarkers() {
  if (!map) return

  markerLayer.clearLayers()
  clusterLayer.clearLayers()

  const props = viewportProperties.value.filter(
    (p) => p.latitude != null && p.longitude != null
  )
  if (props.length === 0) return

  const zoom = map.getZoom()

  // 缩放 >= 13 显示独立标记，< 13 显示聚合点
  if (zoom >= 13) {
    renderIndividualMarkers(props)
  } else {
    renderClusteredMarkers(props, zoom)
  }
}

/** 独立标记 */
function renderIndividualMarkers(props: MapProperty[]) {
  props.forEach((p) => {
    const lat = Number(p.latitude)
    const lng = Number(p.longitude)
    if (isNaN(lat) || isNaN(lng)) return

    const el = L.marker([lat, lng])
      .bindPopup(buildPopupContent(p), { maxWidth: 260 })

    el.on('click', () => {
      el.openPopup()
    })

    markerLayer.addLayer(el)
  })
  markerLayer.addTo(map!)
}

/** 聚合标记（手动网格聚合） */
function renderClusteredMarkers(props: MapProperty[], zoom: number) {
  if (!map) return

  // 根据缩放级别动态计算网格大小（经纬度度数）
  // zoom 5 → ~2° 一格，zoom 12 → ~0.05° 一格
  const gridSize = Math.max(0.02, 2 / Math.pow(2, zoom - 5))

  // 按网格分组
  const groups = new Map<string, MapProperty[]>()
  props.forEach((p) => {
    const lat = Number(p.latitude)
    const lng = Number(p.longitude)
    if (isNaN(lat) || isNaN(lng)) return

    const row = Math.floor(lat / gridSize)
    const col = Math.floor(lng / gridSize)
    const key = `${row}_${col}`
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(p)
  })

  groups.forEach((group, _key) => {
    if (group.length === 1) {
      // 单个房源：直接显示标记
      const p = group[0]
      const m = L.marker([Number(p.latitude), Number(p.longitude)])
        .bindPopup(buildPopupContent(p), { maxWidth: 260 })
      clusterLayer.addLayer(m)
    } else {
      // 多个房源：显示聚合点
      const centerLat = group.reduce((s, p) => s + Number(p.latitude), 0) / group.length
      const centerLng = group.reduce((s, p) => s + Number(p.longitude), 0) / group.length
      // 计算价格范围
      const prices = group.map((p) => p.price_monthly)
      const minPrice = Math.min(...prices)
      const maxPrice = Math.max(...prices)

      const clusterIcon = L.divIcon({
        className: 'cluster-icon-wrapper',
        html: `<div class="cluster-icon" style="--size:${getClusterSize(group.length)}px">
          <span class="cluster-count">${group.length}</span>
          <span class="cluster-price">¥${numberFormat(minPrice)}~${numberFormat(maxPrice)}</span>
        </div>`,
        iconSize: [getClusterSize(group.length), getClusterSize(group.length)],
        iconAnchor: [getClusterSize(group.length) / 2, getClusterSize(group.length) / 2],
      })

      const m = L.marker([centerLat, centerLng], { icon: clusterIcon })
      m.on('click', () => {
        // 点击聚合点：放大到该区域
        const pad = gridSize * 2
        map?.flyToBounds(
          L.latLngBounds(
            [centerLat - pad, centerLng - pad],
            [centerLat + pad, centerLng + pad]
          ),
          { duration: 0.6 }
        )
      })
      clusterLayer.addLayer(m)
    }
  })

  clusterLayer.addTo(map)
}

/** 聚合图标大小：10~60 之间按数量缩放 */
function getClusterSize(count: number): number {
  return Math.min(70, Math.max(40, 30 + Math.log2(count) * 8))
}

/** 弹窗内容 */
function buildPopupContent(p: MapProperty): string {
  return `
    <div class="map-popup">
      <h4>${escapeHtml(p.title)}</h4>
      <p class="popup-addr">📍 ${escapeHtml(p.district)} · ${escapeHtml(p.address)}</p>
      <p class="popup-price">¥${numberFormat(p.price_monthly)}/月 · ${p.bedrooms}室${p.bathrooms}卫</p>
      <a href="/property/${p.id}" class="popup-link">查看详情 →</a>
    </div>
  `
}

function escapeHtml(str: string): string {
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}

// ==================== 位置搜索 ====================
async function onCountryFilterChange() {
  loadPropertiesInViewport()
}

async function searchLocation() {
  const q = searchText.value.trim()
  if (!q) {
    ElMessage.warning('请输入城市或国家名称')
    return
  }

  try {
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q)}&limit=1`
    const resp = await fetch(url)
    const data = await resp.json()
    if (data.length > 0) {
      const { lat, lon } = data[0]
      const zoom = data[0].type === 'city' || data[0].type === 'administrative' ? 12 : 14
      map?.flyTo([Number(lat), Number(lon)], zoom, { duration: 1.5 })
      ElMessage.success(`已定位到 ${data[0].display_name}`)
    } else {
      ElMessage.warning('未找到该位置，请换个关键词试试')
    }
  } catch {
    ElMessage.error('搜索失败，请检查网络')
  }
}

function resetMap() {
  searchText.value = ''
  map?.flyTo(defaultCenter, defaultZoom, { duration: 1 })
}

function flyToProperty(p: MapProperty) {
  const lat = Number(p.latitude)
  const lng = Number(p.longitude)
  if (!isNaN(lat) && !isNaN(lng)) {
    map?.flyTo([lat, lng], 16, { duration: 0.8 })

    // 高亮对应标记：重新渲染以显示独立标记（zoom >= 13 时）
    if (map && map.getZoom() < 13) {
      // 先飞到位置，等动画结束再由 moveend 触发重新渲染
      map.once('moveend', () => {
        // 打开对应弹窗
        markerLayer.eachLayer((layer: any) => {
          if (layer.getLatLng) {
            const ll = layer.getLatLng()
            if (Math.abs(ll.lat - lat) < 0.0001 && Math.abs(ll.lng - lng) < 0.0001) {
              layer.openPopup()
            }
          }
        })
      })
    }
  }
}

// ==================== 地图初始化 ====================
function initMap() {
  if (map) return

  map = L.map('map', {
    center: defaultCenter,
    zoom: defaultZoom,
    zoomControl: true,
    minZoom: 3,
    maxZoom: 18,
  })

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 18,
  }).addTo(map)

  // 初始空图层
  markerLayer.addTo(map)
  clusterLayer.addTo(map)

  // 监听移动/缩放结束 → 防抖加载
  map.on('moveend', debouncedLoad)
  map.on('zoomend', debouncedLoad)

  // 强制重算尺寸
  setTimeout(() => map?.invalidateSize(), 100)

  // 初始加载
  loadPropertiesInViewport()
}

// ==================== 生命周期 ====================
onMounted(() => {
  nextTick(() => initMap())
})

onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
  map?.off('moveend', debouncedLoad)
  map?.off('zoomend', debouncedLoad)
  map?.remove()
  map = null
})
</script>

<style scoped>
.map-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px - 48px);
  margin: -24px;
}

/* ======== 顶部搜索栏 ======== */
.map-search-bar {
  display: flex;
  gap: 10px;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid var(--border, #ebeef5);
  z-index: 10;
  flex-shrink: 0;
  align-items: center;
}

.search-input {
  flex: 1;
  max-width: 420px;
}

.loading-tag {
  margin-left: 4px;
}

/* ======== 地图容器 ======== */
.map-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  min-height: 0;
}

.map-box {
  width: 100%;
  height: 100%;
  z-index: 1;
}

/* ======== 统计提示条 ======== */
.map-stats {
  position: absolute;
  top: 12px;
  right: 12px;
  background: #fff;
  padding: 8px 16px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12);
  z-index: 1000;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.map-stats.empty {
  background: #fdf6ec;
  color: #e6a23c;
  font-size: 13px;
}

/* ======== 底部侧边列表 ======== */
.property-drawer {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  max-height: 240px;
  overflow-y: auto;
  background: #fff;
  border-top: 2px solid var(--border, #ebeef5);
  z-index: 999;
  display: flex;
  flex-direction: column;
}

.drawer-item {
  display: flex;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid #f2f2f2;
  cursor: pointer;
  transition: background 0.15s;
}

.drawer-item:hover {
  background: #ecf5ff;
}

.drawer-img {
  width: 80px;
  height: 60px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
  background: #f5f5f5;
}

.drawer-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.drawer-img-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  background: #e8ecf1;
}

.drawer-info {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3px;
  min-width: 0;
}

.drawer-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drawer-addr {
  font-size: 12px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drawer-price {
  font-size: 13px;
  color: #f56c6c;
  font-weight: 600;
}

/* ======== 列表滑入动画 ======== */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.28s ease;
}

.slide-enter-from,
.slide-leave-to {
  max-height: 0;
  opacity: 0;
}

/* ======== 聚合点样式 ======== */
:deep(.cluster-icon-wrapper) {
  background: transparent !important;
  border: none !important;
}

:deep(.cluster-icon) {
  width: var(--size);
  height: var(--size);
  border-radius: 50%;
  background: linear-gradient(135deg, #409eff, #337ecc);
  color: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 10px rgba(64, 158, 255, 0.45);
  cursor: pointer;
  transition: transform 0.15s;
  font-family: inherit;
  line-height: 1.2;
}

:deep(.cluster-icon:hover) {
  transform: scale(1.12);
}

:deep(.cluster-count) {
  font-size: 14px;
  font-weight: 700;
}

:deep(.cluster-price) {
  font-size: 9px;
  opacity: 0.9;
  white-space: nowrap;
}

/* ======== 弹窗样式 ======== */
:deep(.leaflet-popup-content) {
  font-family: inherit;
  margin: 8px 12px;
  line-height: 1.5;
}

:deep(.map-popup h4) {
  margin: 0 0 4px;
  font-size: 15px;
  color: #303133;
}

:deep(.popup-addr) {
  margin: 0 0 3px;
  font-size: 12px;
  color: #909399;
}

:deep(.popup-price) {
  margin: 0 0 5px;
  font-size: 14px;
  color: #f56c6c;
  font-weight: 700;
}

:deep(.popup-link) {
  color: #409eff;
  font-weight: 600;
  text-decoration: none;
  font-size: 13px;
  display: inline-block;
  margin-top: 2px;
}
</style>





