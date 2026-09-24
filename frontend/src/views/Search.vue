<template>
  <div class="search-page">
    <!-- 大学模式顶部横幅 -->
    <div v-if="searchMode === 'uni' && uniName" class="school-banner uni-banner">
      <el-icon :size="22"><School /></el-icon>
      <h1>靠近 {{ uniName }} 的房源</h1>
    </div>

    <!-- 学校模式顶部横幅 -->
    <div v-if="searchMode === 'school' && schoolName" class="school-banner">
      <el-icon :size="22"><School /></el-icon>
      <h1>靠近 {{ schoolName }} 的房源</h1>
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

        <div v-if="agentFilterSynced && agentSyncedFilterChips.length" class="agent-synced-filters" aria-live="polite">
          <div class="agent-synced-title">
            <el-icon><ChatDotRound /></el-icon>
            Agent 已同步到筛选栏
          </div>
          <div class="agent-synced-chips">
            <span v-for="chip in agentSyncedFilterChips" :key="chip">{{ chip }}</span>
          </div>
        </div>

        <!-- main 的公寓聚合搜索字段 -->
        <div class="filter-block">
          <div class="filter-block-title">国家 / 地区</div>
          <el-select v-model="filters.country" placeholder="全部国家和地区" clearable filterable style="width:100%" @change="doSearch">
            <el-option v-for="country in countryOptions" :key="country.value" :label="country.label" :value="country.value" />
          </el-select>
        </div>

        <div class="filter-block">
          <div class="filter-block-title">城市 / 区域</div>
          <div class="location-inputs">
            <el-input v-model="filters.city" placeholder="城市，例如 Singapore" clearable @change="doSearch" />
            <el-input v-model="filters.district" placeholder="区域，例如 Jurong" clearable @change="doSearch" />
          </div>
        </div>

        <!-- ① 学校 / 半径 -->
        <template v-if="searchMode === 'uni' && uniName">
          <!-- 学校模式：显示学校名 + 半径 -->
          <div class="filter-block">
            <div class="filter-block-title">🎓 {{ uniName }}</div>
            <el-button size="small" text type="danger" @click="clearSchool">✕ 清除学校</el-button>
          </div>
          <div class="filter-block">
            <div class="filter-block-title">搜索半径：{{ uniRadius }}km</div>
            <el-slider v-model="uniRadius" :min="1" :max="20" :step="1" show-input @change="onRadiusChange" />
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
            <el-slider v-model="uniRadius" :min="1" :max="20" :step="1" show-input @change="onRadiusChange" />
          </div>
        </template>

        <!-- ② 租金范围 -->
        <div class="filter-block">
          <div class="filter-block-title">租金范围</div>
          <div class="price-row">
            <el-input-number v-model="filters.price_min" :min="0" :step="500" placeholder="最低" controls-position="right" size="small" style="flex:1" @change="doSearch" />
            <span class="price-dash">—</span>
            <el-input-number v-model="filters.price_max" :min="0" :step="500" placeholder="最高" controls-position="right" size="small" style="flex:1" @change="doSearch" />
          </div>
        </div>

        <!-- 排序紧跟月租金，方便用户在调整预算后直接选择结果顺序 -->
        <div class="filter-block">
          <div class="filter-block-title">排序方式</div>
          <el-radio-group v-model="sortBy" class="fg-radio" @change="onSortChange">
            <el-radio value="default">综合排序</el-radio>
            <el-radio value="created_at">最新发布</el-radio>
            <el-radio value="price_asc">按价格升序</el-radio>
            <el-radio value="price_desc">按价格降序</el-radio>
            <el-radio value="commute_dist">按距离升序</el-radio>
          </el-radio-group>
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
              :model-value="(filters.amenities || []).includes(a)"
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
          <div class="results-heading">
            <span class="results-count">共 <strong>{{ filteredAndSortedResults.length }}</strong> 个公寓</span>
            <span class="results-hierarchy-note">“+”会加入当前筛选下的起价户型，其他户型可进详情选择</span>
          </div>
          <div class="results-actions">
            <el-button size="small" @click="openCart">
              <el-icon><ShoppingCart /></el-icon>
              候选清单<span v-if="cartStore.count">（{{ cartStore.count }}）</span>
            </el-button>
            <el-tooltip :content="agentOpen ? '关闭 AI 租房管家' : '打开 AI 租房管家'" placement="bottom">
              <el-button :type="agentOpen ? 'primary' : 'default'" size="small" @click="toggleAgent">
                <el-icon><ChatDotRound /></el-icon>
                Agent
              </el-button>
            </el-tooltip>
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
              <div v-for="p in filteredAndSortedResults" :key="p.id" :id="'prop-'+p.id" class="map-property-card building-result">
                <PropertyCard entity="building" :property="p" :commute="commuteMap[p.id]" :no-navigate="true" @click="flyToProperty(p)" />
              </div>
            </div>
            <!-- 地图 -->
            <div class="map-container" ref="mapContainer"></div>
          </div>
        </template>

        <!-- ═══ 网格 / 列表模式 ═══ -->
        <template v-else>
          <div :class="viewMode === 'grid' ? 'card-grid' : 'card-list'">
            <div v-for="p in pagedResults" :key="p.id" class="building-result">
              <PropertyCard entity="building" :property="p" :commute="commuteMap[p.id]" :show-similarity="false" />
            </div>
          </div>
          <div v-if="searchResults.length > pageSize" class="pag">
            <el-pagination
              v-model:current-page="currentPage" :page-size="pageSize"
              :total="filteredAndSortedResults.length" layout="prev, pager, next" background small
            />
          </div>
        </template>
      </main>

      <button v-if="agentOpen" class="agent-backdrop" aria-label="关闭 AI 租房管家" @click="agentOpen = false" />
      <aside v-if="agentOpen" class="agent-dock">
        <Suspense>
          <SearchAgentPanel
            :filters="effectiveAgentFilters"
            :pending-cleared-filters="pendingAgentClearedFilters"
            @close="agentOpen = false"
            @apply-filter-patch="applyAgentFilterPatch"
            @show-recommendations="showAgentRecommendations"
            @clear-filters-consumed="consumeAgentClearedFilters"
            @new-session="resetConversationContext"
            @open-full-page="openFullPageAi"
          />
          <template #fallback>
            <div class="agent-panel-loading">
              <el-icon class="is-loading" :size="24"><Loading /></el-icon>
              <span>正在打开 AI 租房管家</span>
            </div>
          </template>
        </Suspense>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, defineAsyncComponent, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { School, Location, Loading, ChatDotRound, ShoppingCart } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { usePropertyStore } from '@/stores/property'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'
