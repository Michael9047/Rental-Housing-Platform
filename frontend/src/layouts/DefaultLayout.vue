<template>
  <el-container class="layout-container">
    <!-- Top Navigation -->
    <el-header class="layout-header">
      <div class="header-left">
        <router-link to="/" class="logo">
          <span class="logo-icon">🏠</span>
          <span class="logo-text">AI全球公寓租赁</span>
        </router-link>
      </div>

      <div class="header-center">
        <!-- 候选清单入口 -->
        <el-badge v-if="authStore.isLoggedIn" :value="cartStore.count" :hidden="cartStore.count === 0" :max="99" class="cart-badge">
          <el-button :icon="ShoppingCart" circle class="cart-btn" @click="router.push('/cart')" />
        </el-badge>
        <div class="header-search-area">
          <div class="header-search-wrapper" :class="{ focused: searchFocused }">
            <el-input
              ref="searchInputRef"
              v-model="searchQuery"
              placeholder="搜索学校、城市或地区..."
              :prefix-icon="Search"
              class="search-input"
              size="large"
              @keyup.enter="handleSearchSubmit"
              @focus="onSearchFocus"
              @blur="onSearchBlur"
              @input="onSearchInput"
            />
            <el-button type="primary" @click="handleSearchSubmit" class="search-btn">搜索</el-button>
          </div>

          <!-- 搜索建议下拉 -->
          <div v-if="showSuggestions" class="search-suggestions">
            <!-- 加载中 -->
            <div v-if="suggestionsLoading" class="suggestions-loading">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>搜索中...</span>
            </div>

            <template v-else>
              <!-- 无搜索词时展示热门 -->
              <template v-if="!searchQuery.trim()">
                <!-- 热门大学：从 API 获取 -->
                <div class="suggestions-group">
                  <div class="suggestions-group-title">热门大学（5km 内搜房）</div>
                  <div class="suggestion-grid school-grid">
                    <div
                      v-for="uni in popularUniversities"
                      :key="uni.id"
                      class="suggestion-card"
                      @mousedown.prevent="selectPopularUniversity(uni)"
                    >
                      <span class="card-name">{{ popularUniDisplay(uni) }}</span>
                      <span class="card-sub">{{ uni.city || '' }}</span>
                    </div>
                  </div>
                </div>

                <!-- 热门城市 -->
                <div v-if="matchingCities.length > 0" class="suggestions-group">
                  <div class="suggestions-group-title">热门城市</div>
                  <div class="suggestion-grid">
                    <div
                      v-for="city in matchingCities"
                      :key="'city-' + city.name"
                      class="suggestion-card"
                      @mousedown.prevent="selectCity(city)"
                    >
                      <span class="card-name">{{ cityLabel(city) }}</span>
                      <span class="card-sub">{{ city.count }} 套房源</span>
                    </div>
                  </div>
                </div>
              </template>

              <!-- 有搜索词时展示匹配 -->
              <template v-else>
                <!-- 匹配学校 -->
                <div v-if="matchingSchools.length > 0" class="suggestions-group">
                  <div class="suggestions-group-title">匹配学校</div>
                  <div class="suggestion-grid school-grid">
                    <div
                      v-for="school in matchingSchools"
                      :key="'school-' + school.id"
                      class="suggestion-card"
                      @mousedown.prevent="selectSchool(school)"
                    >
                      <span class="card-name">{{ school.name }}</span>
                      <span class="card-sub">{{ school.count }} 套房源</span>
                    </div>
                  </div>
                </div>

                <!-- 匹配城市 -->
                <div v-if="matchingCities.length > 0" class="suggestions-group">
                  <div class="suggestions-group-title">匹配城市</div>
                  <div class="suggestion-grid">
                    <div
                      v-for="city in matchingCities"
                      :key="'city-' + city.name"
                      class="suggestion-card"
                      @mousedown.prevent="selectCity(city)"
                    >
                      <span class="card-name">{{ cityLabel(city) }}</span>
                      <span class="card-sub">{{ city.count }} 套房源</span>
                    </div>
                  </div>
                </div>

                <!-- 匹配房源 -->
                <div v-if="matchingProperties.length > 0" class="suggestions-group">
                  <div class="suggestions-group-title">匹配房源</div>
                  <div class="suggestion-grid">
                    <div
                      v-for="prop in matchingProperties"
                      :key="'prop-' + prop.id"
                      class="suggestion-card"
                      @mousedown.prevent="selectProperty(prop)"
                    >
                      <span class="card-name">{{ prop.title }}</span>
                      <span class="card-sub">{{ prop.district }} · ¥{{ prop.price_monthly }}/月</span>
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
        </div>
      </div>

      <div class="header-right">
        <template v-if="authStore.isLoggedIn">
          <el-tag v-if="authStore.isAdmin" type="danger" size="small" effect="dark">管理员</el-tag>
          <el-tag v-else-if="authStore.isLandlord" type="warning" size="small" effect="dark">公寓运营商</el-tag>
          <el-tag v-else-if="authStore.isMaintenance" type="success" size="small" effect="dark">维修师傅</el-tag>
          <el-tag v-else-if="authStore.isBdManager" type="" size="small" effect="dark" style="background-color: #8b5cf6; border-color: #8b5cf6; color: #fff;">商务拓展</el-tag>
          <el-tag v-else type="info" size="small" effect="plain">租客</el-tag>

          <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99">
            <el-button :icon="Bell" circle @click="router.push('/notifications')" />
          </el-badge>

          <el-dropdown trigger="click">
            <span class="user-dropdown">
              <el-avatar :size="34" :icon="UserFilled" />
              <span class="username">{{ authStore.user?.username }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <!-- 租客菜单 -->
                <template v-if="!authStore.isLandlord && !authStore.isAdmin && !authStore.isMaintenance && !authStore.isBdManager">
                  <el-dropdown-item @click="router.push('/profile')">
                    <el-icon><User /></el-icon> 个人中心
                  </el-dropdown-item>
                  <el-dropdown-item @click="router.push('/bookings/tenant')">
                    <el-icon><List /></el-icon> 我的预订
                  </el-dropdown-item>
                </template>
                <!-- 房东/管理员菜单 -->
                <template v-if="authStore.isLandlord || authStore.isAdmin">
                  <el-dropdown-item @click="router.push('/workspace')">
                    <el-icon><DataAnalysis /></el-icon> 运营工作台
                  </el-dropdown-item>
                  <el-dropdown-item @click="router.push('/bookings/landlord')">
                    <el-icon><Tickets /></el-icon> 预约管理
                  </el-dropdown-item>
                  <el-dropdown-item @click="router.push('/property/manage')">
                    <el-icon><Setting /></el-icon> 房源管理
                  </el-dropdown-item>
                  <el-dropdown-item @click="router.push('/property/create')">
                    <el-icon><Plus /></el-icon> 发布房源
                  </el-dropdown-item>
                </template>
                <!-- 维修师傅菜单 -->
                <template v-if="authStore.isMaintenance">
                  <el-dropdown-item @click="router.push('/worker/dashboard')">
                    <el-icon><DataAnalysis /></el-icon> 工单中心
                  </el-dropdown-item>
                </template>
                <!-- BD经理菜单 -->
                <template v-if="authStore.isBdManager">
                  <el-dropdown-item @click="router.push('/bd/dashboard')">
                    <el-icon><DataAnalysis /></el-icon> 数据台
                  </el-dropdown-item>
                  <el-dropdown-item @click="router.push('/property/manage')">
                    <el-icon><Setting /></el-icon> 房源管理
                  </el-dropdown-item>
                  <el-dropdown-item @click="router.push('/property/create')">
                    <el-icon><Plus /></el-icon> 发布房源
                  </el-dropdown-item>
                </template>
                <el-dropdown-item v-if="authStore.isAdmin" @click="router.push('/admin')">
                  <el-icon><DataAnalysis /></el-icon> 系统管理
                </el-dropdown-item>
                <el-dropdown-item v-if="authStore.isAdmin" @click="router.push('/admin/escalated-repairs')">
                  <el-icon><Tickets /></el-icon> 待派单工单
                </el-dropdown-item>
                <el-dropdown-item v-if="authStore.isAdmin" @click="router.push('/admin/landlord-workers')">
                  <el-icon><List /></el-icon> 房东维修工看板
                </el-dropdown-item>
                <el-dropdown-item divided @click="authStore.logout()">
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
        <template v-else>
          <el-button type="primary" @click="router.push('/login')" round>登录</el-button>
          <el-button @click="router.push('/register')" round>注册</el-button>
        </template>
      </div>
    </el-header>

    <el-container class="layout-body">
      <!-- 全局侧边栏 -->
      <GlobalSidebar v-if="authStore.isLandlord || authStore.isAdmin || authStore.isMaintenance || authStore.isBdManager" />
      <el-main class="layout-main">
        <div class="back-bar" v-if="route.path !== '/'">
          <el-button text :icon="ArrowLeft" @click="router.back()">返回上一页</el-button>
        </div>
        <router-view />
        <GlobalFooter v-if="!route.meta.hideFooter" />
      </el-main>
    </el-container>

  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Search, User, UserFilled, ArrowDown, ArrowLeft, Setting, SwitchButton,
  Plus, List, Bell, ChatDotRound, DataAnalysis, Tickets, Loading, ShoppingCart,} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useAgentChatStore } from '@/stores/agentChat'
