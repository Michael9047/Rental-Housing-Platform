<template>
  <div class="search-page">
    <!-- 大学/位置模式顶部横幅 -->
    <div v-if="searchMode === 'uni' && uniName" class="school-banner uni-banner">
      <el-icon :size="22"><component :is="uniId ? School : Location" /></el-icon>
      <h1>靠近 {{ uniName }} 的房源</h1>
      <span class="school-count">共 {{ filteredAndSortedResults.length }} 套</span>
    </div>

    <!-- 学校模式顶部横幅 -->
    <div v-if="searchMode === 'school' && schoolName" class="school-banner">
      <el-icon :size="22"><School /></el-icon>
      <h1>靠近 {{ schoolName }} 的房源</h1>
      <span class="school-count">{{ filteredAndSortedResults.length }} 套</span>
    </div>

    <!-- AI Agent 推荐结果横幅 -->
    <div v-if="fromAgent && !(searchMode === 'uni' && uniName) && !(searchMode === 'school' && schoolName)" class="school-banner agent-banner">
      <el-icon :size="22" color="#409eff"><ChatDotRound /></el-icon>
      <h1>AI 智能推荐结果</h1>
      <span class="school-count">{{ filteredAndSortedResults.length }} 套</span>
    </div>

    <div class="search-layout" :class="{ 'agent-open': agentOpen }">
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

        <!-- ──────── 排序 ──────── -->
        <div class="filter-block">
          <div class="filter-block-title">排序方式</div>
          <div class="chip-row">
            <button
              v-for="opt in sortOptions"
              :key="opt.value"
              class="chip"
              :class="{ on: sortField === opt.value }"
              @click="sortField = opt.value; onSortFieldChange()"
            >{{ opt.label }}</button>
            <button
              class="chip"
              @click="sortAsc = !sortAsc; onSortFieldChange()"
            >{{ sortAsc ? '↑ 升序' : '↓ 降序' }}</button>
          </div>
        </div>

        <!-- ① 学校 / 位置 / 半径 -->
        <template v-if="searchMode === 'uni' && uniName">
          <div class="filter-block">
            <div class="filter-block-title">{{ uniId ? '🎓' : '📍' }} {{ uniName }}</div>
            <el-button size="small" text type="danger" @click="clearSchool">{{ uniId ? '✕ 清除学校' : '✕ 清除位置' }}</el-button>
          </div>
          <div class="filter-block">
            <div class="filter-block-title">搜索半径：{{ uniRadius }}km</div>
            <el-slider v-model="uniRadius" :min="1" :max="20" :step="1" show-input @change="doSearch" />
          </div>
        </template>
        <template v-else>
          <!-- 地区模式：学校选择器 + 半径 -->
          <div class="filter-block">
            <div class="filter-block-title">学校</div>
            <el-select
              v-model="selectedUniId"
              placeholder="输入学校名搜索"
              clearable
              filterable
              remote
              :remote-method="searchSchools"
              :loading="schoolLoading"
              style="width:100%"
              @change="onSchoolSelect"
              @visible-change="(v:boolean) => { if(v) searchSchools('') }"
            >
              <el-option v-for="s in schoolOptions" :key="s.id"
                :label="(s.name_cn||'') + ' / ' + s.name" :value="s.id" />
            </el-select>
          </div>
          <div class="filter-block">
            <div class="filter-block-title">搜索半径：{{ uniRadius }}km</div>
            <el-slider v-model="uniRadius" :min="1" :max="20" :step="1" show-input @change="doSearch" />
          </div>
        </template>

        <!-- ② 月租金范围 -->
        <div class="filter-block">
          <div class="filter-block-title">月租金范围</div>
          <div class="price-row">
            <el-input-number v-model="filters.price_min" :min="0" :step="500" placeholder="最低" controls-position="right" size="small" style="flex:1" @change="doSearch" />
            <span class="price-dash">—</span>
            <el-input-number v-model="filters.price_max" :min="0" :step="500" placeholder="最高" controls-position="right" size="small" style="flex:1" @change="doSearch" />
          </div>
        </div>

        <!-- ③ 户型类型 -->
        <div class="filter-block">
          <div class="filter-block-title">户型类型</div>
          <div class="chip-row">
            <span v-for="opt in roomTypeOptions" :key="opt.value"
              class="chip" :class="{ on: filters.property_type === opt.value }"
              @click="filters.property_type = filters.property_type === opt.value ? undefined : opt.value; doSearch()"
            >{{ opt.label }}</span>
          </div>
        </div>

        <!-- ④ 便利设施 -->
        <div class="filter-block">
          <div class="filter-block-title">便利设施</div>
          <div class="amenity-grid">
            <el-checkbox
              v-for="a in visibleAmenities"
              :key="a"
              :model-value="filters.amenities || []"
              :label="a"
              size="small"
              @change="(checked: boolean) => toggleAmenity(a, checked)"
            >{{ a }}</el-checkbox>
          </div>
          <el-button
            v-if="amenityOptions.length > amenityCollapseLimit"
            text size="small" type="primary"
            class="amenity-toggle"
            @click="amenityExpanded = !amenityExpanded"
          >
            {{ amenityExpanded ? '收起 ▲' : `展开全部 (${amenityOptions.length - amenityCollapseLimit}+)` }}
          </el-button>
        </div>

        <!-- ⑤ 周边配套 — 待实现 -->
      </aside>

      <!-- ════════════════════════════════════════════ -->
      <!--  右侧：房源卡片 / 地图                       -->
      <!-- ════════════════════════════════════════════ -->
      <main class="results-area" :class="{ 'map-layout': viewMode === 'map' }">
        <div class="results-top">
          <span class="results-count">共 <strong>{{ filteredAndSortedResults.length }}</strong> 套房源</span>

          <div class="results-top-actions">
            <el-tooltip content="AI 租房管家 — 结合当前筛选帮你找房" placement="bottom">
              <el-button
                class="agent-toggle-btn"
                :type="agentOpen ? 'primary' : 'default'"
                size="small"
                @click="toggleAgent"
              >
                <el-icon :size="16"><ChatDotRound /></el-icon>
                <span>AI 管家</span>
              </el-button>
            </el-tooltip>

            <span v-if="selectedResultIds.length" class="results-compare-status">
              已选 {{ selectedResultIds.length }} 套待对比
            </span>
          </div>
        </div>

        <div v-if="loading" class="loading-wrap">
          <el-icon class="is-loading" :size="36"><Loading /></el-icon>
          <p>搜索中...</p>
        </div>

        <el-empty v-else-if="filteredAndSortedResults.length === 0" description="暂无匹配房源，请调整筛选条件" />

        <!-- ═══ 地图模式 ═══ -->
        <template v-else-if="viewMode === 'map'">
          <div class="map-body">
            <!-- 房源列表列 -->
            <div class="map-property-col" ref="propertyListCol">
              <div v-for="p in filteredAndSortedResults" :key="p.id" :id="'prop-'+p.id" class="map-property-card">
                <PropertyCard :property="p" :commute="commuteMap[p.id]" :no-navigate="true" @click="flyToProperty(p)" />
              </div>
            </div>
            <!-- 地图 -->
            <div class="map-container" ref="mapContainer"></div>
          </div>
        </template>

        <!-- ═══ 网格 / 列表模式 ═══ -->
        <template v-else>
          <div :class="viewMode === 'grid' ? 'card-grid' : 'card-list'">
            <PropertyCard v-for="p in pagedResults" :key="p.id" :property="p" :commute="commuteMap[p.id]" :show-similarity="false" />
          </div>
          <div v-if="searchResults.length > pageSize" class="pag">
            <el-pagination
              v-model:current-page="currentPage" :page-size="pageSize"
              :total="filteredAndSortedResults.length" layout="prev, pager, next" background small
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

  <!-- Agent 遮罩（窄屏） -->
  <div v-if="agentOpen" class="agent-overlay" @click="agentOpen = false" />
  <!-- Agent 侧边栏 -->
  <aside v-if="agentOpen" class="agent-dock">
    <Suspense>
      <SearchAgentPanel
        :filters="agentFilters"
        :result-count="agentComparableResults.length"
        :result-ids="agentComparableResults.map((property: any) => property.id)"
        :selected-result-ids="selectedResultIds"
        @close="agentOpen = false"
        @apply-filter-patch="applyAgentFilterPatch"
        @show-recommendations="showAgentRecommendations"
        @goto-ai-search="gotoAiSearch"
      />
      <template #fallback>
        <div class="agent-loading">AI 管家启动中...</div>
      </template>
    </Suspense>
  </aside>
