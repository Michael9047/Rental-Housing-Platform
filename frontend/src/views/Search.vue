<template>
  <div class="search-page">
    <!-- 学校模式顶部横幅 -->
    <div v-if="searchMode === 'school' && schoolName" class="school-banner">
      <el-icon :size="22"><School /></el-icon>
      <h1>靠近 {{ schoolName }} 的房源</h1>
      <span class="school-count">{{ searchResults.length }} 套</span>
    </div>

    <div class="search-layout">
      <!-- ════════════════════════════════════════════ -->
      <!--  左侧筛选栏                                 -->
      <!-- ════════════════════════════════════════════ -->
      <aside class="filter-sidebar">
        <!-- 地图切换按钮 -->
        <el-button
          class="map-toggle-btn"
          :type="viewMode === 'map' ? 'primary' : 'default'"
          @click="viewMode = viewMode === 'map' ? 'grid' : 'map'"
        >
          <el-icon><Location /></el-icon>
          {{ viewMode === 'map' ? '收起地图' : '地图看房' }}
        </el-button>

        <div class="sidebar-title-row">
          <span class="sidebar-title">筛选条件</span>
          <el-button v-if="activeFilterCount > 0" size="small" text type="danger" @click="resetFilters">
            清空 ({{ activeFilterCount }})
          </el-button>
        </div>

        <!-- ──────── 学校专属 ──────── -->
        <template v-if="searchMode === 'school'">
          <div class="filter-block">
            <div class="filter-block-title">到学校的时间</div>
            <el-radio-group v-model="commuteTime" class="fg-radio" @change="doSearch">
              <el-radio :value="null">不限</el-radio>
              <el-radio :value="5">步行5分钟以内</el-radio>
              <el-radio :value="10">步行10分钟以内</el-radio>
              <el-radio :value="15">步行15分钟以内</el-radio>
              <el-radio :value="20">车程15分钟以内</el-radio>
              <el-radio :value="30">车程30分钟以内</el-radio>
            </el-radio-group>
          </div>

          <div class="filter-block">
            <div class="filter-block-title">距离</div>
            <el-radio-group v-model="distanceFilter" class="fg-radio" @change="doSearch">
              <el-radio :value="null">不限</el-radio>
              <el-radio :value="0.5">500m 以内</el-radio>
              <el-radio :value="1">1km 以内</el-radio>
              <el-radio :value="3">3km 以内</el-radio>
              <el-radio :value="5">5km 以内</el-radio>
            </el-radio-group>
          </div>
        </template>

        <!-- ──────── 城市专属：时长 ──────── -->
        <template v-if="searchMode === 'city'">
          <div class="filter-block">
            <div class="filter-block-title">时长</div>
            <el-radio-group v-model="durationFilter" class="fg-radio" @change="doSearch">
              <el-radio :value="null">不限</el-radio>
              <el-radio value="short">短租 (1-3月)</el-radio>
              <el-radio value="medium">中租 (3-6月)</el-radio>
              <el-radio value="long">长租 (12月+)</el-radio>
            </el-radio-group>
          </div>
        </template>

        <!-- ──────── 通用：入住月份 ──────── -->
        <div class="filter-block">
          <div class="filter-block-title">入住月份</div>
          <el-select v-model="filters.move_in_month" placeholder="不限" clearable style="width:100%" @change="doSearch">
            <el-option v-for="m in moveInMonths" :key="m.value" :label="m.label" :value="m.value" />
          </el-select>
        </div>

        <!-- ──────── 通用：房型 / 房间类型 ──────── -->
        <div class="filter-block">
          <div class="filter-block-title">{{ searchMode === 'school' ? '房型' : '房间类型' }}</div>
          <div class="chip-row">
            <span v-for="opt in roomTypes" :key="opt.value"
              class="chip" :class="{ on: filters.room_type === opt.value }"
              @click="filters.room_type = filters.room_type === opt.value ? undefined : opt.value; doSearch()"
            >{{ opt.label }}</span>
          </div>
        </div>

        <!-- ──────── 通用：公寓类型 ──────── -->
        <div class="filter-block">
          <div class="filter-block-title">公寓类型</div>
          <div class="chip-row">
            <span v-for="opt in propertyTypes" :key="opt.value"
              class="chip" :class="{ on: filters.property_type === opt.value }"
              @click="filters.property_type = filters.property_type === opt.value ? undefined : opt.value; doSearch()"
            >{{ opt.label }}</span>
          </div>
        </div>

        <!-- ──────── 通用：价格 ──────── -->
        <div class="filter-block">
          <div class="filter-block-title">价格范围</div>
          <div class="price-row">
            <el-input-number v-model="filters.price_min" :min="0" placeholder="最低" controls-position="right" size="small" style="flex:1" @change="doSearch" />
            <span class="price-dash">—</span>
            <el-input-number v-model="filters.price_max" :min="0" placeholder="最高" controls-position="right" size="small" style="flex:1" @change="doSearch" />
          </div>
        </div>

        <!-- ──────── 通用：房型（卧室数） ──────── -->
        <div class="filter-block">
          <div class="filter-block-title">户型</div>
          <div class="chip-row">
            <span v-for="opt in bedroomOptions" :key="opt.value"
              class="chip" :class="{ on: filters.bedrooms === opt.value }"
              @click="filters.bedrooms = filters.bedrooms === opt.value ? undefined : opt.value; doSearch()"
            >{{ opt.label }}</span>
          </div>
        </div>

        <!-- ──────── 通用：服务特点 ──────── -->
        <div class="filter-block">
          <div class="filter-block-title">服务特点</div>
          <el-checkbox-group v-model="filters.features" class="fg-check" @change="doSearch">
            <el-checkbox label="furnished">全套家具</el-checkbox>
            <el-checkbox label="wifi">WiFi 覆盖</el-checkbox>
            <el-checkbox label="cleaning">定期保洁</el-checkbox>
            <el-checkbox label="security">24h 安保</el-checkbox>
            <el-checkbox label="laundry">洗衣烘干</el-checkbox>
            <el-checkbox label="gym">健身房</el-checkbox>
            <el-checkbox label="pool">游泳池</el-checkbox>
            <el-checkbox label="parking">停车位</el-checkbox>
          </el-checkbox-group>
        </div>

        <!-- ──────── 通用：便利设施 ──────── -->
        <div class="filter-block">
          <div class="filter-block-title">便利设施</div>
          <el-checkbox-group v-model="filters.amenities" class="fg-check" @change="doSearch">
            <el-checkbox label="supermarket">超市</el-checkbox>
            <el-checkbox label="restaurant">餐厅</el-checkbox>
            <el-checkbox label="hospital">医院</el-checkbox>
            <el-checkbox label="bus">公交站</el-checkbox>
            <el-checkbox label="metro">地铁站</el-checkbox>
            <el-checkbox label="park">公园</el-checkbox>
          </el-checkbox-group>
        </div>

        <!-- ──────── 通用：位置特点 ──────── -->
        <div class="filter-block">
          <div class="filter-block-title">位置特点</div>
          <el-checkbox-group v-model="filters.location_tags" class="fg-check" @change="doSearch">
            <el-checkbox label="quiet">安静社区</el-checkbox>
            <el-checkbox label="downtown">市中心</el-checkbox>
            <el-checkbox label="riverside">河景 / 海景</el-checkbox>
            <el-checkbox label="pet_friendly">可养宠物</el-checkbox>
            <el-checkbox label="balcony">阳台 / 露台</el-checkbox>
            <el-checkbox label="elevator">电梯楼</el-checkbox>
            <el-checkbox label="new_renovation">新装修</el-checkbox>
          </el-checkbox-group>
        </div>

        <!-- ──────── 排序 ──────── -->
        <div class="filter-block">
          <div class="filter-block-title">排序方式</div>
          <el-radio-group v-model="sortBy" class="fg-radio" @change="doSearch">
            <el-radio value="similarity">匹配度优先</el-radio>
            <el-radio value="price_asc">价格从低到高</el-radio>
            <el-radio value="price_desc">价格从高到低</el-radio>
            <el-radio value="area_desc">面积从大到小</el-radio>
          </el-radio-group>
        </div>
      </aside>

      <!-- ════════════════════════════════════════════ -->
      <!--  右侧：房源卡片 / 地图                       -->
      <!-- ════════════════════════════════════════════ -->
      <main class="results-area" :class="{ 'map-layout': viewMode === 'map' }">
        <div class="results-top">
          <span class="results-count">共 <strong>{{ searchResults.length }}</strong> 套房源</span>
        </div>

        <div v-if="loading" class="loading-wrap">
          <el-icon class="is-loading" :size="36"><Loading /></el-icon>
          <p>搜索中...</p>
        </div>

        <el-empty v-else-if="searchResults.length === 0" description="暂无匹配房源，请调整筛选条件" />

        <!-- ═══ 地图模式 ═══ -->
        <template v-else-if="viewMode === 'map'">
          <div class="map-body">
            <!-- 房源列表列 -->
            <div class="map-property-col" ref="propertyListCol">
              <div
                v-for="p in searchResults" :key="p.id"
                :id="'prop-' + p.id"
                class="map-property-card"
              >
                <PropertyCard
                  :property="p"
                  :show-quick-book="true"
                  :commute="commuteMap[p.id] || null"
                  :link-query="schoolLinkQuery"
                  :class="{ 'map-card-highlight': highlightedId === p.id }"
                  @click="flyToProperty(p)"
                  @book="openBookingDialog"
                />
              </div>
            </div>
            <!-- 地图 -->
            <div class="map-container" ref="mapContainer"></div>
          </div>
        </template>

        <!-- ═══ 网格 / 列表模式 ═══ -->
        <template v-else>
          <div :class="viewMode === 'grid' ? 'card-grid' : 'card-list'">
            <PropertyCard
              v-for="p in pagedResults" :key="p.id" :property="p"
              :show-quick-book="true"
              :commute="commuteMap[p.id] || null"
              :link-query="schoolLinkQuery"
              @book="openBookingDialog"
            />
          </div>
          <div v-if="searchResults.length > pageSize" class="pag">
            <el-pagination
              v-model:current-page="currentPage" :page-size="pageSize"
              :total="searchResults.length" layout="prev, pager, next" background small
            />
          </div>
        </template>
      </main>
    </div>

    <BookingDateDialog
      v-model="showBookingDialog"
      :property-id="selectedProperty?.id || 0"
      :property-title="selectedProperty?.title"
      :property-price="selectedProperty?.price_monthly"
      @confirm="handleBookingConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, School, Grid, List, Location, Loading } from '@element-plus/icons-vue'