import { useCartStore } from '@/stores/cart'
import { notificationService } from '@/services/notification'
import api from '@/services/api'
import GlobalFooter from '@/components/GlobalFooter.vue'
import GlobalSidebar from '@/components/GlobalSidebar.vue'

interface SuggestionSchool {
  type: string
  id: number
  name: string
  name_cn: string | null
  abbreviation: string | null
  address: string | null
  count: number
  query: { school_id: number }
}

interface SuggestionCity {
  type: string
  name: string
  country: string
  count: number
  query: { district: string; country: string }
}

interface SuggestionProperty {
  type: string
  id: number
  title: string
  district: string
  price_monthly: number | null
  query: { property_id: number }
}

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const cartStore = useCartStore()
const agentChatStore = useAgentChatStore()

const searchQuery = ref('')
const unreadCount = ref(0)

// ── 搜索建议状态 ─────────────────────────
const searchFocused = ref(false)
const showSuggestions = ref(false)
const suggestionsLoading = ref(false)
const matchingSchools = ref<SuggestionSchool[]>([])
const matchingCities = ref<SuggestionCity[]>([])
const matchingProperties = ref<SuggestionProperty[]>([])
let debounceTimer: ReturnType<typeof setTimeout> | null = null
let blurTimer: ReturnType<typeof setTimeout> | null = null
const hasAnySuggestions = computed(() =>
  matchingSchools.value.length > 0 ||
  matchingCities.value.length > 0 ||
  matchingProperties.value.length > 0
)

