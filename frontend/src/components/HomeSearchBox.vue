<!-- 首页统一搜索框：标语 + 搜索/AI对话 Tab + 搜索栏 + 建议下拉 + 快捷标签 -->
<template>
  <div class="home-search-box">
    <!-- 标语 -->
    <h1 class="hero-slogan">智能找房，一句话就够了</h1>

    <!-- 模式切换 Tab -->
    <div class="search-tabs">
      <button
        :class="['tab-btn', { active: activeTab === 'search' }]"
        @click="switchTab('search')"
      >
        <el-icon :size="16"><Search /></el-icon>
        <span>搜索</span>
      </button>
      <button
        :class="['tab-btn', { active: activeTab === 'ai' }]"
        @click="switchTab('ai')"
      >
        <el-icon :size="16"><ChatDotRound /></el-icon>
        <span>AI对话</span>
      </button>
    </div>

    <!-- 统一搜索栏 -->
    <div class="search-bar-wrapper">
      <!-- ═══ 搜索模式：带建议下拉 ═══ -->
      <template v-if="activeTab === 'search'">
        <el-input
          ref="searchInputRef"
          v-model="query"
          :placeholder="searchPlaceholder"
          :prefix-icon="Search"
          size="large"
          class="unified-input"
          @focus="onSearchFocus"
          @blur="onSearchBlur"
          @input="onSearchInput"
          @keyup.enter="handleSearchSubmit"
        >
          <template #suffix>
            <el-button
              type="primary"
              :disabled="!query.trim()"
              @click="handleSearchSubmit"
              class="search-submit-btn"
              aria-label="搜索"
            ><el-icon :size="18"><Search /></el-icon></el-button>
          </template>
        </el-input>
        <!-- 建议下拉 -->
        <transition name="slide-down">
          <div v-if="showSuggestions" class="suggestions-panel">
            <!-- 加载中 -->
            <div v-if="suggestionsLoading" class="suggestions-loading">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>搜索中...</span>
            </div>

            <template v-else>
              <!-- 无输入：热门展示（含国家 Tab） -->
              <template v-if="!query.trim()">
                <!-- 国家 Tab -->
                <div class="suggestions-tabs">
                  <span
                    v-for="ct in countryTabs"
                    :key="ct.key"
                    :class="['suggestions-tab', { active: popularCountry === ct.key }]"
                    @mousedown.prevent="popularCountry = ct.key"
                  >{{ ct.label }}</span>
                </div>

                <!-- 热门城市（非 SG 时展示） -->
                <div v-if="popularCountry !== 'SG' && filteredCities.length > 0" class="suggestion-section">
                  <div class="section-title">城市</div>
                  <div class="suggestion-grid">
                    <div
                      v-for="city in filteredCities"
                      :key="'pop-city-' + city.query.district + city.query.country"
                      class="suggestion-card"
                      @mousedown.prevent="selectPopularCity(city)"
                    >
                      <span class="card-name">{{ cityLabel(city) }}</span>
                      <span class="card-sub">{{ city.count }} 套房源</span>
                    </div>
                  </div>
                </div>

                <!-- 热门大学 -->
                <div class="suggestion-section">
                  <div class="section-title">大学</div>
                  <div class="suggestion-grid school-grid">
                    <div
                      v-for="uni in filteredUniversities"
                      :key="'pop-uni-' + uni.id"
                      class="suggestion-card"
                      @mousedown.prevent="selectPopularUniversity(uni)"
                    >
                      <span class="card-name">{{ popularUniDisplay(uni) }}</span>
                      <span class="card-sub">{{ uni.city || '' }}</span>
                    </div>
                  </div>
                  <div v-if="filteredUniversities.length === 0" class="suggestions-empty">
                    暂无数据
                  </div>
                </div>
              </template>

              <!-- 有输入：匹配结果 -->
              <template v-else>
                <!-- 匹配大学 -->
                <div v-if="matchingUniversities.length > 0" class="suggestion-section">
                  <div class="section-title">匹配大学</div>
                  <div class="suggestion-grid school-grid">
                    <div
                      v-for="uni in matchingUniversities"
                      :key="'match-uni-' + (uni.id || uni.name)"
                      class="suggestion-card"
                      @mousedown.prevent="selectUniversity(uni)"
                    >
                      <span class="card-name">{{ uni.name_cn || uni.name }}</span>
                      <span class="card-sub">{{ uni.city || '' }}</span>
                    </div>
                  </div>
                </div>

                <!-- 匹配城市 -->
                <div v-if="matchingCities.length > 0" class="suggestion-section">
                  <div class="section-title">匹配城市</div>
                  <div class="suggestion-grid">
                    <div
                      v-for="city in matchingCities"
                      :key="'match-city-' + city.query.district + city.query.country"
                      class="suggestion-card"
                      @mousedown.prevent="selectMatchingCity(city)"
                    >
                      <span class="card-name">{{ cityLabel(city) }}</span>
                      <span class="card-sub">{{ city.count }} 套房源</span>
                    </div>
                  </div>
                </div>

                <!-- 匹配房源 -->
                <div v-if="matchingProperties.length > 0" class="suggestion-section">
                  <div class="section-title">匹配房源</div>
                  <div class="suggestion-grid">
                    <div
                      v-for="prop in matchingProperties"
                      :key="'match-prop-' + prop.id"
                      class="suggestion-card"
                      @mousedown.prevent="selectProperty(prop)"
                    >
                      <span class="card-name">{{ prop.title }}</span>
                      <span class="card-sub">{{ prop.district || '' }}</span>
                    </div>
                  </div>
                </div>

                <!-- 无结果 -->
                <div v-if="!hasAnySuggestions" class="suggestions-empty">
                  未找到匹配的学校或地区
                </div>
              </template>
            </template>
          </div>
        </transition>
      </template>

      <!-- ═══ AI对话模式：内嵌发送按钮 ═══ -->
      <template v-else>
        <el-input
          v-model="query"
          :placeholder="aiPlaceholder"
          size="large"
          class="unified-input ai-input"
          :disabled="aiLoading"
          @keyup.enter="handleAiSearch"
        >
          <template #prefix>
            <span style="font-size:18px">💬</span>
          </template>
          <template #suffix>
            <el-button
              type="primary"
              :loading="aiLoading"
              :disabled="!query.trim()"
              @click="handleAiSearch"
              class="send-btn"
              aria-label="发送AI查询"
            >
              <el-icon :size="18"><Promotion /></el-icon>
            </el-button>
          </template>
        </el-input>
      </template>
    </div>

    <!-- 快捷标签 -->
    <div class="hero-tags">
      <el-tag
        v-for="tag in quickTags"
        :key="tag"
        @click="handleTagClick(tag)"
        class="quick-tag"
      >{{ tag }}</el-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search, ChatDotRound, Promotion, Loading } from '@element-plus/icons-vue'
