<template>
  <div class="map-page">
    <!-- 搜索栏 -->
    <div class="map-search-bar">
      <el-input
        v-model="searchText"
        placeholder="输入国家/城市名，快速定位… 例如：北京、东京、Paris"
        size="large"
        clearable
        @keyup.enter="searchLocation"
        class="search-input"
      >
        <template #prefix>🔍</template>
      </el-input>
      <el-button type="primary" size="large" @click="searchLocation">搜索</el-button>
      <el-button size="large" @click="resetMap">🌍 世界视图</el-button>
    </div>

    <!-- 地图主体 -->
    <div class="map-container">
      <div id="map" class="map-box"></div>

      <!-- 房源数量提示 -->
      <div class="map-stats" v-if="filteredProperties.length > 0">
        当前区域 {{ filteredProperties.length }} 套房源
        <el-button size="small" text type="primary" @click="showList = !showList">
          {{ showList ? '收起列表' : '展开列表' }}
        </el-button>
      </div>

      <!-- 侧边列表 -->
      <transition name="slide">
        <div v-if="showList && filteredProperties.length > 0" class="property-drawer">
          <div v-for="p in filteredProperties" :key="p.id" class="drawer-item" @click="flyToProperty(p)">
            <div class="drawer-img" v-if="p.images?.length">
              <img :src="`/api/v1/uploads/${p.images[0].filename}`" />
            </div>
            <div class="drawer-info">
              <span class="drawer-title">{{ p.title }}</span>
              <span class="drawer-addr">📍 {{ p.district }} · {{ p.address }}</span>
              <span class="drawer-price">¥{{ numberFormat(p.price_monthly) }}/月 · {{ p.bedrooms }}室{{ p.bathrooms }}卫</span>
            </div>
          </div>
        </div>
      </transition>
    </div>

    <!-- 房源弹窗模板（Leaflet 用） -->
    <div style="display:none">
      <div v-for="p in allProperties" :key="p.id" :id="'popup-' + p.id" class="map-popup">
        <h4>{{ p.title }}</h4>
        <p class="popup-addr">📍 {{ p.district }} · {{ p.address }}</p>
        <p class="popup-price">¥{{ numberFormat(p.price_monthly) }}/月 · {{ p.bedrooms }}室{{ p.bathrooms }}卫</p>
        <a :href="'/property/' + p.id" class="popup-link">查看详情 →</a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch, shallowRef, markRaw } from 'vue'
import { ElMessage } from 'element-plus'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { propertyService } from '@/services/property'
import type { Property } from '@/types/property'

// 修复 Leaflet 默认图标在 Vite 中不显示的问题
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
})

const searchText = ref('')
const showList = ref(true)
const allProperties = ref<Property[]>([])
const map = shallowRef<L.Map | null>(null)
const markers = shallowRef<L.Marker[]>([])

// 默认视图：北京为中心
const defaultCenter: [number, number] = [39.9042, 116.4074]
const defaultZoom = 5

const filteredProperties = computed(() => allProperties.value)

function numberFormat(n: number) {
  return n?.toLocaleString('zh-CN') || '0'
}

async function loadProperties() {
  try {
    allProperties.value = await propertyService.list({ limit: 200 })
  } catch {
    allProperties.value = []
  }
}

function initMap() {
  if (map.value) return

  map.value = markRaw(L.map('map', {
    center: defaultCenter,
    zoom: defaultZoom,
    zoomControl: true,
  }))

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 18,
  }).addTo(map.value)

  // 强制重新计算尺寸
  setTimeout(() => map.value?.invalidateSize(), 100)

  // 放置标记
  placeMarkers()
}

function placeMarkers() {
  if (!map.value) return
  markers.value.forEach(m => m.remove())
  markers.value = []

  const propWithCoords = allProperties.value.filter((p: any) => p.latitude && p.longitude)

  propWithCoords.forEach((p: any) => {
    const lat = Number(p.latitude)
    const lng = Number(p.longitude)
    if (isNaN(lat) || isNaN(lng)) return

    const popupContent = document.getElementById('popup-' + p.id)?.innerHTML || `
      <h4>${p.title}</h4>
      <p>${p.district} · ${p.address}</p>
      <p>¥${numberFormat(p.price_monthly)}/月</p>
      <a href="/property/${p.id}">查看详情 →</a>
    `

    const marker = markRaw(L.marker([lat, lng])
      .addTo(map.value!)
      .bindPopup(popupContent, { maxWidth: 280 }))

    markers.value.push(marker)
  })

  if (propWithCoords.length > 0 && map.value) {
    try {
      const group = L.featureGroup(markers.value)
      map.value.fitBounds(group.getBounds().pad(0.1))
    } catch { /* ignore */ }
  }
}

async function searchLocation() {
  const q = searchText.value.trim()
  if (!q) { ElMessage.warning('请输入城市或国家名'); return }

  try {
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q)}&limit=1`
    const resp = await fetch(url)
    const data = await resp.json()
    if (data.length > 0) {
      const { lat, lon } = data[0]
      map.value?.flyTo([Number(lat), Number(lon)], 12, { duration: 1.5 })
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
  map.value?.flyTo(defaultCenter, defaultZoom, { duration: 1 })
}

function flyToProperty(p: any) {
  const lat = Number(p.latitude)
  const lng = Number(p.longitude)
  if (!isNaN(lat) && !isNaN(lng)) {
    map.value?.flyTo([lat, lng], 15, { duration: 1 })
  }
}

watch(allProperties, () => {
  nextTick(() => {
    if (map.value) placeMarkers()
  })
})

onMounted(async () => {
  await loadProperties()
  nextTick(() => initMap())
})
</script>

<style scoped>
.map-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px - 48px);
  margin: -24px;
}

.map-search-bar {
  display: flex;
  gap: 10px;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid var(--border);
  z-index: 10;
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  max-width: 460px;
}

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

.map-stats {
  position: absolute;
  top: 12px;
  right: 12px;
  background: #fff;
  padding: 8px 16px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
  z-index: 1000;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.property-drawer {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  max-height: 240px;
  overflow-y: auto;
  background: #fff;
  border-top: 2px solid var(--border);
  z-index: 999;
  display: flex;
  flex-direction: column;
}

.drawer-item {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
  transition: background 0.15s;
}

.drawer-item:hover {
  background: var(--primary-light);
}

.drawer-img {
  width: 80px;
  height: 60px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
}

.drawer-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.drawer-info {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3px;
}

.drawer-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.drawer-addr {
  font-size: 12px;
  color: var(--text-muted);
}

.drawer-price {
  font-size: 13px;
  color: var(--danger);
  font-weight: 600;
}

.slide-enter-active, .slide-leave-active {
  transition: all 0.3s ease;
}
.slide-enter-from, .slide-leave-to {
  max-height: 0;
  opacity: 0;
}

/* Leaflet popup 样式 */
:deep(.leaflet-popup-content) {
  font-family: inherit;
  margin: 10px 14px;
}
:deep(.map-popup h4) {
  margin: 0 0 6px;
  font-size: 15px;
  color: #303133;
}
:deep(.popup-addr) {
  margin: 0 0 4px;
  font-size: 12px;
  color: #909399;
}
:deep(.popup-price) {
  margin: 0 0 6px;
  font-size: 14px;
  color: #f56c6c;
  font-weight: 700;
}
:deep(.popup-link) {
  color: #409eff;
  font-weight: 600;
  text-decoration: none;
  font-size: 13px;
}
</style>