import { useAgentChatStore } from '@/stores/agentChat'
import { storeToRefs } from 'pinia'
interface CommuteInfo { dist_km: number; walk_min: number; bike_min: number; drive_min: number; transit_min: number }
import PropertyCard from '@/components/PropertyCard.vue'
import type { PropertySearchParams, PropertyType } from '@/types/property'
import type { AgentFilterField, AgentFilters, AgentRecommendation, AgentSearchWorkspace } from '@/types/agent'
import { commuteService } from '@/services/commute'
import api from '@/services/api'
import { universityService, type UniversityOption } from '@/services/university'
import { countryToCurrency, formatPrice } from '@/data/currency'
import { saveRecentHousingSearch } from '@/utils/recentHousingSearch'
import {
  filterBuildingsByAgentRecommendations,
  uniqueAgentRecommendations,
} from '@/utils/agentRecommendations'
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
const authStore = useAuthStore()
const cartStore = useCartStore()
const agentChatStore = useAgentChatStore()
const { searchResults, loading } = storeToRefs(propertyStore)
const SearchAgentPanel = defineAsyncComponent(() => import('@/components/search/SearchAgentPanel.vue'))

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
const schoolOptions = ref<UniversityOption[]>([])
const schoolLoading = ref(false)

async function searchSchools(q: string) {
  schoolLoading.value = true
  try {
    // 大学接口支持空查询并按热门排序；空值时不要发送 q=""，避免触发
    // FastAPI 的 min_length 校验错误。
    schoolOptions.value = await universityService.search(q, 20)
  } catch { schoolOptions.value = [] }
  finally { schoolLoading.value = false }
}

function onSchoolSelect(schoolId: number | null) {
  if (!schoolId) {
    uniId.value = null; uniName.value = ''; uniLat.value = null; uniLng.value = null; searchMode.value = 'city'
  } else {
    const s = schoolOptions.value.find((university) => university.id === schoolId)
    if (s) {
      uniId.value = s.id; uniName.value = s.name_cn || s.name
      uniLat.value = s.latitude ?? null; uniLng.value = s.longitude ?? null
      searchMode.value = 'uni'
      saveRecentHousingSearch({
        kind: 'school', schoolId: s.id, schoolName: uniName.value,
        latitude: s.latitude ?? undefined, longitude: s.longitude ?? undefined,
        city: s.city ?? undefined, country: s.country ?? undefined, radiusKm: uniRadius.value,
      })
    }
  }
  doSearch()
}

function resetSchoolSelection() {
  schoolId.value = null; schoolName.value = ''
  uniId.value = null; uniName.value = ''; uniLat.value = null; uniLng.value = null
  selectedUniId.value = null; schoolOptions.value = []; searchMode.value = 'city'
}