</template>

<script setup lang="ts">
import { ref, reactive, computed, defineAsyncComponent, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAgentChatStore } from '@/stores/agentChat'
import { ElMessage } from 'element-plus'
import { Search, School, Grid, List, Location, Loading, ChatDotRound, SortUp, SortDown } from '@element-plus/icons-vue'

import { usePropertyStore } from '@/stores/property'
import { storeToRefs } from 'pinia'
interface CommuteInfo { dist_km: number; walk_min: number; bike_min: number; drive_min: number; transit_min: number }
// PropertyCard 替换，避免组件依赖崩溃
import BookingDateDialog from '@/components/BookingDateDialog.vue'
import PropertyCard from '@/components/PropertyCard.vue'
import type { Property, PropertySearchParams, PropertyType } from '@/types/property'
import type { AgentFilters, AgentRecommendation } from '@/types/agent'
import { commuteService } from '@/services/commute'
import { formatPropertyPrice } from '@/utils/currency'
import { uniqueAgentRecommendations, uniquePropertiesByIdAndTitle } from '@/utils/agentRecommendations'
import api from '@/services/api'
// Google Maps 加载
const gmKey = import.meta.env.VITE_GM_KEY as string | undefined
let gmReady = false

async function loadGoogleMaps(): Promise<boolean> {
  if (gmReady) return true
  if (!gmKey) { console.warn('VITE_GM_KEY not set'); return false }
  const gWin = window as any
  if (gWin.google?.maps) { gmReady = true; return true }
  return new Promise((resolve) => {
    const script = document.createElement('script')
    script.src = `https://maps.googleapis.com/maps/api/js?key=${gmKey}&libraries=places&language=zh-CN`
    script.onload = () => { gmReady = true; resolve(true) }
    script.onerror = () => { console.warn('Google Maps load failed'); resolve(false) }
    document.head.appendChild(script)
  })
}

const route = useRoute()
const router = useRouter()
const propertyStore = usePropertyStore()
const { searchResults, loading } = storeToRefs(propertyStore)
const SearchAgentPanel = defineAsyncComponent(() => import("@/components/search/SearchAgentPanel.vue"))
const authStore = useAuthStore()
const agentChatStore = useAgentChatStore()
const lastAgentSearchKey = ref('')
let restoringFromNavigation = false

// ── 模式 ──
const searchMode = ref<'city' | 'school' | 'uni' | 'agent'>('city')
const schoolId = ref<number | null>(null)
const schoolName = ref('')
const uniId = ref<number | null>(null)
const uniName = ref('')
const uniLat = ref<number | null>(null)
const uniLng = ref<number | null>(null)
const uniRadius = ref<number>(5)

const selectedUniId = ref<number | null>(null)
const schoolOptions = ref<any[]>([])
const schoolLoading = ref(false)