import { usePropertyStore } from '@/stores/property'
import { storeToRefs } from 'pinia'
import PropertyCard from '@/components/PropertyCard.vue'
import type { CommuteInfo } from '@/components/PropertyCard.vue'
import BookingDateDialog from '@/components/BookingDateDialog.vue'
import type { Property, PropertySearchParams, PropertyType } from '@/types/property'
import { commuteService } from '@/services/commute'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
})

const route = useRoute()
const router = useRouter()
const propertyStore = usePropertyStore()
const { searchResults, loading } = storeToRefs(propertyStore)

// ── 模式 ──
const searchMode = ref<'city' | 'school'>('city')
const schoolId = ref<number | null>(null)
const schoolName = ref('')
const viewMode = ref<'grid' | 'list'>('grid')

// ── 学校专属 ──
const commuteTime = ref<number | null>(null)
const distanceFilter = ref<number | null>(null)

// ── 城市专属 ──
const durationFilter = ref<string | null>(null)

// ── 地图 ──
let mapInstance: L.Map | null = null
let markerLayer = L.layerGroup()
const mapContainer = ref<HTMLElement | null>(null)
const propertyListCol = ref<HTMLElement | null>(null)
const mapReady = ref(false)
const highlightedId = ref<number | null>(null)

/** 滚动房源列表到指定卡片 */
function scrollToList(propertyId: number) {
  highlightedId.value = propertyId
  nextTick(() => {
    const el = document.getElementById('prop-' + propertyId)
    if (el && propertyListCol.value) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  })
  // 1.5 秒后取消高亮
  setTimeout(() => { highlightedId.value = null }, 2000)
}