import api from '@/services/api'
import { propertyService } from '@/services/property'
import { formatPrice } from '@/data/currency'

// ── 类型 ─────────────────────────────────

type SearchTab = 'search' | 'ai'

interface SuggestionCity {
  type: string
  name: string
  country: string
  count: number
  query: { district: string; country: string }
}

interface SuggestionUniversity {
  type: string
  id: number
  name: string
  name_cn?: string | null
  abbreviation?: string | null
  city?: string | null
  country?: string | null
}

interface SuggestionProperty {
  type: string
  id: number
  title: string
  district: string
  price_monthly: number | null
  currency?: string
}

interface PopularUniversity {
  id: number
  name: string
  name_cn?: string | null
  abbreviation?: string | null
  city?: string | null
  country?: string | null
}

// ── 路由 ─────────────────────────────────

const router = useRouter()

// ── 模式 ─────────────────────────────────

const activeTab = ref<SearchTab>('search')

function switchTab(tab: SearchTab) {
  activeTab.value = tab
  showSuggestions.value = false
  // 保留已输入的文本
}

// ── 输入 ─────────────────────────────────

const query = ref('')
const searchPlaceholder = '搜索城市、大学或区域...'
const aiPlaceholder = '试试：NUS附近两居室 预算3000...'
const aiLoading = ref(false)

// ── 快捷标签 ─────────────────────────────

const quickTags = ['金文泰', 'NUS附近', '伦敦学生公寓']

function handleTagClick(tag: string) {
  query.value = tag
  if (activeTab.value === 'ai') {
    handleAiSearch()
  } else {
    handleSearchSubmit()
  }
}