// ── 搜索建议请求 ─────────────────────────

async function fetchSuggestions(q: string) {
  suggestionsLoading.value = true
  try {
    const params: Record<string, string | number> = { limit: 6 }
    if (q.trim()) params.q = q.trim()
    const resp = await api.get('/search/suggestions', { params })
    const data = resp.data

    if (q.trim()) {
      matchingSchools.value = data.matching_schools || []
      matchingCities.value = data.matching_cities || []
      matchingProperties.value = data.matching_properties || []
    } else {
      matchingSchools.value = data.popular_schools || []
      matchingCities.value = (data.popular_cities || []).filter((c: any) => c.name)
      matchingProperties.value = []
    }
  } catch {
    matchingSchools.value = []
    matchingCities.value = []
    matchingProperties.value = []
  } finally {
    suggestionsLoading.value = false
  }
}

// ── 输入处理（防抖 300ms）─────────────────

function onSearchInput() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    fetchSuggestions(searchQuery.value)
  }, 300)
}

function onSearchFocus() {
  if (blurTimer) clearTimeout(blurTimer)
  searchFocused.value = true
  showSuggestions.value = true
  // 聚焦时立即拉取建议（展示热门或匹配结果）
  fetchSuggestions(searchQuery.value)
}

function onSearchBlur() {
  searchFocused.value = false
  // 延迟关闭，让 mousedown 有时间触发
  blurTimer = setTimeout(() => {
    showSuggestions.value = false
  }, 200)
}