function initMap() {
  if (!mapContainer.value || mapReady.value) return
  mapInstance = L.map(mapContainer.value, { zoomControl: true }).setView([30, 0], 2)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap',
    maxZoom: 19,
  }).addTo(mapInstance)
  markerLayer.addTo(mapInstance)
  mapReady.value = true
}

function renderMarkers() {
  if (!mapInstance) return
  markerLayer.clearLayers()
  const bounds: [number, number][] = []
  for (const p of searchResults.value) {
    const lat = Number((p as any).latitude)
    const lng = Number((p as any).longitude)
    if (isNaN(lat) || isNaN(lng)) continue
    const m = L.marker([lat, lng]).bindPopup(
      `<div style="max-width:220px">
        <strong>${(p as any).title || ''}</strong><br/>
        ${(p as any).district || ''}<br/>
        ¥${(p as any).price_monthly}/月 · ${(p as any).bedrooms}室
      </div>`
    )
    // 点击标记 → 滚动房源列表到对应卡片
    m.on('click', () => {
      scrollToList(p.id)
    })
    markerLayer.addLayer(m)
    bounds.push([lat, lng])
  }
  if (bounds.length > 0) {
    mapInstance.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 })
  }
}

function flyToProperty(p: any) {
  if (!mapInstance) return
  const lat = Number(p.latitude)
  const lng = Number(p.longitude)
  if (isNaN(lat) || isNaN(lng)) return
  mapInstance.flyTo([lat, lng], 16, { duration: 0.8 })
  // 打开弹窗
  markerLayer.eachLayer((layer: any) => {
    const ll = layer.getLatLng()
    if (Math.abs(ll.lat - lat) < 0.0001 && Math.abs(ll.lng - lng) < 0.0001) {
      layer.openPopup()
    }
  })
}