// ── AI 模式 ──────────────────────────────

function handleAiSearch() {
  const q = query.value.trim()
  if (!q || aiLoading.value) return
  aiLoading.value = true
  router.push({ path: '/ai-search', query: { q } })
  // loading 状态随页面跳转自然解除
}

// ── 搜索模式 ─────────────────────────────

async function handleSearchSubmit() {
  const q = query.value.trim()
  if (!q) return
  showSuggestions.value = false
  // 地理编码：把地址文本转为坐标 → 直接传给搜索结果页做半径搜索
  try {
    const geo = await propertyService.geocodeAddress(q)
    if (geo.latitude && geo.longitude) {
      const query: Record<string, string> = {
        q, lat: String(geo.latitude), lng: String(geo.longitude), radius: '5',
      }
      // 传递城市信息作为补充筛选
      if (geo.city) query.geo_city = geo.city
      if (geo.district) query.geo_district = geo.district
      router.push({ name: 'search', query })
      return
    }
  } catch { /* 地理编码失败则走纯文本搜索 */ }
  router.push({ name: 'search', query: { q } })
}

// ── 建议下拉状态 ─────────────────────────

const searchInputRef = ref()
const showSuggestions = ref(false)
const suggestionsLoading = ref(false)
const matchingCities = ref<SuggestionCity[]>([])
const matchingUniversities = ref<SuggestionUniversity[]>([])
const matchingProperties = ref<SuggestionProperty[]>([])
const popularCities = ref<SuggestionCity[]>([])
const popularUniversities = ref<PopularUniversity[]>([])

let debounceTimer: ReturnType<typeof setTimeout> | null = null
let blurTimer: ReturnType<typeof setTimeout> | null = null

const hasAnySuggestions = computed(() =>
  matchingUniversities.value.length > 0 ||
  matchingCities.value.length > 0 ||
  matchingProperties.value.length > 0
)

// ── 国家 Tab ─────────────────────────────

const countryTabs = [
  { key: 'all', label: '全部' },
  { key: 'SG', label: '新加坡' },
  { key: 'GB', label: '英国' },
] as const
const popularCountry = ref<string>('all')

const filteredCities = computed(() => {
  const cities = popularCities.value
  if (popularCountry.value === 'all') return cities
  return cities.filter(c => (c.country || '').toUpperCase() === popularCountry.value)
})

const filteredUniversities = computed(() => {
  const unis = popularUniversities.value
  if (popularCountry.value === 'all') return unis
  return unis.filter(u => (u.country || '').toUpperCase() === popularCountry.value)
})

// ── 建议数据获取 ─────────────────────────

async function fetchSuggestions(q?: string) {
  suggestionsLoading.value = true
  try {
    const params: Record<string, string | number> = { limit: 30 }
    if (q?.trim()) params.q = q.trim()
    const resp = await api.get('/search/suggestions', { params })
    const data = resp.data

    if (q?.trim()) {
      matchingCities.value = data.matching_cities || []
      matchingUniversities.value = data.matching_universities || []
      matchingProperties.value = data.matching_properties || []
    } else {
      matchingCities.value = []
      matchingUniversities.value = []
      matchingProperties.value = []
      popularCities.value = (data.popular_cities || []).filter((c: any) => c.name)
      popularUniversities.value = data.popular_universities || []
    }
  } catch {
    matchingCities.value = []
    matchingUniversities.value = []
    matchingProperties.value = []
    popularCities.value = []
  } finally {
    suggestionsLoading.value = false
  }
}

// ── 输入处理（防抖 300ms）─────────────────

function onSearchInput() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    fetchSuggestions(query.value)
  }, 300)
}

function onSearchFocus() {
  if (blurTimer) clearTimeout(blurTimer)
  showSuggestions.value = true
  fetchSuggestions(query.value)
}

function onSearchBlur() {
  // 延迟关闭，让 mousedown 有时间触发
  blurTimer = setTimeout(() => {
    showSuggestions.value = false
  }, 200)
}

// ── 选择处理 ─────────────────────────────

/** 去掉 API 返回 district 中的 "国家-" 前缀 */
function cityLabel(city: SuggestionCity): string {
  const name = city.name || ''
  const idx = name.indexOf('-')
  return idx > -1 ? name.slice(idx + 1) : name
}