// ── 热门大学（从 API 获取）─────

interface PopularUniversity {
  id: number
  name: string
  name_cn?: string | null
  abbreviation?: string | null
  city?: string | null
  country?: string | null
}

const popularUniversities = ref<PopularUniversity[]>([])

async function fetchPopularUniversities() {
  try {
    const resp = await api.get('/search/suggestions', { params: { limit: 10 } })
    popularUniversities.value = resp.data.popular_universities || []
  } catch { /* 静默失败 */ }
}

function popularUniDisplay(uni: PopularUniversity): string {
  if (uni.name_cn) return uni.abbreviation ? `${uni.name_cn} (${uni.abbreviation})` : uni.name_cn
  return uni.abbreviation || uni.name
}

function selectPopularUniversity(uni: PopularUniversity) {
  showSuggestions.value = false
  const name = uni.name_cn || uni.name
  router.push({ name: 'search', query: { uni_id: String(uni.id), radius: '5', uni_name: name } })
}

// Called on mount
fetchPopularUniversities()

/** 去掉 API 返回 district 中的 "国家-" 前缀，只保留城市名 */
function cityLabel(city: SuggestionCity): string {
  const name = city.name || ''
  const idx = name.indexOf('-')
  return idx > -1 ? name.slice(idx + 1) : name
}

// ── 选择处理 ─────────────────────────────

function selectSchool(school: SuggestionSchool) {
  showSuggestions.value = false
  searchQuery.value = school.name
  router.push({ name: 'search', query: { school_id: String(school.id) } })
}

function selectCity(city: SuggestionCity) {
  showSuggestions.value = false
  searchQuery.value = city.name
  router.push({ name: 'search', query: { district: city.name } })
}

function selectProperty(prop: SuggestionProperty) {
  showSuggestions.value = false
  router.push({ name: 'property-detail', params: { id: prop.id } })
}

// ── 搜索提交 ─────────────────────────────

function handleSearchSubmit() {
  showSuggestions.value = false
  if (searchQuery.value.trim()) {
    router.push({ name: 'search', query: { q: searchQuery.value.trim() } })
  }
}

// ── 通知 ─────────────────────────────────

async function fetchUnreadCount() {
  if (!authStore.isLoggedIn) return
  try {
    const resp = await notificationService.getUnreadCount()
    unreadCount.value = resp.count
  } catch {
    // ignore
  }
}

onMounted(() => {
  fetchUnreadCount()
  window.addEventListener('notifications:changed', fetchUnreadCount)
  if (authStore.isLoggedIn) cartStore.fetch()
})

onUnmounted(() => window.removeEventListener('notifications:changed', fetchUnreadCount))

// 每次路由变化刷新未读数（从通知页回来时数字更新）
watch(() => route.path, () => {
  fetchUnreadCount()
  // 路由变化时关闭建议
  showSuggestions.value = false
})