function destroyMap() {
  if (mapInstance) {
    mapInstance.remove()
    mapInstance = null
  }
  mapReady.value = false
}

// 监听 viewMode 切换到 map 时初始化地图
watch(viewMode, (mode) => {
  if (mode === 'map') {
    nextTick(() => {
      initMap()
      nextTick(() => renderMarkers())
    })
  } else {
    destroyMap()
  }
})

// 地图模式下搜索结果变化时刷新标记
watch(searchResults, (results) => {
  if (viewMode.value === 'map' && mapReady.value) {
    nextTick(() => renderMarkers())
  }
})

// ── 通用 ──
const sortBy = ref('similarity')
const currentPage = ref(1)
const pageSize = 12

const filters = reactive<PropertySearchParams & {
  move_in_month?: number; room_type?: string
  features?: string[]; amenities?: string[]; location_tags?: string[]
}>({
  q: '', district: undefined, price_min: undefined, price_max: undefined,
  bedrooms: undefined, property_type: undefined,
  limit: 30, country: undefined, institute_id: undefined,
})

const activeFilterCount = computed(() => {
  let n = 0
  if (commuteTime.value) n++
  if (distanceFilter.value) n++
  if (durationFilter.value) n++
  if (filters.move_in_month) n++
  if (filters.room_type) n++
  if (filters.property_type) n++
  if (filters.price_min || filters.price_max) n++
  if (filters.bedrooms != null) n++
  if (filters.features?.length) n += filters.features.length
  if (filters.amenities?.length) n += filters.amenities.length
  if (filters.location_tags?.length) n += filters.location_tags.length
  return n
})

// ── 学校信息（硬编码，避免后端 API 依赖）──
const SCHOOL_INFO: Record<number, { name: string; lat: number; lng: number; country: string; city: string }> = {
  1: { name: 'University of California, Los Angeles (UCLA)', lat: 34.0689, lng: -118.4452, country: 'US', city: 'Los Angeles' },
  2: { name: 'National University of Singapore (NUS)',       lat: 1.2966,  lng: 103.7764,  country: 'SG', city: 'Singapore' },
  3: { name: 'Nanyang Technological University (NTU)',       lat: 1.3483,  lng: 103.6831,  country: 'SG', city: 'Singapore' },
}

/** Haversine 距离 (km) */
function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLng = (lng2 - lng1) * Math.PI / 180
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLng / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

/** Haversine 兜底估算（API 不可用时使用） */
function estimateCommuteFallback(distKm: number): CommuteInfo {
  const road = distKm * 1.35
  return {
    dist_km: Math.round(distKm * 100) / 100,
    walk_min: Math.max(1, Math.round(road / 5 * 60)),
    bike_min: Math.max(1, Math.round(road / 15 * 60)),
    drive_min: Math.max(1, Math.round(road / 35 * 60)),
    transit_min: Math.max(1, Math.round(road / 20 * 60)),
  }
}

/** 当前学校模式下每个 property_id → 通勤信息 */
const commuteMap = ref<Record<number, CommuteInfo>>({})
const commuteLoading = ref(false)