async function searchSchools(q: string) {
  if (!q || q.length < 1) q = ''
  schoolLoading.value = true
  try {
    const r = await import('@/services/api').then(m => m.default.get('/search/schools', { params: { q, limit: 20 } }))
    schoolOptions.value = r.data || []
  } catch { schoolOptions.value = [] }
  finally { schoolLoading.value = false }
}

function onSchoolSelect(schoolId: number | null) {
  if (!schoolId) {
    uniId.value = null; uniName.value = ''; uniLat.value = null; uniLng.value = null; searchMode.value = 'city'
  } else {
    const s = schoolOptions.value.find((u: any) => u.id === schoolId)
    if (s) {
      uniId.value = s.id; uniName.value = s.name_cn || s.name; uniLat.value = s.latitude; uniLng.value = s.longitude
      searchMode.value = 'uni'
    }
  }
  doSearch()
}

function clearSchool() {
  uniId.value = null; uniName.value = ''; uniLat.value = null; uniLng.value = null
  selectedUniId.value = null; schoolOptions.value = []; searchMode.value = 'city'
  doSearch()
}
const viewMode = ref<'grid' | 'list'>('grid')
/** 是否来自 Agent 推荐（显示 AI 推荐横幅） */
const fromAgent = ref(false)
const agentContext = ref<{ filters?: Record<string, unknown>; total?: number } | null>(null)
const agentOpen = ref(false)

const selectedResultIds = ref<number[]>([])

const agentFilterSynced = ref(false)

const unmappedAgentAmenities = ref<string[]>([])

const agentInstitutionName = ref('')



/** 国家筛选变更 */
function onCountryFilterChange() {
  filters.district = undefined
  currentPage.value = 1
  doSearch()
}

const countryOptions = [
  { label: '全部', value: '' },
  { label: '新加坡', value: 'SG' },
  { label: '英国', value: 'GB' },
  { label: '美国', value: 'US' },
  { label: '中国香港', value: 'HK' },
  { label: '中国大陆', value: 'CN' },
  { label: '澳大利亚', value: 'AU' },
]

// ── 学校专属 ──
const commuteTime = ref<number | null>(null)
const distanceFilter = ref<number | null>(null)

// ── 城市专属 ──
const durationFilter = ref<string | null>(null)

// ── Google 地图 ──
let mapInstance: any = null
let markers: any[] = []
let infoWindow: any = null
const mapContainer = ref<HTMLElement | null>(null)
const propertyListCol = ref<HTMLElement | null>(null)
const mapReady = ref(false)
const highlightedId = ref<number | null>(null)

function scrollToList(propertyId: number) {
  highlightedId.value = propertyId
  nextTick(() => {
    const el = document.getElementById('prop-' + propertyId)
    if (el && propertyListCol.value) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  })
  setTimeout(() => { highlightedId.value = null }, 2000)
}

async function initMap() {
  if (!mapContainer.value || mapReady.value) return
  const ok = await loadGoogleMaps()
  if (!ok) return
  const google = (window as any).google
  mapInstance = new google.maps.Map(mapContainer.value, {
    zoom: 12,
    center: { lat: 1.3521, lng: 103.8198 },
    gestureHandling: 'greedy',
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: true,
    zoomControl: true,
  })
  infoWindow = new google.maps.InfoWindow()
  mapReady.value = true
  renderMarkers()
}

function renderMarkers() {
  if (!mapInstance) return
  const google = (window as any).google
  // 清除旧标记
  markers.forEach(m => m.setMap(null))
  markers = []
  const bounds = new google.maps.LatLngBounds()
  let hasValid = false

  // 学校模式：标注大学位置（蓝色圆形+标签）
  if (uniLat.value != null && uniLng.value != null && uniName.value) {
    const uniPos = { lat: uniLat.value, lng: uniLng.value }
    const uniMarker = new google.maps.Marker({
      position: uniPos, map: mapInstance, title: uniName.value,
      icon: {
        path: google.maps.SymbolPath.CIRCLE,
        scale: 16, fillColor: '#4285F4', fillOpacity: 1,
        strokeColor: '#fff', strokeWeight: 2,
      },
      label: { text: uniId.value ? '🏫' : '📍', fontSize: '16px' },
    })
    uniMarker.addListener('click', () => {
      infoWindow?.setContent('<b>'+uniName.value+'</b>'); infoWindow?.open(mapInstance, uniMarker)
    })
    markers.push(uniMarker)
    bounds.extend(uniPos)
    hasValid = true
  }

  for (const p of filteredAndSortedResults.value) {
    const lat = Number((p as any).latitude)
    const lng = Number((p as any).longitude)
    if (isNaN(lat) || isNaN(lng)) continue
    hasValid = true
    const pos = { lat, lng }

    const marker = new google.maps.Marker({
      position: pos,
      map: mapInstance,
      title: (p as any).name || (p as any).title || '',
      animation: google.maps.Animation.DROP,
    })

    const name = (p as any).name || (p as any).title || ''
    const rent = (p as any).min_rent ?? (p as any).base_rent ?? (p as any).price_monthly ?? 0
    const currency = (p as any).currency || 'CNY'
    const sym = { CNY: '¥', GBP: '£', SGD: 'SG$', USD: '$' }[currency] || '¥'
    const rp = (p as any).rent_period === 'weekly' ? '/周' : '/月'
    const content = `<div style="max-width:200px;font-size:13px">
      <strong>${name}</strong><br/>
      ${sym}${Number(rent).toLocaleString()}${rp}起
    </div>`

    marker.addListener('click', () => {
      infoWindow?.close()
      infoWindow?.setContent(content)
      infoWindow?.open(mapInstance, marker)
      scrollToList(p.id)
    })

    markers.push(marker)
    bounds.extend(pos)
  }

  if (hasValid) {
    mapInstance.fitBounds(bounds, { top: 30, right: 30, bottom: 30, left: 380 })
  }
}