function clearSchool() {
  resetSchoolSelection()
  doSearch()
}
const viewMode = ref<'grid' | 'map'>('grid')
/** 是否来自 Agent 推荐（显示 AI 推荐横幅） */
const fromAgent = ref(false)
const agentContext = ref<{ filters?: Record<string, unknown>; total?: number } | null>(null)
const agentOpen = ref(false)
const agentFilterSynced = ref(false)
const latestRecommendationCount = ref(0)
const agentResultRecommendations = ref<AgentRecommendation[] | null>(null)
const pendingAgentClearedFilters = ref<AgentFilterField[]>([])
const conversationFilters = ref<AgentFilters>({})
const conversationLocation = ref<{ lat: number; lng: number; name: string; country?: string } | null>(null)
const conversationRadiusKm = ref(5)
let lastHandledSearchId = ''
let activeSearchId = ''
let restoringWorkspace = false
let workspaceSave: Promise<unknown> | null = null

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
      label: { text: '🏫', fontSize: '16px' },
    })
    uniMarker.addListener('click', () => {
      infoWindow?.setContent('<b>'+escapeMapText(uniName.value)+'</b>'); infoWindow?.open(mapInstance, uniMarker)
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
    const country = (p as any).country
    const currency = (p as any).currency || countryToCurrency(country)
    const content = `<div style="max-width:200px;font-size:13px">
      <strong>${escapeMapText(name)}</strong><br/>
      ${escapeMapText(formatPrice(rent, currency, country))}/月起
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

function escapeMapText(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
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
  void persistSearchWorkspace()
})

// ── 通用 ──
const sortBy = ref('default')
const currentPage = ref(1)
const pageSize = 12

const filters = reactive<PropertySearchParams & {
  amenities?: string[]
}>({
  q: '', district: undefined, price_min: undefined, price_max: undefined,
  property_type: undefined,
  limit: 30, country: undefined, institute_id: undefined,
})

const countryOptions = [
  { label: '中国大陆', value: 'CN' },
  { label: '新加坡', value: 'SG' },
  { label: '英国', value: 'GB' },
  { label: '美国', value: 'US' },
  { label: '澳大利亚', value: 'AU' },
  { label: '加拿大', value: 'CA' },
  { label: '中国香港', value: 'HK' },
]

const agentFilters = computed<AgentFilters>(() => {
  const result: AgentFilters = {
    country: filters.country,
    city: filters.city,
    district: filters.district,
    institute_id: filters.institute_id,
    price_min: filters.price_min,
    price_max: filters.price_max,
    property_type: filters.property_type,
    amenities: filters.amenities,
  }
  if (searchMode.value === 'uni' && uniName.value) result.institution = uniName.value
  return result
})

/** 左侧条件与当前对话条件合并，AI 提取结果同时回写可见筛选控件。 */
const effectiveAgentFilters = computed<AgentFilters>(() => {
  const merged: AgentFilters = { ...agentFilters.value }
  for (const [key, value] of Object.entries(conversationFilters.value)) {
    if (value === undefined || value === null || value === '') continue
    if (key === 'price_min' && typeof value === 'number') {
      merged.price_min = Math.max(merged.price_min ?? value, value)
    } else if (key === 'price_max' && typeof value === 'number') {
      merged.price_max = Math.min(merged.price_max ?? value, value)
    } else if (key === 'amenities' && Array.isArray(value)) {
      merged.amenities = [...new Set([...(merged.amenities || []), ...(value as string[])])]
    } else {
      (merged as Record<string, unknown>)[key] = value
    }
  }
  return merged
})

/** 同一枚举条件不一致时，两层条件的交集为空，不应让其中一层覆盖另一层。 */
const hasManualConversationConflict = computed(() => {
  const manual = agentFilters.value as Record<string, unknown>
  const conversation = conversationFilters.value as Record<string, unknown>
  const equalityFields = ['country', 'city', 'district', 'institute_id', 'property_type']
  const normalize = (value: unknown) => String(value).trim().toLowerCase()
  if (equalityFields.some((field) => (
    manual[field] != null
    && manual[field] !== ''
    && conversation[field] != null
    && conversation[field] !== ''
    && normalize(manual[field]) !== normalize(conversation[field])
  ))) return true

  const effective = effectiveAgentFilters.value
  return effective.price_min != null
    && effective.price_max != null
    && effective.price_min > effective.price_max
})

const agentSyncedFilterChips = computed(() => {
  const chips: string[] = []
  const current = conversationFilters.value
  if (current.country) chips.push(countryOptions.find((item) => item.value === current.country)?.label || current.country)
  if (current.city) chips.push(current.city)
  if (current.district) chips.push(current.district)
  const currency = countryToCurrency(current.country)
  if (current.price_min != null) chips.push(`最低 ${formatPrice(current.price_min, currency, current.country)}`)
  if (current.price_max != null) chips.push(`最高 ${formatPrice(current.price_max, currency, current.country)}`)
  if (current.property_type) chips.push(roomTypeOptions.find((item) => item.value === current.property_type)?.label || String(current.property_type))
  if (current.amenities?.length) chips.push(...current.amenities.slice(0, 3))
  if (current.institution) chips.push(current.institution)
  return [...new Set(chips)].slice(0, 7)
})

const activeFilterCount = computed(() => {
  let n = 0
  if (filters.country) n++
  if (filters.city) n++
  if (filters.district) n++
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
  { label: 'Ensuite 独卫', value: 'ensuite' },
  { label: '一室', value: '1bed' },
  { label: '两室', value: '2bed' },
  { label: '三室', value: '3bed' },
  { label: '四室', value: '4bed' },
  { label: '五室+', value: '5bed+' },
  { label: '合租', value: 'shared' },
] satisfies Array<{ label: string; value: PropertyType }>

/** 便利设施 可收起 */
const amenityCollapseLimit = 12
const amenityExpanded = ref(false)
const visibleAmenities = computed(() =>
  amenityExpanded.value ? amenityOptions : amenityOptions.slice(0, amenityCollapseLimit)
)

/** 便利设施 → institutes.amenities (公寓级) */
function toggleAmenity(amenity: string, checked: boolean) {
  if (!filters.amenities) filters.amenities = []
  if (checked) {
    if (!filters.amenities.includes(amenity)) filters.amenities.push(amenity)
  } else {
    filters.amenities = filters.amenities.filter(a => a !== amenity)
  }
  doSearch()
}

/** 便利设施 → 公寓级 (institutes.amenities)，不涉及户型内设施 */
const amenityOptions = [
  'WiFi免费',
  '空调',
  '电梯',
  '健身房',
  '泳池',
  '洗衣房',
  '停车位',
  '公共厨房',
  '公共休闲区',
  '自习室',
  '门禁系统',
  '监控系统(CCTV)',
  '24小时安保',
  '夜间巡逻',
  '管家服务',
  '维修服务',
  '代收包裹',
  '公共区域保洁',
  'BBQ区',
  '网球场',
  '瑜伽室',
  '影音室',
  '校车接驳',
  '自行车库',
  '定期社交活动',
]

/** 应用客户端筛选（通勤时间/距离/排序）后的最终结果 */
const filteredAndSortedResults = computed(() => {
  let results = [...searchResults.value]

  if (agentResultRecommendations.value !== null) {
    results = filterBuildingsByAgentRecommendations(
      results,
      agentResultRecommendations.value,
    )
  }

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
  if (sortBy.value === 'commute_time') {
    results.sort((a, b) => {
      const ca = commuteMap.value[a.id]
      const cb = commuteMap.value[b.id]
      const ta = ca ? Math.min(ca.walk_min, ca.drive_min) : Infinity
      const tb = cb ? Math.min(cb.walk_min, cb.drive_min) : Infinity
      return ta - tb
    })
  } else if (sortBy.value === 'commute_dist') {
    results.sort((a, b) => {
      const ca = commuteMap.value[a.id]
      const cb = commuteMap.value[b.id]
      return (ca?.dist_km ?? Infinity) - (cb?.dist_km ?? Infinity)
    })
  } else if (sortBy.value === 'price_asc') {
    results.sort((a, b) => buildingRent(a) - buildingRent(b))
  } else if (sortBy.value === 'price_desc') {
    results.sort((a, b) => buildingRent(b) - buildingRent(a))
  }
  // default / created_at 走 main 的 Building 搜索排序。

  return results
})

function buildingRent(building: unknown): number {
  const card = building as Record<string, unknown>
  const value = card.min_rent ?? card.base_rent ?? card.price_monthly
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

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

function toggleAgent() {
  if (!authStore.isLoggedIn) {
    ElMessage.warning('登录后即可使用 AI 租房管家')
    void router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  agentOpen.value = !agentOpen.value
}

function openCart() {
  if (!authStore.isLoggedIn) {
    void router.push({ name: 'login', query: { redirect: '/cart' } })
    return
  }
  void router.push({ name: 'cart' })
}

function patchNumber(value: unknown): number | undefined {
  if (value == null || value === '') return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function normalizeCountry(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const normalized = value.trim().toLowerCase().replace(/[\s_-]+/g, '')
  const aliases: Record<string, string> = {
    cn: 'CN', china: 'CN', 中国: 'CN', 中国大陆: 'CN',
    sg: 'SG', singapore: 'SG', 新加坡: 'SG',
    gb: 'GB', uk: 'GB', unitedkingdom: 'GB', 英国: 'GB',
    us: 'US', usa: 'US', unitedstates: 'US', 美国: 'US',
    au: 'AU', australia: 'AU', 澳大利亚: 'AU',
    ca: 'CA', canada: 'CA', 加拿大: 'CA',
    hk: 'HK', hongkong: 'HK', 香港: 'HK', 中国香港: 'HK',
  }
  return aliases[normalized] || (normalized.length === 2 ? normalized.toUpperCase() : undefined)
}

function normalizePropertyType(value: unknown): PropertyType | undefined {
  if (typeof value !== 'string') return undefined
  const normalized = value.trim().toLowerCase().replace(/[\s_-]+/g, '')
  const aliases: Record<string, PropertyType> = {
    studio: 'studio', 单间: 'studio', 开间: 'studio',
    ensuite: 'ensuite', 独卫: 'ensuite', 独立卫浴: 'ensuite',
    '1bed': '1bed', 一室: '1bed',
    '2bed': '2bed', 两室: '2bed',
    '3bed': '3bed', '3bed+': '3bed', 三室: '3bed',
    '4bed': '4bed', 四室: '4bed',
    '5bed': '5bed+', '5bed+': '5bed+', 五室: '5bed+',
    shared: 'shared', 合租: 'shared',
  }
  return aliases[normalized]
}

function propertyTypeFromBedrooms(value: unknown): PropertyType | undefined {
  const bedrooms = patchNumber(value)
  if (bedrooms == null) return undefined
  if (bedrooms <= 0) return 'studio'
  if (bedrooms === 1) return '1bed'
  if (bedrooms === 2) return '2bed'
  if (bedrooms === 3) return '3bed'
  if (bedrooms === 4) return '4bed'
  return '5bed+'
}

function normalizeAmenities(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined
  const aliases: Record<string, string> = {
    wifi: 'WiFi免费', freewifi: 'WiFi免费', gym: '健身房', fitness: '健身房',
    fitnesscentre: '健身房', fitnesscenter: '健身房', swimmingpool: '泳池', pool: '泳池',
    laundry: '洗衣房', laundryroom: '洗衣房', washer: '洗衣房',
    parking: '停车位', elevator: '电梯', lift: '电梯',
    furnished: '家具齐全', 家具: '家具齐全',
    airconditioning: '空调', aircon: '空调',
    privatebathroom: '独立卫浴', ensuite: '独立卫浴', privatekitchen: '独立厨房',
    balcony: '阳台', refrigerator: '冰箱', fridge: '冰箱', wardrobe: '衣柜',
  }
  const normalized = value
    .map((item) => String(item).trim())
    .filter(Boolean)
    .map((item) => aliases[item.toLowerCase().replace(/[\s_-]+/g, '')] || item)
  return [...new Set(normalized)]
}

async function resolveConversationInstitution(institution: string) {
  const name = institution.trim()
  if (!name) return null

  await searchSchools(name)
  const normalized = name.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]/g, '')
  const matched = schoolOptions.value.find((school) => {
    const names = [school.name, school.name_cn, school.abbreviation]
      .filter(Boolean)
      .map((item) => String(item).toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]/g, ''))
    return names.some((item) => item.includes(normalized) || normalized.includes(item))
  }) || schoolOptions.value[0]

  if (matched?.latitude != null && matched?.longitude != null) {
    return {
      lat: Number(matched.latitude),
      lng: Number(matched.longitude),
      name: matched.name_cn || matched.name || name,
      country: matched.country ? normalizeCountry(matched.country) : undefined,
    }
  }

  try {
    const geo = await import('@/services/property').then((module) => module.propertyService.geocodeAddress(name))
    if (geo.latitude != null && geo.longitude != null) {
      return {
        lat: geo.latitude,
        lng: geo.longitude,
        name: geo.formatted_address || name,
      }
    }
  } catch {
    ElMessage.warning(`暂时无法定位「${name}」，已保留其他筛选条件`)
  }
  return null
}

/**
 * Agent 只修改 main Building 搜索能表达的条件；bedrooms 会映射为 UnitType
 * 聚合户型，学校名称会解析为经纬度后继续使用 main 的半径搜索。
 */
async function applyAgentFilterPatch(
  patch: Record<string, unknown>,
  refreshResults = true,
  clearedFilters: AgentFilterField[] = [],
) {
  if (!patch || typeof patch !== 'object') return
  if (Object.keys(patch).length || clearedFilters.length) agentFilterSynced.value = true

  const next: AgentFilters = { ...conversationFilters.value }
  const cleared = new Set<AgentFilterField>(clearedFilters)
  for (const field of cleared) delete next[field]
  if (cleared.has('country')) filters.country = undefined
  if (cleared.has('city')) filters.city = undefined
  if (cleared.has('district')) filters.district = undefined
  if (cleared.has('institute_id')) filters.institute_id = undefined
  if (cleared.has('price_min')) filters.price_min = undefined
  if (cleared.has('price_max')) filters.price_max = undefined
  if (cleared.has('property_type') || cleared.has('room_type') || cleared.has('bedrooms')) {
    filters.property_type = undefined
  }
  if (cleared.has('amenities')) filters.amenities = undefined
  if (cleared.has('institution')) conversationLocation.value = null
  if (cleared.has('commute_minutes')) conversationRadiusKm.value = 5

  if ('country' in patch) next.country = normalizeCountry(patch.country)
  if ('city' in patch) next.city = typeof patch.city === 'string' ? patch.city.trim() || undefined : undefined
  if ('district' in patch) next.district = typeof patch.district === 'string' ? patch.district.trim() || undefined : undefined
  if ('institute_id' in patch) {
    const instituteId = patchNumber(patch.institute_id)
    next.institute_id = instituteId != null && Number.isInteger(instituteId) && instituteId > 0
      ? instituteId
      : undefined
  }
  if ('price_min' in patch) next.price_min = patchNumber(patch.price_min)
  if ('price_max' in patch) next.price_max = patchNumber(patch.price_max)
  if ('property_type' in patch) next.property_type = normalizePropertyType(patch.property_type)
  if ('room_type' in patch && !('property_type' in patch)) next.property_type = normalizePropertyType(patch.room_type)
  if ('bedrooms' in patch && !('property_type' in patch) && !('room_type' in patch)) {
    next.property_type = propertyTypeFromBedrooms(patch.bedrooms)
  }
  if ('amenities' in patch) next.amenities = normalizeAmenities(patch.amenities)

  // AI 识别出的可表达条件直接同步到左侧控件，让界面与实际查询保持一致。
  if ('country' in patch) filters.country = next.country ?? undefined
  if ('city' in patch) filters.city = next.city ?? undefined
  if ('district' in patch) filters.district = next.district ?? undefined
  if ('institute_id' in patch) filters.institute_id = next.institute_id ?? undefined
  if ('price_min' in patch) filters.price_min = next.price_min ?? undefined
  if ('price_max' in patch) filters.price_max = next.price_max ?? undefined
  if ('property_type' in patch || 'room_type' in patch || 'bedrooms' in patch) {
    filters.property_type = next.property_type ?? undefined
  }
  if ('amenities' in patch) filters.amenities = next.amenities ? [...next.amenities] : undefined

  if ('institution' in patch) {
    const institution = typeof patch.institution === 'string' ? patch.institution.trim() : ''
    next.institution = institution || undefined
    conversationLocation.value = institution
      ? await resolveConversationInstitution(institution)
      : null
    if (conversationLocation.value?.country && !('country' in patch)) {
      next.country = conversationLocation.value.country
    }
  }

  const commuteMinutes = patchNumber(patch.commute_minutes)
  if ('commute_minutes' in patch) {
    next.commute_minutes = commuteMinutes
    if (commuteMinutes != null) {
      conversationRadiusKm.value = Math.max(1, Math.min(20, Math.round(commuteMinutes / 3)))
    }
  }
  if ('commute_mode' in patch) next.commute_mode = typeof patch.commute_mode === 'string' ? patch.commute_mode : undefined

  conversationFilters.value = next
  currentPage.value = 1
  if (refreshResults) await doSearch()
}

/** 通过公寓 ID 将右侧户型推荐同步到中间的公寓搜索结果。 */
function showAgentRecommendations(
  recommendations: AgentRecommendation[],
  total = recommendations.length,
) {
  const uniqueRecommendations = uniqueAgentRecommendations(recommendations)
  agentResultRecommendations.value = uniqueRecommendations
  latestRecommendationCount.value = Math.max(
    total,
    uniqueRecommendations.length,
  )
  fromAgent.value = true
  agentContext.value = { filters: { ...effectiveAgentFilters.value }, total: latestRecommendationCount.value }
  currentPage.value = 1
}

/** 新建或切换对话时，只清除对话提取条件，保留左侧人工筛选。 */
function resetConversationContext() {
  conversationFilters.value = {}
  conversationLocation.value = null
  conversationRadiusKm.value = 5
  agentFilterSynced.value = false
  agentResultRecommendations.value = null
  fromAgent.value = false
  agentContext.value = null
  latestRecommendationCount.value = 0
  pendingAgentClearedFilters.value = []
  void doSearch()
}

function consumeAgentClearedFilters(fields: AgentFilterField[]) {
  const consumed = new Set(fields)
  pendingAgentClearedFilters.value = pendingAgentClearedFilters.value
    .filter((field) => !consumed.has(field))
}

watch(agentOpen, () => {
  nextTick(() => {
    if (viewMode.value === 'map' && mapInstance) {
      const google = (window as any).google
      google?.maps?.event?.trigger(mapInstance, 'resize')
      renderMarkers()
    }
  })
})

function compactRecord(source: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(source).filter(([, value]) => (
      value !== undefined
      && value !== null
      && value !== ''
      && (!Array.isArray(value) || value.length > 0)
    )),
  )
}

function currentRouteQuery(): Record<string, string> {
  const query: Record<string, string> = {}
  for (const [key, value] of Object.entries(route.query)) {
    if (typeof value === 'string') query[key] = value
  }
  if (activeSearchId) query.search_id = activeSearchId
  return query
}

function buildSearchWorkspace(): AgentSearchWorkspace {
  return {
    search_id: activeSearchId,
    route_query: currentRouteQuery(),
    manual_filters: compactRecord({
      q: filters.q,
      country: filters.country,
      city: filters.city,
      district: filters.district,
      institute_id: filters.institute_id,
      price_min: filters.price_min,
      price_max: filters.price_max,
      bedrooms: filters.bedrooms,
      property_type: filters.property_type,
      amenities: filters.amenities,
    }),
    ui_state: compactRecord({
      search_mode: searchMode.value,
      school_id: schoolId.value,
      school_name: schoolName.value,
      uni_id: uniId.value,
      uni_name: uniName.value,
      uni_lat: uniLat.value,
      uni_lng: uniLng.value,
      uni_radius: uniRadius.value,
      selected_uni_id: selectedUniId.value,
      sort_by: sortBy.value,
      view_mode: viewMode.value,
      commute_time: commuteTime.value,
      distance_filter: distanceFilter.value,
      duration_filter: durationFilter.value,
    }),
  }
}

async function persistSearchWorkspace(): Promise<void> {
  if (!activeSearchId || restoringWorkspace || agentChatStore.sessionId === null) return
  const workspace = buildSearchWorkspace()
  const task = agentChatStore.saveSearchWorkspace(workspace)
  workspaceSave = task
  try {
    await task
  } catch {
    // 搜索结果仍可使用；下一次筛选变化或进入全页 AI 时会再次保存。
  } finally {
    if (workspaceSave === task) workspaceSave = null
  }
}

function resetSearchWorkspaceState(): void {
  filters.q = ''
  filters.country = undefined
  filters.city = undefined
  filters.district = undefined
  filters.price_min = undefined
  filters.price_max = undefined
  filters.property_type = undefined
  filters.institute_id = undefined
  filters.amenities = undefined
  schoolId.value = null
  schoolName.value = ''
  uniId.value = null
  uniName.value = ''
  uniLat.value = null
  uniLng.value = null
  selectedUniId.value = null
  uniRadius.value = 5
  searchMode.value = 'city'
  sortBy.value = 'default'
  viewMode.value = 'grid'
  conversationFilters.value = {}
  conversationLocation.value = null
  conversationRadiusKm.value = 5
  agentFilterSynced.value = false
  agentResultRecommendations.value = null
  fromAgent.value = false
  agentContext.value = null
  latestRecommendationCount.value = 0
  pendingAgentClearedFilters.value = []
}

async function hydrateSearchWorkspace(
  workspace: AgentSearchWorkspace,
  conversation: Record<string, unknown>,
): Promise<void> {
  restoringWorkspace = true
  resetSearchWorkspaceState()
  activeSearchId = workspace.search_id
  lastHandledSearchId = workspace.search_id

  const manual = workspace.manual_filters
  filters.q = typeof manual.q === 'string' ? manual.q : ''
  filters.country = typeof manual.country === 'string' ? manual.country : undefined
  filters.city = typeof manual.city === 'string' ? manual.city : undefined
  filters.district = typeof manual.district === 'string' ? manual.district : undefined
  filters.institute_id = typeof manual.institute_id === 'number' ? manual.institute_id : undefined
  filters.price_min = typeof manual.price_min === 'number' ? manual.price_min : undefined
  filters.price_max = typeof manual.price_max === 'number' ? manual.price_max : undefined
  filters.bedrooms = typeof manual.bedrooms === 'number' ? manual.bedrooms : undefined
  filters.property_type = typeof manual.property_type === 'string'
    ? manual.property_type as PropertyType
    : undefined
  filters.amenities = Array.isArray(manual.amenities)
    ? manual.amenities.map(String)
    : undefined

  const ui = workspace.ui_state
  if (['city', 'school', 'uni', 'agent'].includes(String(ui.search_mode))) {
    searchMode.value = ui.search_mode as typeof searchMode.value
  }
  schoolId.value = typeof ui.school_id === 'number' ? ui.school_id : null
  schoolName.value = typeof ui.school_name === 'string' ? ui.school_name : ''
  uniId.value = typeof ui.uni_id === 'number' ? ui.uni_id : null
  uniName.value = typeof ui.uni_name === 'string' ? ui.uni_name : ''
  uniLat.value = typeof ui.uni_lat === 'number' ? ui.uni_lat : null
  uniLng.value = typeof ui.uni_lng === 'number' ? ui.uni_lng : null
  uniRadius.value = typeof ui.uni_radius === 'number' ? ui.uni_radius : 5
  selectedUniId.value = typeof ui.selected_uni_id === 'number' ? ui.selected_uni_id : null
  sortBy.value = typeof ui.sort_by === 'string' ? ui.sort_by : 'default'
  viewMode.value = ui.view_mode === 'map' ? 'map' : 'grid'
  commuteTime.value = typeof ui.commute_time === 'number' ? ui.commute_time : null
  distanceFilter.value = typeof ui.distance_filter === 'number' ? ui.distance_filter : null
  durationFilter.value = typeof ui.duration_filter === 'string' ? ui.duration_filter : null

  await applyAgentFilterPatch(conversation, false)
  agentFilterSynced.value = Object.keys(conversation).length > 0
  agentOpen.value = true
  restoringWorkspace = false
}

async function openFullPageAi(): Promise<void> {
  await persistSearchWorkspace()
  if (workspaceSave) await workspaceSave.catch(() => undefined)
  await router.push({
    name: 'ai-search',
    query: agentChatStore.sessionId !== null
      ? { session: String(agentChatStore.sessionId) }
      : {},
  })
}

// ── 搜索 ──
async function doSearch() {
  currentPage.value = 1
  const p: PropertySearchParams = {}
  const effective = effectiveAgentFilters.value

  if (agentResultRecommendations.value !== null) {
    const instituteIds = [...new Set(
      agentResultRecommendations.value
        .map((recommendation) => Number(recommendation.property?.institute_id))
        .filter((id) => Number.isInteger(id) && id > 0),
    )]
    void persistSearchWorkspace()
    if (!instituteIds.length) {
      searchResults.value = []
      return
    }
    await propertyStore.fetchSearch({
      institute_ids: instituteIds,
      limit: instituteIds.length,
    })
    return
  }

  if (hasManualConversationConflict.value) {
    searchResults.value = []
    void persistSearchWorkspace()
    return
  }

  if (effective.country) p.country = effective.country
  if (effective.city) p.city = effective.city
  if (effective.district) p.district = effective.district
  if (effective.institute_id != null) p.institute_id = effective.institute_id

  if (filters.q) p.q = filters.q
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
  if (effective.price_min != null) p.price_min = effective.price_min
  if (effective.price_max != null) p.price_max = effective.price_max
  if (effective.property_type) p.property_type = effective.property_type as PropertyType
  if (effective.amenities?.length) p.amenities = effective.amenities

  // 对话中提取的学校位置优先；否则沿用左侧大学/地址半径。
  if (conversationLocation.value) {
    p.near_lat = conversationLocation.value.lat
    p.near_lng = conversationLocation.value.lng
    p.near_distance_km = conversationRadiusKm.value
  } else if (uniLat.value != null && uniLng.value != null) {
    p.near_lat = uniLat.value; p.near_lng = uniLng.value
    p.near_distance_km = uniRadius.value
  }

  // 排序（非通勤排序发送到后端）
  if (sortBy.value && !['commute_time', 'commute_dist'].includes(sortBy.value)) {
    p.sort_by = sortBy.value
  }

  // limit 由后端默认值控制；结果始终是 main 的 Building 聚合卡片。
  void persistSearchWorkspace()
  await propertyStore.fetchSearch(p)
}

/** 半径变更 → 重新搜索 */
function onRadiusChange() {
  // 更新 URL 并重新搜索
  if (uniId.value) {
    router.replace({
      path: '/search',
      query: {
        ...route.query,
        uni_id: String(uniId.value),
        radius: String(uniRadius.value),
        uni_name: uniName.value,
      }
    })
  }
  doSearch()
}

/** 通勤筛选变更（纯客户端筛选，不需要重新请求后端） */
function onCommuteFilterChange() {
  currentPage.value = 1
  void persistSearchWorkspace()
}

/** 排序变更 — 后端排序需重新请求，客户端排序仅重置分页 */
function onSortChange() {
  currentPage.value = 1
  void persistSearchWorkspace()
  if (sortBy.value && !['commute_time', 'commute_dist'].includes(sortBy.value)) {
    doSearch() // 后端排序需要重新请求
  }
  // 客户端排序：filteredAndSortedResults 自动响应
}

function resetFilters() {
  filters.q = ''; filters.country = undefined; filters.city = undefined; filters.district = undefined; filters.price_min = undefined
  filters.price_max = undefined; filters.property_type = undefined
  filters.institute_id = undefined; filters.amenities = undefined
  schoolId.value = null; schoolName.value = ''; searchMode.value = 'city'
  uniId.value = null; uniName.value = ''; uniLat.value = null; uniLng.value = null; selectedUniId.value = null
  sortBy.value = 'default'
  agentResultRecommendations.value = null
  fromAgent.value = false
  agentContext.value = null
  latestRecommendationCount.value = 0
  doSearch()
}

/** 一次普通搜索绑定一个空会话，但不会把搜索文字发送给 AI。 */
async function prepareNormalSearch(searchId: string): Promise<boolean> {
  if (!searchId) return false
  if (searchId === lastHandledSearchId && activeSearchId === searchId) return true
  lastHandledSearchId = searchId

  try {
    const hasAgentIdentity = Boolean(
      localStorage.getItem('access_token') || localStorage.getItem('guest_token'),
    )
    const restored = hasAgentIdentity
      ? await agentChatStore.findAndRestoreSearchWorkspace(searchId)
      : null
    if (restored) {
      await hydrateSearchWorkspace(restored.workspace, restored.conversation_filters)
      return true
    }

    // 只有后端确认该 search_id 从未绑定时，才把它视为真正的新搜索。
    resetSearchWorkspaceState()
    activeSearchId = searchId
    await agentChatStore.prepareForSearch()
    agentOpen.value = true
    return false
  } catch {
    ElMessage.error('原搜索对话恢复失败，请稍后重试')
    throw new Error('搜索工作区恢复失败')
  }
}

// ── 路由初始化 ──
async function initFromRoute() {
  const q = route.query
  let restoredWorkspace = false

  if (typeof q.search_id === 'string') {
    try {
      restoredWorkspace = await prepareNormalSearch(q.search_id)
    } catch {
      return
    }
  }

  if (restoredWorkspace) {
    await doSearch()
    return
  }

  // 兼容旧 AI 页面写入的上下文，但不再把 UnitType 推荐注入 Building 结果列表。
  const agentCtxJson = sessionStorage.getItem('agentSearchContext')
  if (q.from === 'agent' && agentCtxJson) {
    try {
      const ctx = JSON.parse(agentCtxJson)
      if (ctx?.filters && typeof ctx.filters === 'object') {
        await applyAgentFilterPatch(ctx.filters as Record<string, unknown>, false)
        fromAgent.value = true
        agentContext.value = ctx
      }
    } catch { /* fallback */ }
    sessionStorage.removeItem('agentSearchContext')
    sessionStorage.removeItem('agentSearchResults')
  }

  // 大学近距搜索
  if (q.uni_id) {
    uniId.value = Number(q.uni_id)
    uniName.value = (q.uni_name as string) || ''
    uniRadius.value = Number(q.radius) || 5
    searchMode.value = 'uni'
    filters.district = undefined
    filters.institute_id = undefined

    // 从 API 获取大学坐标
    try {
      const unis = await universityService.search('', 50)
      const found = unis.find((university) => university.id === uniId.value)
      if (found?.latitude && found?.longitude) {
        uniLat.value = found.latitude
        uniLng.value = found.longitude
        uniName.value = found.name_cn || found.name || uniName.value
      }
      if (found) {
        saveRecentHousingSearch({
          kind: 'school', schoolId: found.id, schoolName: found.name_cn || found.name,
          latitude: found.latitude ?? undefined, longitude: found.longitude ?? undefined,
          radiusKm: uniRadius.value, city: found.city ?? undefined, country: found.country ?? undefined,
        })
      }
    } catch { /* fallback: use hardcoded */ }
  } else if (q.school_id) {
    const routeSchoolId = Number(q.school_id)
    const school = Number.isInteger(routeSchoolId) && routeSchoolId > 0
      ? SCHOOL_INFO[routeSchoolId]
      : undefined
    searchMode.value = 'school'
    schoolId.value = Number.isInteger(routeSchoolId) && routeSchoolId > 0 ? routeSchoolId : null
    schoolName.value = school?.name || ''
    uniName.value = school?.name || ''
    uniLat.value = school?.lat ?? null
    uniLng.value = school?.lng ?? null
    uniRadius.value = Number(q.radius) || 5
    filters.institute_id = undefined
    filters.district = undefined
    if (school) {
      saveRecentHousingSearch({
        kind: 'school', schoolId: routeSchoolId, schoolName: school.name,
        latitude: school.lat, longitude: school.lng, radiusKm: uniRadius.value,
        city: school.city, country: school.country,
      })
    }
  } else if (q.institute_id) {
    const routeInstituteId = Number(q.institute_id)
    searchMode.value = 'city'
    schoolId.value = null
    schoolName.value = ''
    uniId.value = null
    uniName.value = ''
    uniLat.value = null
    uniLng.value = null
    selectedUniId.value = null
    filters.institute_id = Number.isInteger(routeInstituteId) && routeInstituteId > 0
      ? routeInstituteId
      : undefined
    filters.district = undefined
  } else if (q.district) {
    searchMode.value = 'city'; filters.district = q.district as string
    filters.institute_id = undefined; schoolName.value = ''
  }
  if (q.country) filters.country = normalizeCountry(q.country)
  if (q.city) filters.city = q.city as string
  if (q.district) {
    saveRecentHousingSearch({
      kind: 'district', district: q.district as string,
      city: filters.city, country: normalizeCountry(q.country),
    })
  } else if (q.city) {
    saveRecentHousingSearch({ kind: 'city', city: filters.city, country: normalizeCountry(q.country) })
  }
  const hasStructuredSearch = Boolean(
    q.uni_id || q.school_id || q.institute_id || q.city || q.district,
  )
  if (q.q && !hasStructuredSearch) filters.q = q.q as string
  if (q.price_min) filters.price_min = Number(q.price_min) || undefined
  if (q.price_max) filters.price_max = Number(q.price_max) || undefined
  if (q.bedrooms) filters.bedrooms = Number(q.bedrooms) || undefined
  if (q.property_type) filters.property_type = q.property_type as PropertyType
  await doSearch()
}
onMounted(async () => {
  if (authStore.isLoggedIn && !cartStore.loaded) await cartStore.fetch()
  await initFromRoute()
})
onUnmounted(() => {
  void persistSearchWorkspace()
  destroyMap()
})
watch(() => route.query, () => { void initFromRoute() })
</script>

<style scoped>
.search-page {
  flex: 1;
  min-height: 0;
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
  overflow-x: hidden;
  overflow-y: auto; /* 筛选栏内部滚动 */
}
.sidebar-title-row {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 14px; padding-bottom: 10px;
  border-bottom: 2px solid var(--primary);
}
.sidebar-title { font-size: 15px; font-weight: 700; color: var(--text-primary); }
.agent-synced-filters {
  margin: -2px 0 14px; padding: 10px; border: 1px solid #cfe1f2;
  border-radius: 8px; background: #f2f8fe;
}
.agent-synced-title {
  margin-bottom: 7px; display: flex; align-items: center; gap: 5px;
  color: #35658f; font-size: 11px; font-weight: 700;
}
.agent-synced-chips { display: flex; flex-wrap: wrap; gap: 5px; }
.agent-synced-chips span {
  max-width: 100%; padding: 3px 7px; overflow: hidden; color: #3e6385;
  background: #fff; border: 1px solid #d8e6f3; border-radius: 999px;
  font-size: 10.5px; text-overflow: ellipsis; white-space: nowrap;
}
.location-inputs { display: flex; flex-direction: column; gap: 7px; }

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

/* ── 便利设施两列网格：允许长标签换行，不撑宽筛选栏 ── */
.amenity-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px 8px;
}
.amenity-grid .el-checkbox {
  min-width: 0;
  margin-right: 0;
  font-size: 12px;
  height: auto;
  min-height: 24px;
  white-space: normal;
}
.amenity-grid .el-checkbox__label {
  min-width: 0;
  padding-left: 5px;
  line-height: 1.3;
  overflow-wrap: anywhere;
  white-space: normal;
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
.results-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 14px; padding: 0 4px; flex-shrink: 0; }
.results-heading { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.results-count { font-size: 14px; color: var(--text-secondary); }
.results-hierarchy-note { color: #909399; font-size: 11px; }
.results-actions { display: flex; gap: 6px; flex-shrink: 0; }
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

/* Building 搜索卡使用后端返回的代表 UnitType 执行候选清单操作。 */
.building-result { min-width: 0; }
.building-result :deep(.property-card) { height: 100%; }

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

.agent-dock {
  width: 390px; min-width: 340px; max-width: 420px; flex: 0 0 30vw;
  min-height: 0; position: relative; z-index: 4;
}
.agent-panel-loading {
  height: 100%; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 8px; color: #909399; background: #fff;
  border: 1px solid var(--border); border-radius: 12px;
}
.agent-backdrop { display: none; }

@media (max-width: 1200px) { .card-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 1150px) {
  .agent-dock {
    position: fixed; z-index: 30; top: 74px; right: 12px; bottom: 12px;
    width: min(430px, calc(100vw - 24px)); max-width: none; min-width: 0;
  }
  .agent-backdrop {
    display: block; position: fixed; z-index: 29; inset: 0; border: 0;
    background: rgba(15, 23, 42, .28); cursor: default;
  }
}
@media (max-width: 900px) {
  .search-layout { flex-direction: column; }
  .filter-sidebar { width: 100%; position: static; max-height: none; }
  .card-grid { grid-template-columns: 1fr; }
  .results-top { align-items: flex-start; flex-direction: column; }
}
</style>

<style>
</style>