/** 异步获取真实通勤时间（API → Haversine 兜底） */
async function fetchCommuteTimes() {
  if (searchMode.value !== 'school' || !schoolId.value) {
    commuteMap.value = {}
    return
  }
  const school = SCHOOL_INFO[schoolId.value]
  if (!school) { commuteMap.value = {}; return }

  // 收集有坐标的房源
  const destinations: { id: number; lat: number; lng: number }[] = []
  for (const p of searchResults.value) {
    const lat = Number((p as any).latitude)
    const lng = Number((p as any).longitude)
    if (!isNaN(lat) && !isNaN(lng)) {
      destinations.push({ id: p.id, lat, lng })
    }
  }

  if (destinations.length === 0) { commuteMap.value = {}; return }

  // 第一步：立即用 Haversine 填充，保证 UI 不空白
  const fallbackMap: Record<number, CommuteInfo> = {}
  for (const d of destinations) {
    const km = haversineKm(school.lat, school.lng, d.lat, d.lng)
    fallbackMap[d.id] = estimateCommuteFallback(km)
  }
  commuteMap.value = fallbackMap

  // 第二步：调用后端 API 获取真实路线时间
  commuteLoading.value = true
  try {
    const resp = await commuteService.calculate({
      origin_lat: school.lat,
      origin_lng: school.lng,
      destinations: destinations.slice(0, 30), // 最多 30 个
      country: school.country,
      city: school.city,
    })
    // 用 API 结果更新
    const apiMap: Record<number, CommuteInfo> = {}
    for (const item of resp.results) {
      const id = typeof item.dest_id === 'string' ? Number(item.dest_id) : item.dest_id
      apiMap[id] = {
        dist_km: item.dist_km,
        walk_min: item.walk_min,
        bike_min: item.bike_min,
        drive_min: item.drive_min,
        transit_min: item.transit_min,
      }
    }
    commuteMap.value = apiMap
  } catch {
    // API 失败，保持 Haversine 兜底值（已在上方赋值）
    console.debug('通勤 API 调用失败，使用 Haversine 估算')
  } finally {
    commuteLoading.value = false
  }
}

// 搜索结果或学校变化时重新获取通勤时间
watch([searchResults, schoolId], () => {
  fetchCommuteTimes()
})

/** 传递给详情页的 school query 参数 */
const schoolLinkQuery = computed(() => {
  if (searchMode.value !== 'school' || !schoolId.value) return {} as Record<string, string>
  const school = SCHOOL_INFO[schoolId.value]
  if (!school) return {} as Record<string, string>
  return {
    school_id: String(schoolId.value),
    school_lat: String(school.lat),
    school_lng: String(school.lng),
    school_name: school.name,
    school_country: school.country,
    school_city: school.city,
  } as Record<string, string>
})

// ── 选项数据 ──
const moveInMonths = [
  { label: '2026年7月', value: 202607 }, { label: '2026年8月', value: 202608 },
  { label: '2026年9月', value: 202609 }, { label: '2026年10月', value: 202610 },
  { label: '2027年1月', value: 202701 },
]
const roomTypes = [
  { label: 'Ensuite 独卫', value: 'ensuite' }, { label: 'Studio 单人', value: 'studio' },
  { label: '1室', value: '1bed' }, { label: '2室', value: '2bed' },
  { label: '3室+', value: '3bed+' }, { label: '共享', value: 'shared' },
]
const propertyTypes = [
  { label: '学生公寓', value: 'student' }, { label: '普通公寓', value: 'apartment' },
  { label: '别墅', value: 'house' }, { label: '合租', value: 'shared' },
]
const bedroomOptions = [
  { label: '开间', value: 0 }, { label: '1室', value: 1 }, { label: '2室', value: 2 },
  { label: '3室', value: 3 }, { label: '4室+', value: 4 },
]

// ── Booking ──
const showBookingDialog = ref(false)
const selectedProperty = ref<Property | null>(null)
function openBookingDialog(p: Property) { selectedProperty.value = p; showBookingDialog.value = true }
function handleBookingConfirm(data: { propertyId: number; date: string; slot: string }) {
  showBookingDialog.value = false
  router.push({ path: '/booking/confirm', query: { property_id: String(data.propertyId), date: data.date, slot: data.slot } })
}