function popularUniDisplay(uni: PopularUniversity): string {
  if (uni.name_cn) return uni.abbreviation ? `${uni.name_cn} (${uni.abbreviation})` : uni.name_cn
  return uni.abbreviation || uni.name
}

function selectPopularCity(city: SuggestionCity) {
  showSuggestions.value = false
  router.push({ name: 'search', query: { city: city.name } })
}

function selectMatchingCity(city: SuggestionCity) {
  showSuggestions.value = false
  router.push({ name: 'search', query: { city: city.name } })
}

function selectPopularUniversity(uni: PopularUniversity | SuggestionUniversity) {
  showSuggestions.value = false
  const name = uni.name_cn || uni.name
  router.push({ name: 'search', query: { uni_id: String(uni.id), radius: '5', uni_name: name } })
}

function selectUniversity(uni: SuggestionUniversity) {
  selectPopularUniversity(uni)
}

function selectProperty(prop: SuggestionProperty) {
  showSuggestions.value = false
  router.push({ name: 'building-detail', params: { id: prop.id } })
}

// ── 点击外部关闭 ─────────────────────────

function handleClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement
  // 检查点击是否在 search-bar-wrapper 内
  const wrapper = document.querySelector('.search-bar-wrapper')
  if (wrapper && !wrapper.contains(target)) {
    showSuggestions.value = false
  }
}

// ── 生命周期 ─────────────────────────────