function flyToProperty(p: any) {
  if (!mapInstance) return
  const lat = Number(p.latitude)
  const lng = Number(p.longitude)
  if (isNaN(lat) || isNaN(lng)) return
  mapInstance.panTo({ lat, lng })
  mapInstance.setZoom(16)
  // 找到对应 marker 并触发 click 以打开 infoWindow
  for (const m of markers) {
    const pos = m.getPosition()
    if (pos && Math.abs(pos.lat() - lat) < 0.0001 && Math.abs(pos.lng() - lng) < 0.0001) {
      const google = (window as any).google
      google.maps.event.trigger(m, 'click')
      break
    }
  }
}

function destroyMap() {
  markers.forEach(m => m.setMap(null))
  markers = []
  if (infoWindow) { infoWindow.close(); infoWindow = null }
  mapInstance = null
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

// ── 通用 ──
const sortField = ref('similarity')
const sortAsc = ref(false)
const sortOptions = [
  { label: '综合匹配', value: 'similarity' },
  { label: '距离', value: 'commute_dist' },
  { label: '价格', value: 'price' },
]
const currentPage = ref(1)
const pageSize = 12

const filters = reactive<PropertySearchParams & {
  amenities?: string[]
}>({
  q: '', district: undefined, city: undefined, price_min: undefined, price_max: undefined,
  property_type: undefined,
  limit: 30, country: undefined, institute_id: undefined,
})

const activeFilterCount = computed(() => {
  let n = 0
  if (filters.institute_id) n++
  if (filters.property_type) n++
  if (filters.price_min || filters.price_max) n++
  if (filters.amenities?.length) n += filters.amenities.length
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
  // 大学模式：用 uniLat/Lng 作为起点
  if (searchMode.value === 'uni' && uniLat.value != null && uniLng.value != null) {
    const origin = { lat: uniLat.value, lng: uniLng.value, country: 'SG', city: 'Singapore' }
    await _calcCommute(origin)
    return
  }
  if (searchMode.value !== 'school' || !schoolId.value) {
    commuteMap.value = {}
    return
  }
  const school = SCHOOL_INFO[schoolId.value]
  if (!school) { commuteMap.value = {}; return }
  await _calcCommute(school)
}

async function _calcCommute(origin: { lat: number; lng: number; country: string; city: string }) {
  // collect destinations...

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
    const km = haversineKm(origin.lat, origin.lng, d.lat, d.lng)
    fallbackMap[d.id] = estimateCommuteFallback(km)
  }
  commuteMap.value = fallbackMap

  // 第二步：调用后端 API 获取真实路线时间
  commuteLoading.value = true
  try {
    const resp = await commuteService.calculate({
      origin_lat: origin.lat,
      origin_lng: origin.lng,
      destinations: destinations.slice(0, 30),
      country: origin.country,
      city: origin.city,
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

// 通勤数据更新后重置分页（可能因筛选导致结果减少）
watch(commuteMap, () => {
  currentPage.value = 1
})

/** 传递给详情页的 school query 参数 */

const AGENT_AMENITY_LABELS: Record<string, string> = {
  furnished: '家具齐全', wifi: 'WiFi', cleaning: '定期保洁', security: '24h安保',
  laundry: '洗衣机', gym: '健身房', pool: '泳池', parking: '停车位',
  air_conditioning: '空调', private_kitchen: '独立厨房', study_room: '自习室',
  supermarket: '超市', restaurant: '餐厅', hospital: '医院', bus: '公交站', metro: '地铁站', park: '公园',
  quiet: '安静社区', downtown: '市中心', riverside: '河景/海景',
  pet_friendly: '宠物友好', balcony: '阳台', elevator: '电梯', new_renovation: '新装修',
}

const agentFilters = computed<AgentFilters>(() => {
  const result: AgentFilters = {
    country: filters.country,
    district: filters.district,
    price_min: filters.price_min,
    price_max: filters.price_max,
    bedrooms: filters.bedrooms,
    property_type: filters.property_type,
    room_type: filters.room_type,
    available_from: filters.move_in_month ? String(filters.move_in_month) : undefined,
  }
  const amenityValues = [
    ...(filters.features || []),
    ...(filters.amenities || []),
    ...(filters.location_tags || []),
  ]
  const amenities = amenityValues.map((value) => AGENT_AMENITY_LABELS[value]).filter(Boolean)
  if (amenities.length) result.amenities = amenities
  if (searchMode.value === 'school' && schoolName.value) result.institution = schoolName.value
  if (searchMode.value === 'uni' && uniName.value) result.institution = uniName.value
  if ((searchMode.value === 'school' || searchMode.value === 'uni') && commuteTime.value != null) {
    result.commute_minutes = commuteTime.value
    result.commute_mode = commuteTime.value <= 15 ? 'walking' : 'driving'
  }
  if (durationFilter.value === 'short') result.max_lease_months = 3
  if (durationFilter.value === 'medium') {
    result.min_lease_months = 3
    result.max_lease_months = 6
  }
  if (durationFilter.value === 'long') result.min_lease_months = 12
  return result
})

const agentComparableResults = computed(() => {
  return filteredAndSortedResults.value
})

function isResultSelected(propertyId: number): boolean {
  return selectedResultIds.value.includes(propertyId)
}

function toggleResultCompare(propertyId: number, checked: boolean) {
  if (checked) {
    if (!selectedResultIds.value.includes(propertyId)) selectedResultIds.value.push(propertyId)
  } else {
    selectedResultIds.value = selectedResultIds.value.filter((id) => id !== propertyId)
  }
}

/** 打开/关闭 Agent 面板 */
function toggleAgent() {
  if (!authStore.isLoggedIn) {
    ElMessage.warning('请先登录后再使用 AI 租房管家')
    router.push({ path: '/login', query: { redirect: route.fullPath } })
    return
  }
  agentOpen.value = !agentOpen.value
}

/** 接收 Agent 筛选补丁 -> 回填传统筛选栏 */
function applyAgentFilterPatch(patch: Record<string, unknown>, refreshResults?: boolean) {
  agentFilterSynced.value = true
  unmappedAgentAmenities.value = []

  if ('country' in patch) {
    const v = patch.country as string | null
    filters.country = v || undefined
    if (v) onCountryFilterChange()
  }
  if ('district' in patch) {
    const v = patch.district as string | null
    filters.district = v || undefined
    if (v) searchMode.value = 'city'
  }
  if ('price_min' in patch) filters.price_min = (patch.price_min as number) || undefined
  if ('price_max' in patch) filters.price_max = (patch.price_max as number) || undefined
  if ('bedrooms' in patch) filters.bedrooms = (patch.bedrooms as number) || undefined
  if ('property_type' in patch) filters.property_type = (patch.property_type as PropertyType) || undefined
  if ('room_type' in patch) filters.room_type = (patch.room_type as string) || undefined
  if ('institution' in patch) {
    const instName = patch.institution as string
    if (instName) {
      agentInstitutionName.value = instName
      const id = findSchoolId(instName)
      if (id) {
        schoolId.value = id
        filters.institute_id = id
        searchMode.value = 'school'
      }
    }
  }
  if ('commute_minutes' in patch) {
    commuteTime.value = (patch.commute_minutes as number) || null
    if (commuteTime.value) onCommuteFilterChange()
  }
  if ('amenities' in patch && Array.isArray(patch.amenities)) {
    const mapped: string[] = []
    const reverseLabel: Record<string, string> = {}
    for (const [key, label] of Object.entries(AGENT_AMENITY_LABELS)) {
      reverseLabel[label] = key
    }
    for (const label of patch.amenities as string[]) {
      const key = reverseLabel[label]
      if (key) mapped.push(key)
      else unmappedAgentAmenities.value.push(label)
    }
    if (mapped.length) {
      filters.features = [...new Set([...(filters.features || []), ...mapped])]
      filters.amenities = [...new Set([...(filters.amenities || []), ...mapped])]
    }
  }

  if (refreshResults !== false) doSearch()
}

/** 接收 Agent 推荐 -> 替换搜索结果 */
function showAgentRecommendations(recommendations: AgentRecommendation[]) {
  const results = recommendations.map((rec) => ({
    ...rec.property,
    id: rec.property_id,
  }))
  propertyStore.setSearchResults(results)
  fromAgent.value = true
  agentContext.value = {
    filters: agentFilters.value as unknown as Record<string, unknown>,
    total: results.length,
  }
}

/** 跳转到 AI 找房全页，携带当前搜索上下文 */
function gotoAiSearch() {
  sessionStorage.setItem('returnSearchState', JSON.stringify({
    filters: { ...filters },
    searchMode: searchMode.value,
    uniId: uniId.value, uniName: uniName.value,
    uniLat: uniLat.value, uniLng: uniLng.value, uniRadius: uniRadius.value,
    schoolId: schoolId.value, schoolName: schoolName.value,
    fromAgent: fromAgent.value, agentContext: agentContext.value,
    selectedUniId: selectedUniId.value,
  }))
  router.push('/ai-search')
}

/** 查找学校 ID（硬编码映射，与后端 universities 表对齐） */
function findSchoolId(name: string): number | null {
  const n = name.toLowerCase()
  if (n.includes('ucla')) return 1
  if (n.includes('nus') || n.includes('新加坡国立')) return 2
  if (n.includes('ntu') || n.includes('南洋理工')) return 3
  return null
}

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
// ── 筛选选项（对应 DB 真实字段）──

/** 户型类型 → rooms.property_type (DB值: studio, 1-bed, 2-bed, shared, house) */
const roomTypeOptions = [
  { label: 'Studio 单间', value: 'studio' },
  { label: '一室', value: '1-bed' },
  { label: '两室', value: '2-bed' },
  { label: '合租', value: 'shared' },
  { label: '整栋', value: 'house' },
]

/** 便利设施 可收起 */
const amenityCollapseLimit = 9
const amenityExpanded = ref(false)
const visibleAmenities = computed(() =>
  amenityExpanded.value ? amenityOptions : amenityOptions.slice(0, amenityCollapseLimit)
)

/** 便利设施 → institutes.amenities (JSONB)，覆盖常见租房配套设施 */
function toggleAmenity(amenity: string, checked: boolean) {
  if (!filters.amenities) filters.amenities = []
  if (checked) {
    if (!filters.amenities.includes(amenity)) filters.amenities.push(amenity)
  } else {
    filters.amenities = filters.amenities.filter(a => a !== amenity)
  }
  doSearch()
}

/** 便利设施 → room_types.amenities (DB 真实值，23 种) */
const amenityOptions = [
  'WiFi',
  '独立卫浴',
  '共享厨房',
  '独立厨房',
  '公共卫浴',
  '空调',
  '中央空调',
  '家具齐全',
  '全屋家电',
  '洗衣机',
  '冰箱',
  '微波炉',
  '电视',
  '衣柜',
  '衣帽间',
  '阳台',
  '双阳台',
  '沙发',
  '书桌',
  '椅子',
  '床垫',
  '台灯',
  '储物间',
]

/** 公寓搜索 */
const instituteLoading = ref(false)
const instituteOptions = ref<{ id: number; name: string }[]>([])

async function searchInstitutes(query: string) {
  if (!query || query.trim().length < 1) { instituteOptions.value = []; return }
  instituteLoading.value = true
  try {
    const resp = await api.get('/buildings/public', { params: { limit: 20 } })
    const buildings: any[] = resp.data || []
    const q = query.trim().toLowerCase()
    instituteOptions.value = buildings
      .filter((b: any) => b.name?.toLowerCase().includes(q) || (b.name_cn || '').includes(q))
      .slice(0, 10)
      .map((b: any) => ({ id: b.id, name: b.name || b.name_cn || String(b.id) }))
  } catch { instituteOptions.value = [] }
  finally { instituteLoading.value = false }
}

function onInstituteChange(val: number | undefined) {
  filters.institute_id = val || undefined
  if (val) {
    searchMode.value = 'school'
    schoolId.value = val
    schoolName.value = instituteOptions.value.find(o => o.id === val)?.name || ''
  } else {
    searchMode.value = 'city'
    schoolId.value = null
    schoolName.value = ''
  }
  doSearch()
}

// ── Booking ──
const showBookingDialog = ref(false)
const selectedProperty = ref<Property | null>(null)
function openBookingDialog(p: Property) { selectedProperty.value = p; showBookingDialog.value = true }
function handleBookingConfirm(data: { propertyId: number; date: string; slot: string }) {
  showBookingDialog.value = false
  router.push({ name: 'booking-move-in-date', params: { propertyId: String(data.propertyId) } })
}

/** 应用客户端筛选（通勤时间/距离/排序）后的最终结果 */
const filteredAndSortedResults = computed(() => {
  let results = [...searchResults.value]

  // ── 通勤时间筛选（学校模式）──
  if (searchMode.value === 'school' && commuteTime.value != null) {
    const maxMin = commuteTime.value
    results = results.filter(p => {
      const c = commuteMap.value[p.id]
      if (!c) return false // 无通勤数据则排除
      // 前3档（≤15）按步行时间，后2档（20/30）按驾车时间
      if (maxMin <= 15) {
        return c.walk_min <= maxMin
      } else {
        return c.drive_min <= maxMin
      }
    })
  }

  // ── 距离筛选（学校模式）──
  if (searchMode.value === 'school' && distanceFilter.value != null) {
    const maxKm = distanceFilter.value
    results = results.filter(p => {
      const c = commuteMap.value[p.id]
      if (!c) return false
      return c.dist_km <= maxKm
    })
  }

  // ── 客户端排序 ──
  const order = sortAsc.value ? 1 : -1
  if (sortField.value === 'commute_dist') {
    results.sort((a, b) => {
      const ca = commuteMap.value[a.id]
      const cb = commuteMap.value[b.id]
      return ((ca?.dist_km ?? Infinity) - (cb?.dist_km ?? Infinity)) * order
    })
  } else if (sortField.value === 'price') {
    results.sort((a, b) => (a.price_monthly - b.price_monthly) * order)
  }
  // 'similarity' 走后端排序，不在此处理

  return results
})

const pagedResults = computed(() => {
  const s = (currentPage.value - 1) * pageSize
  return filteredAndSortedResults.value.slice(s, s + pageSize)
})

// 地图模式下筛选结果变化时刷新标记
watch(filteredAndSortedResults, (results) => {
  if (viewMode.value === 'map' && mapReady.value) {
    nextTick(() => renderMarkers())
  }
})

// ── 搜索 ──
async function doSearch() {
  currentPage.value = 1
  const p: PropertySearchParams = {}

  // 地点筛选
  if (filters.country) p.country = filters.country
  if (filters.institute_id) p.institute_id = filters.institute_id
  else if (filters.city) p.city = filters.city
  else if (filters.district) p.district = filters.district

  // 半径搜索时 q 仅用于显示，不传给后端做名称过滤（否则会和半径条件叠加导致空结果）
  if (filters.q && !(uniLat.value && uniLng.value)) p.q = filters.q
  // 文字搜索→geocode→自动切换为学校模式
  if (filters.q && !uniLat.value) {
    try {
      const geo = await import('@/services/property').then(m => m.propertyService.geocodeAddress(filters.q!))
      if (geo.latitude && geo.longitude) {
        uniLat.value = geo.latitude; uniLng.value = geo.longitude
        uniName.value = geo.formatted_address || (geo.city ? geo.city + ' · ' + (geo.district || '') : filters.q)
        searchMode.value = 'uni'
      }
    } catch { /* ignore */ }
  }
  if (filters.price_min != null) p.price_min = filters.price_min
  if (filters.price_max != null) p.price_max = filters.price_max
  if (filters.bedrooms != null) p.bedrooms = filters.bedrooms
  if (filters.property_type) p.property_type = filters.property_type as PropertyType
  if (filters.room_type) p.room_type = filters.room_type
  if (filters.move_in_month) p.available_from = String(filters.move_in_month)

  // 合并 features + amenities + location_tags
  const allAmenities = [
    ...(filters.features || []),
    ...(filters.amenities || []),
    ...(filters.location_tags || []),
  ]
  if (allAmenities.length > 0) p.amenities = allAmenities

  // 租期筛选
  if (durationFilter.value === 'short') p.max_lease_months = 3
  else if (durationFilter.value === 'medium') { p.min_lease_months = 3; p.max_lease_months = 6 }
  else if (durationFilter.value === 'long') p.min_lease_months = 12

  // 半径搜索：大学坐标 → 地图中心
  if (uniLat.value != null && uniLng.value != null) {
    p.near_lat = uniLat.value; p.near_lng = uniLng.value
    p.near_distance_km = uniRadius.value
  }

  // 排序（后端排序：price 字段 + 方向；距离和综合为客户端排序）
  if (sortField.value === 'price') {
    p.sort_by = sortAsc.value ? 'price_asc' : 'price_desc'
  }

  // 从详情页返回时不触发新会话（保留对话历史）
  if (!restoringFromNavigation) {
    // 切换城市/学校/国家 → 自动新 Agent 会话，避免跨市场对话串扰
    if (agentChatStore.sessionId !== null) {
      const currentKey = JSON.stringify({
        country: filters.country,
        city: filters.city,
        district: filters.district,
        institute_id: filters.institute_id,
        uniId: uniId.value,
        uniName: uniName.value,
        searchMode: searchMode.value,
      })
      if (currentKey && currentKey !== lastAgentSearchKey.value) {
        lastAgentSearchKey.value = currentKey
        // 已有实质对话时才创新会话（空对话没必要重建）
        const hasRealMessages = agentChatStore.messages.some(m => m.role === 'user')
        if (hasRealMessages) agentChatStore.newSession().catch(() => {})
      }
    }
  }
  restoringFromNavigation = false

  propertyStore.fetchSearch(p)
}

/** 半径变更 → 重新搜索 */
function onRadiusChange() {
  // 更新 URL 并重新搜索
  if (uniId.value) {
    router.replace({
      path: '/search',
      query: { uni_id: String(uniId.value), radius: String(uniRadius.value), uni_name: uniName.value }
    })
  }
  doSearch()
}

/** 通勤筛选变更（纯客户端筛选，不需要重新请求后端） */
function onCommuteFilterChange() {
  currentPage.value = 1
}

/** 排序变更 */
function onSortFieldChange() {
  currentPage.value = 1
  if (sortField.value === 'price') {
    doSearch() // 价格走后端排序
  }
  // 距离和综合为客户端排序：filteredAndSortedResults 自动响应
}

function resetFilters() {
  filters.q = ''; filters.district = undefined; filters.city = undefined; filters.price_min = undefined
  filters.price_max = undefined; filters.property_type = undefined
  filters.institute_id = undefined; filters.amenities = undefined
  schoolId.value = null; schoolName.value = ''; searchMode.value = 'city'
  sortField.value = 'similarity'; sortAsc.value = false
  doSearch()
}

// ── 路由初始化 ──
async function initFromRoute() {
  restoringFromNavigation = true
  const q = route.query

  // 优先检查是否来自 Agent 推荐（sessionStorage 中预存了结果）
  const agentResultsJson = sessionStorage.getItem('agentSearchResults')
  const agentCtxJson = sessionStorage.getItem('agentSearchContext')
  if (agentResultsJson && q.from === 'agent') {
    try {
      const results = JSON.parse(agentResultsJson)
      const ctx = agentCtxJson ? JSON.parse(agentCtxJson) : null
      if (Array.isArray(results) && results.length > 0) {
        propertyStore.setSearchResults(results)
        fromAgent.value = true
        agentContext.value = ctx
        searchMode.value = 'agent'
        if (ctx?.filters) {
          const f = ctx.filters as Record<string, unknown>
          if (f.country) filters.country = f.country as string
          if (f.district) filters.district = f.district as string
        }
      }
    } catch { /* fallback */ }
    sessionStorage.removeItem('agentSearchResults')
    sessionStorage.removeItem('agentSearchContext')
    return
  }

  // 直接坐标搜索（来自搜索框地理编码结果）
  if (q.lat && q.lng) {
    uniLat.value = Number(q.lat)
    uniLng.value = Number(q.lng)
    uniName.value = (q.geo_city as string) || (q.q as string) || (q.uni_name as string) || ''
    uniRadius.value = Number(q.radius) || 5
    searchMode.value = 'uni'
    filters.district = undefined
    filters.city = undefined
    filters.institute_id = undefined
  } else if (q.uni_id) {
    // 大学近距搜索
    uniId.value = Number(q.uni_id)
    uniName.value = (q.uni_name as string) || ''
    uniRadius.value = Number(q.radius) || 5
    searchMode.value = 'uni'
    filters.district = undefined
    filters.city = undefined
    filters.institute_id = undefined

    // 从 API 获取大学坐标
    try {
      const resp = await api.get(`/universities?q=&limit=50`)
      const unis: any[] = resp.data || []
      const found = unis.find((u: any) => u.id === uniId.value)
      if (found?.latitude && found?.longitude) {
        uniLat.value = found.latitude
        uniLng.value = found.longitude
        uniName.value = found.name_cn || found.name || uniName.value
      }
    } catch { /* fallback: use hardcoded */ }
  } else if (q.school_id) {
    searchMode.value = 'school'; schoolId.value = Number(q.school_id)
    filters.institute_id = schoolId.value; filters.district = undefined; filters.city = undefined
    schoolName.value = SCHOOL_INFO[schoolId.value]?.name || ''
  } else if (q.institute_id) {
    searchMode.value = 'school'; schoolId.value = Number(q.institute_id)
    filters.institute_id = schoolId.value; filters.district = undefined; filters.city = undefined
    schoolName.value = (q.institute_name as string) || ''
  } else if (q.city) {
    searchMode.value = 'city'; filters.city = q.city as string; filters.district = undefined
    filters.institute_id = undefined; schoolName.value = ''
  } else if (q.district) {
    searchMode.value = 'city'; filters.city = undefined; filters.district = q.district as string
    filters.institute_id = undefined; schoolName.value = ''
  }
  if (q.q) filters.q = q.q as string
  if (q.price_min) filters.price_min = Number(q.price_min) || undefined
  if (q.price_max) filters.price_max = Number(q.price_max) || undefined
  if (q.bedrooms) filters.bedrooms = Number(q.bedrooms) || undefined
  if (q.property_type) filters.property_type = q.property_type as PropertyType
  doSearch()
}
// ── 导航状态保存/恢复 ──
const SESSION_KEY = 'searchPageState'

function saveSearchState() {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify({
    filters: { ...filters },
    searchMode: searchMode.value,
    uniId: uniId.value, uniName: uniName.value, uniLat: uniLat.value, uniLng: uniLng.value,
    uniRadius: uniRadius.value, schoolId: schoolId.value, schoolName: schoolName.value,
    sortField: sortField.value, sortAsc: sortAsc.value,
    agentOpen: agentOpen.value,
    hasAgentSession: agentChatStore.sessionId !== null,
  }))
}

function restoreSearchState() {
  const raw = sessionStorage.getItem(SESSION_KEY)
  if (!raw) return false
  try {
    const s = JSON.parse(raw)
    sessionStorage.removeItem(SESSION_KEY)
    // 恢复筛选
    if (s.filters) Object.assign(filters, s.filters)
    if (s.searchMode) searchMode.value = s.searchMode
    if (s.uniId) { uniId.value = s.uniId; uniName.value = s.uniName; uniLat.value = s.uniLat; uniLng.value = s.uniLng; uniRadius.value = s.uniRadius }
    if (s.schoolId) { schoolId.value = s.schoolId; schoolName.value = s.schoolName }
    if (s.sortField) sortField.value = s.sortField
    if (s.sortAsc != null) sortAsc.value = s.sortAsc
    // 恢复 Agent 面板
    if (s.agentOpen) agentOpen.value = true
    // 同步追踪 key，避免恢复后首次搜索误创对话
    lastAgentSearchKey.value = JSON.stringify({
      country: filters.country, city: filters.city, district: filters.district,
      institute_id: filters.institute_id, uniId: uniId.value,
      uniName: uniName.value, searchMode: searchMode.value,
    })
    return true
  } catch { return false }
}

onMounted(() => {
  const restored = restoreSearchState()
  if (!restored) initFromRoute()
})
onUnmounted(() => {
  saveSearchState()
  destroyMap()
})
watch(() => route.query, () => { initFromRoute() })
</script>

<style scoped>
.search-page {
  height: calc(100vh - 108px);
  margin: 0; padding: 0 16px;
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
.uni-banner { flex-wrap: wrap; gap: 8px; }
.radius-slider { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.radius-label { font-size: 12px; color: var(--text-muted); }
.radius-value { font-size: 13px; font-weight: 600; color: var(--primary); min-width: 36px; }

/* Agent 推荐横幅 */
.agent-banner {
  border-color: var(--el-color-primary-light-5, #b3d8ff);
  background: linear-gradient(135deg, #f0f7ff 0%, #fff 100%);
}

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

/* ── 便利设施 3列网格 ── */
.amenity-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 2px 4px;
}
.amenity-grid .el-checkbox {
  margin-right: 0;
  font-size: 11px;
  height: 24px;
}
.amenity-toggle {
  margin-top: 6px;
  padding: 2px 8px;
  font-size: 12px;
}

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
  overflow-y: auto;
  overflow-x: hidden;
  padding-bottom: 60px;
}
.results-area.map-layout { overflow-y: hidden; } /* 地图模式由 map-body 控制滚动 */
.results-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; padding: 0 4px; flex-shrink: 0; }
.results-count { font-size: 14px; color: var(--text-secondary); }
.loading-wrap { display: flex; flex-direction: column; align-items: center; padding: 60px; color: var(--text-muted); gap: 10px; }
.card-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.card-list { display: flex; flex-direction: column; gap: 14px; }
.pag { display: flex; justify-content: center; margin-top: 24px; padding-bottom: 30px; flex-shrink: 0; }

/* ── 内联房产卡片 ── */
.property-card { background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.06); cursor: pointer; transition: transform .2s, box-shadow .2s; }
.property-card:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,0,0,0.12); }
.card-image { height: 180px; background: #f5f6f8; position: relative; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.property-img { width: 100%; height: 100%; object-fit: cover; }
.image-placeholder { font-size: 14px; color: #c0c4cc; }
.district-badge { position: absolute; top: 8px; left: 8px; background: rgba(0,0,0,0.6); color: #fff; padding: 2px 10px; border-radius: 6px; font-size: 12px; }
.card-body { padding: 12px 16px 16px; }
.card-title { font-size: 15px; font-weight: 600; color: #303133; margin: 0 0 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.card-footer { display: flex; justify-content: space-between; align-items: center; }
.card-price { font-size: 18px; font-weight: 700; color: #f56c6c; }

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

/* ── Agent 侧边栏（独立于 .search-layout，固定定位在右侧）── */
.search-layout.agent-open {
  margin-right: 390px;
}
.search-layout.agent-open .card-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.agent-dock {
  position: fixed;
  top: 60px;
  right: 0;
  bottom: 0;
  width: 390px;
  z-index: 100;
  background: #fff;
  border-left: 1px solid #e4e7ed;
  overflow-y: auto;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.06);
}
.agent-overlay { display: none; }
.agent-loading {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-size: 14px;
}
.agent-toggle-btn { margin-right: 8px; }
.results-compare-status {
  font-size: 12px;
  color: var(--el-color-primary);
  margin-right: 12px;
  white-space: nowrap;
}

@media (max-width: 1360px) {
  .search-layout.agent-open { margin-right: 350px; }
  .agent-dock { width: 350px; }
}
@media (max-width: 1100px) {
  .search-layout.agent-open { margin-right: 0; }
  .agent-dock {
    width: min(400px, 100vw);
    z-index: 2000;
    box-shadow: -4px 0 20px rgba(0, 0, 0, 0.15);
  }
  .agent-overlay {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 1999;
    background: rgba(0, 0, 0, 0.3);
  }
  .search-layout.agent-open .card-grid { grid-template-columns: 1fr; }
}
</style>