const pagedResults = computed(() => {
  const s = (currentPage.value - 1) * pageSize
  return searchResults.value.slice(s, s + pageSize)
})

// ── 搜索 ──
function doSearch() {
  currentPage.value = 1
  const p: PropertySearchParams = {}

  // 地点筛选
  if (searchMode.value === 'school' && filters.institute_id) {
    p.institute_id = filters.institute_id
  } else if (filters.district) {
    p.district = filters.district
  }

  if (filters.q) p.q = filters.q
  if (filters.price_min != null) p.price_min = filters.price_min
  if (filters.price_max != null) p.price_max = filters.price_max
  if (filters.bedrooms != null) p.bedrooms = filters.bedrooms
  if (filters.property_type) p.property_type = filters.property_type as PropertyType
  p.limit = 30

  propertyStore.fetchSearch(p)
}

function resetFilters() {
  filters.q = ''; filters.district = undefined; filters.price_min = undefined
  filters.price_max = undefined; filters.bedrooms = undefined; filters.property_type = undefined
  filters.move_in_month = undefined; filters.room_type = undefined
  filters.features = undefined; filters.amenities = undefined; filters.location_tags = undefined
  commuteTime.value = null; distanceFilter.value = null; durationFilter.value = null
  sortBy.value = 'similarity'
  doSearch()
}

// ── 路由初始化 ──
function initFromRoute() {
  const q = route.query
  if (q.school_id) {
    searchMode.value = 'school'; schoolId.value = Number(q.school_id)
    filters.institute_id = schoolId.value; filters.district = undefined
    schoolName.value = SCHOOL_INFO[schoolId.value]?.name || ''
  } else if (q.district) {
    searchMode.value = 'city'; filters.district = q.district as string
    filters.institute_id = undefined; schoolName.value = ''
  }
  if (q.q) filters.q = q.q as string
  // 来自 AI 搜索的精确筛选条件
  if (q.price_min) filters.price_min = Number(q.price_min) || undefined
  if (q.price_max) filters.price_max = Number(q.price_max) || undefined
  if (q.bedrooms) filters.bedrooms = Number(q.bedrooms) || undefined
  if (q.property_type) filters.property_type = q.property_type as PropertyType
  doSearch()
}
onMounted(() => {
  document.documentElement.classList.add('search-page-active')
  initFromRoute()
})
onUnmounted(() => {
  document.documentElement.classList.remove('search-page-active')
  destroyMap()
})
watch(() => route.query, () => initFromRoute())
</script>

<style scoped>
.search-page {
  height: calc(100vh - 64px - 24px); /* header 64px + layout-main padding-top 24px */
  margin: 0; padding: 0 16px 8px 16px;
  display: flex; flex-direction: column; overflow: hidden;
}

/* ── Banner ── */
.school-banner {
  display: flex; align-items: center; gap: 12px; padding: 16px 20px;
  background: var(--bg-white); border: 1px solid var(--border);
  border-radius: var(--radius); margin-bottom: 16px;
}
.school-banner h1 { font-size: 20px; font-weight: 700; color: var(--text-primary); margin: 0; }
.school-count { font-size: 13px; color: var(--text-muted); background: var(--bg); padding: 2px 12px; border-radius: 20px; }

/* ── Layout ── */
.search-layout {
  display: flex; gap: 20px; align-items: stretch;
  flex: 1; min-height: 0; /* 填满 search-page 剩余高度 */
}

/* ── Sidebar ── */
.filter-sidebar {
  width: 250px; flex-shrink: 0;
  background: var(--bg-white);
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 16px;
  display: flex; flex-direction: column;
  overflow-y: auto; /* 筛选栏内部滚动 */
}
.sidebar-title-row {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 14px; padding-bottom: 10px;
  border-bottom: 2px solid var(--primary);
}
.sidebar-title { font-size: 15px; font-weight: 700; color: var(--text-primary); }

/* ── Filter Blocks ── */
.filter-block {
  margin-bottom: 18px; padding-bottom: 16px;
  border-bottom: 1px solid var(--border-light);
}
.filter-block:last-child { border-bottom: none; margin-bottom: 0; }
.filter-block-title {
  font-size: 12.5px; font-weight: 700; color: var(--text-secondary);
  margin-bottom: 10px; letter-spacing: 0.5px;
}