// 登录状态变化时同步候选清单与管家会话（登录后拉取、登出清空）
watch(
  () => authStore.isLoggedIn,
  (loggedIn) => {
    if (loggedIn) {
      cartStore.fetch()
    } else {
      cartStore.clear()
      agentChatStore.reset()
    }
  },
)
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── Header ───────────────────────── */

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--bg-white);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  height: 64px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: var(--shadow-sm);
}

.header-left .logo {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
}

.logo-icon {
  font-size: 26px;
}

.logo-text {
  font-size: 17px;
  font-weight: 700;
  color: var(--primary);
  letter-spacing: 0.5px;
}

.header-center {
  flex: 1;
  max-width: 640px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: center;
}

.cart-badge {
  flex-shrink: 0;
}

.cart-btn {
  width: 42px;
  height: 42px;
  font-size: 18px;
  color: var(--text-secondary, #606266);
  border-color: var(--border, #dcdfe6);
  transition: color 0.2s, border-color 0.2s;
}

.cart-btn:hover {
  color: var(--primary);
  border-color: var(--primary);
}

.header-search-area {
  position: static;
}

.header-search-wrapper {
  display: flex;
  align-items: center;
  border-radius: 36px;
  overflow: hidden;
  height: 48px;
  width: 100%;
  transition: box-shadow 0.2s;
}

.header-search-wrapper.focused {
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.15);
}

.search-input {
  flex: 1;
  border-radius: 36px 0 0 36px;
  overflow: hidden;
}

.search-input :deep(.el-input__wrapper) {
  border-radius: 36px 0 0 36px !important;
  background: var(--bg-white) !important;
  border: 2px solid var(--primary) !important;
  box-shadow: none !important;
  height: 48px;
  padding-left: 16px;
}

.search-input :deep(.el-input__inner) {
  color: var(--text-primary);
}

.search-input :deep(.el-input__prefix) {
  color: var(--text-muted);
}

.search-btn {
  height: 48px !important;
  border: 2px solid var(--primary) !important;
  border-radius: 0 36px 36px 0 !important;
  background: var(--primary) !important;
  color: #fff !important;
  font-size: 15px;
  font-weight: 600;
  margin-left: -2px;
  padding: 0 20px !important;
}

.search-btn:hover {
  background: var(--primary-light) !important;
}

/* ── 搜索建议下拉 ─────────────────────────── */

.search-suggestions {
  position: absolute;
  top: 58px;
  left: 50%;
  transform: translateX(-50%);
  width: 680px;
  max-width: 90vw;
  background: var(--bg-white);
  border: 1px solid var(--border-light, #ebeef5);
  border-radius: 16px;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.12);
  max-height: 480px;
  overflow-y: auto;
  z-index: 200;
  padding: 16px 20px;
}

.suggestions-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  color: var(--text-muted);
  font-size: 13px;
}

.suggestions-group {
  margin-bottom: 16px;
}

.suggestions-group:last-child {
  margin-bottom: 0;
}

.suggestions-group + .suggestions-group {
  border-top: 1px solid var(--border-light, #f0f0f0);
  padding-top: 16px;
}

.suggestions-group-title {
  padding: 0 0 12px 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
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
  padding: 6px 10px;
  background: var(--bg, #fafafa);
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.suggestion-card:hover {
  background: var(--primary-light, #ecf5ff);
  border-color: var(--primary);
}

.suggestion-card .card-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.suggestion-card .card-sub {
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.suggestions-empty {
  padding: 32px 16px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-dropdown {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 24px;
  transition: background 0.2s;
}

.user-dropdown:hover {
  background: var(--bg);
}

.username {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

/* ── Body ─────────────────────────── */

.layout-body {
  flex: 1;
}

/* ── Main ─────────────────────────── */

.layout-main {
  flex: 1;
  background: var(--bg);
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
}

.back-bar {
  margin-bottom: 12px;
}

.back-bar .el-button {
  font-size: 13px;
  color: var(--text-secondary, #606266);
}

.back-bar .el-button:hover {
  color: var(--primary);
}
</style>