onMounted(() => {
  // 预加载热门数据
  fetchSuggestions()
  document.addEventListener('mousedown', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('mousedown', handleClickOutside)
  if (debounceTimer) clearTimeout(debounceTimer)
  if (blurTimer) clearTimeout(blurTimer)
})
</script>

<style scoped>
/* ── 容器 ──────────────────────────────── */

.home-search-box {
  text-align: center;
}

/* ── 标语 ──────────────────────────────── */

.hero-slogan {
  font-size: 38px;
  font-weight: 800;
  background: linear-gradient(135deg, #e94560 0%, #6c5ce7 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 20px 0;
  line-height: 1.3;
}

/* ── Tab 按钮组 ────────────────────────── */

.search-tabs {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 28px;
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 28px;
  border-radius: 24px;
  border: none;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.25s ease;
  background: #f0f0f5;
  color: #909399;
  outline: none;
  font-family: inherit;
}

.tab-btn:hover {
  background: #e8e7f0;
  color: #6c5ce7;
}

.tab-btn.active {
  background: linear-gradient(135deg, #6c5ce7, #e94560);
  color: #fff;
  box-shadow: 0 4px 16px rgba(108, 92, 231, 0.35);
}

/* ── 搜索栏外层 ────────────────────────── */

.search-bar-wrapper {
  max-width: 640px;
  margin: 0 auto;
  position: relative;
}

/* ── 统一样式的 el-input ────────────────── */

.unified-input :deep(.el-input__wrapper) {
  border-radius: 28px;
  height: 56px;
  padding: 4px 8px 4px 20px;
  background: var(--bg-white, #fff);
  border: 2px solid transparent;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
  transition: all 0.25s ease;
}

.unified-input :deep(.el-input__wrapper:hover) {
  border-color: #d0c8f0;
}

.unified-input :deep(.el-input__wrapper.is-focus) {
  border-color: #6c5ce7;
  box-shadow: 0 4px 28px rgba(108, 92, 231, 0.15);
}

.unified-input :deep(.el-input__inner) {
  font-size: 16px;
  color: var(--text-primary, #303133);
}

.unified-input :deep(.el-input__prefix) {
  color: var(--text-muted, #909399);
  font-size: 18px;
}

/* ── AI 模式：内置发送按钮 ──────────────── */

.ai-input :deep(.el-input__suffix) {
  display: flex;
  align-items: center;
  margin-right: 2px;
}

.send-btn {
  width: 44px;
  height: 44px;
  border-radius: 50% !important;
  padding: 0 !important;
  min-width: 44px;
  background: linear-gradient(135deg, #6c5ce7, #e94560) !important;
  border: none !important;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.send-btn:hover:not(:disabled) {
  opacity: 0.88;
  transform: scale(1.05);
}

.send-btn:disabled {
  background: #dcdfe6 !important;
  cursor: not-allowed;
}

/* ── 搜索模式：内置搜索按钮 ── */

.unified-input :deep(.el-input__suffix) {
  display: flex;
  align-items: center;
  margin-right: 2px;
}

.search-submit-btn {
  height: 44px;
  width: 44px;
  border-radius: 50% !important;
  padding: 0 !important;
  background: linear-gradient(135deg, #6c5ce7, #e94560) !important;
  border: none !important;
  font-size: 15px;
  font-weight: 600;
  transition: all 0.2s ease;
}

.search-submit-btn:hover:not(:disabled) {
  opacity: 0.88;
}

.search-submit-btn:disabled {
  background: #dcdfe6 !important;
  cursor: not-allowed;
}

/* ── 快捷标签 ───────────────────────────── */

.hero-tags {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: 24px;
  flex-wrap: wrap;
}

.quick-tag {
  cursor: pointer;
  border-radius: 20px;
  padding: 4px 18px;
  font-size: 14px;
  border: 1px solid #e0e0f0;
  background: #fff;
  color: #6c5ce7;
  transition: all 0.2s;
}

.quick-tag:hover {
  background: #6c5ce7;
  color: #fff;
  border-color: #6c5ce7;
}

/* ── 建议下拉面板 ───────────────────────── */

.suggestions-panel {
  position: absolute;
  top: calc(100% + 10px);
  left: 0;
  right: 0;
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-light, #ebeef5);
  border-radius: 16px;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.12);
  max-height: 480px;
  overflow-y: auto;
  z-index: 200;
  padding: 16px 20px;
  text-align: left;
}

.suggestions-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  color: var(--text-muted, #909399);
  font-size: 13px;
}

.suggestion-section {
  margin-bottom: 16px;
}

.suggestion-section:last-child {
  margin-bottom: 0;
}

.suggestion-section + .suggestion-section {
  border-top: 1px solid var(--border-light, #f0f0f0);
  padding-top: 16px;
}

.section-title {
  padding: 0 0 12px 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted, #909399);
  letter-spacing: 0.5px;
}

/* ── Grid 卡片布局 ── */

.suggestion-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}

.suggestion-grid.school-grid {
  grid-template-columns: repeat(2, 1fr);
}

.suggestion-card {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  background: var(--bg, #fafafa);
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.suggestion-card:hover {
  background: var(--primary-light, #ecf5ff);
  border-color: var(--primary, #ff6b35);
}

.suggestion-card .card-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary, #303133);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.suggestion-card .card-sub {
  font-size: 11px;
  color: var(--text-muted, #909399);
  flex-shrink: 0;
}

.suggestions-empty {
  padding: 32px 16px;
  text-align: center;
  color: var(--text-muted, #909399);
  font-size: 13px;
}

/* ── 建议面板内国家 Tab ── */

.suggestions-tabs {
  display: flex;
  gap: 4px;
  padding: 0 0 12px 0;
  border-bottom: 1px solid var(--border-light, #ebeef5);
  margin-bottom: 8px;
}

.suggestions-tab {
  padding: 4px 14px;
  border-radius: 14px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted, #909399);
  cursor: pointer;
  transition: all 0.2s;
  background: transparent;
}

.suggestions-tab:hover {
  color: var(--primary, #ff6b35);
  background: var(--primary-light, #ecf5ff);
}

.suggestions-tab.active {
  color: #fff;
  background: var(--primary, #ff6b35);
  font-weight: 600;
}

/* ── 过渡动画 ── */

.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.25s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ── 响应式 ── */

@media (max-width: 768px) {
  .hero-slogan {
    font-size: 26px;
    margin-bottom: 16px;
  }

  .tab-btn {
    padding: 8px 18px;
    font-size: 14px;
  }

  .search-tabs {
    margin-bottom: 20px;
  }

  .unified-input :deep(.el-input__wrapper) {
    height: 50px;
    padding-left: 14px;
  }

  .unified-input :deep(.el-input__inner) {
    font-size: 15px;
  }

  .suggestions-panel {
    max-height: 360px;
    padding: 12px 14px;
  }

  .suggestion-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .suggestion-grid.school-grid {
    grid-template-columns: 1fr;
  }

  .send-btn {
    width: 38px;
    height: 38px;
    min-width: 38px;
  }
}
</style>