/* radio group vertical */
.fg-radio { display: flex; flex-direction: column; gap: 5px; }
.fg-radio .el-radio { margin-right: 0; font-size: 13px; height: 28px; }

/* check group vertical */
.fg-check { display: flex; flex-direction: column; gap: 5px; }
.fg-check .el-checkbox { margin-right: 0; font-size: 13px; height: 26px; }

/* chip buttons */
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  font-size: 12px; padding: 4px 10px; border-radius: 6px;
  border: 1px solid var(--border); cursor: pointer;
  color: var(--text-secondary); background: var(--bg);
  transition: all .15s; user-select: none;
}
.chip:hover { border-color: var(--primary); color: var(--primary); }
.chip.on { background: var(--primary-light); border-color: var(--primary); color: var(--primary); font-weight: 600; }

/* price */
.price-row { display: flex; align-items: center; gap: 6px; }
.price-dash { color: var(--text-muted); font-size: 12px; }

/* ── Results ── */
.results-area {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column;
  overflow-y: auto; /* 网格/列表模式下内部滚动 */
  overflow-x: hidden;
}
.results-area.map-layout { overflow-y: hidden; } /* 地图模式由 map-body 控制滚动 */
.results-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; padding: 0 4px; flex-shrink: 0; }
.results-count { font-size: 14px; color: var(--text-secondary); }
.loading-wrap { display: flex; flex-direction: column; align-items: center; padding: 60px; color: var(--text-muted); gap: 10px; }
.card-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.card-list { display: flex; flex-direction: column; gap: 14px; }
.pag { display: flex; justify-content: center; margin-top: 24px; padding-bottom: 30px; flex-shrink: 0; }

/* ── Map Toggle Button ── */
.map-toggle-btn {
  width: 100%;
  margin-bottom: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

/* ── Map Layout ── */
.results-area.map-layout { overflow-y: hidden; }

.map-body {
  flex: 1; min-height: 0;
  display: flex; gap: 0;
  border: 1px solid var(--border); border-radius: var(--radius);
  overflow: hidden;
}

.map-property-col {
  width: 300px; flex-shrink: 0; overflow-y: auto;
  background: var(--bg-white); border-right: 1px solid var(--border);
  padding: 8px;
}
.map-property-card {
  margin-bottom: 8px;
  border-radius: 8px;
  transition: box-shadow 0.3s, outline 0.3s;
}
.map-property-card:last-child { margin-bottom: 0; }

/* 高亮当前选中的卡片 */
.map-card-highlight {
  outline: 3px solid var(--primary);
  outline-offset: -1px;
  box-shadow: 0 0 16px rgba(255, 107, 53, 0.35);
}

/* 地图模式：卡片内容自适应 */
.map-property-col :deep(.property-card) { height: auto; }
.map-property-col :deep(.card-image) { height: 130px; }
.map-property-col :deep(.card-body) { padding: 10px 12px; }
.map-property-col :deep(.card-title) { font-size: 13px; margin-bottom: 4px; }
.map-property-col :deep(.card-tags) { margin-bottom: 4px; }
.map-property-col :deep(.card-tags .el-tag) { font-size: 11px !important; padding: 0 6px !important; }
.map-property-col :deep(.commute-row) { font-size: 10px; padding: 4px 6px; margin-bottom: 2px; }
.map-property-col :deep(.commute-dist) { font-size: 10px; padding: 0 6px 2px; margin-bottom: 2px; }
.map-property-col :deep(.card-address) { font-size: 11px; margin-bottom: 8px; }
.map-property-col :deep(.card-price) { font-size: 18px; }
.map-property-col :deep(.card-actions .el-button) { font-size: 12px; padding: 4px 8px !important; }
.map-property-col :deep(.add-cart-btn) { width: 22px; height: 22px; }

.map-container {
  flex: 1; min-width: 0;
}

@media (max-width: 1200px) { .card-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 900px) {
  .search-layout { flex-direction: column; }
  .filter-sidebar { width: 100%; position: static; max-height: none; }
  .card-grid { grid-template-columns: 1fr; }
}
</style>

<style>
/* 搜索页全局样式：锁定视口，阻止 body 滚动 */
html.search-page-active,
html.search-page-active body {
  overflow: hidden;
  height: 100%;
}
</style>
