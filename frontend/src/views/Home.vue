<template>
  <div class="home-page">
    <!-- ═══════════ Hero — AI 搜索主入口 ═══════════ -->
    <section class="hero">
      <h1 class="hero-title">智能找房，一句话就够了</h1>
      <p class="hero-subtitle">告诉 AI 你的预算、位置和需求，秒级匹配最适合你的公寓</p>
      <div class="hero-search-bar">
        <el-input
          v-model="searchQuery"
          placeholder="试试：NUS附近两居室 预算3000..."
          size="large"
          clearable
          @keyup.enter="handleAiSearch"
          class="search-input"
        >
          <template #prefix>
            <el-icon :size="20"><Search /></el-icon>
          </template>
        </el-input>
        <el-button
          type="primary"
          size="large"
          @click="handleAiSearch"
          :loading="aiLoading"
          class="search-btn"
        >
          <span v-if="!aiLoading">✨ AI 找房</span>
        </el-button>
      </div>
      <div class="hero-tags">
        <span class="tag-label">快速搜索：</span>
        <el-tag
          v-for="tag in quickTags"
          :key="tag"
          @click="searchQuery = tag; handleAiSearch()"
          class="quick-tag"
        >
          {{ tag }}
        </el-tag>
      </div>
    </section>

    <!-- ═══════════ 推荐房源 ═══════════ -->
    <section class="recommend-section" v-loading="loading">
      <div class="section-header">
        <h2 class="section-title">{{ sectionTitle }}</h2>
        <el-link type="primary" :underline="false" @click="$router.push('/search')">
          查看更多 <el-icon><ArrowRight /></el-icon>
        </el-link>
      </div>

      <div class="card-grid" v-if="properties.length">
        <PropertyCard
          v-for="p in properties"
          :key="p.id"
          :property="p"
          :show-quick-book="authStore.isLoggedIn"
          @click.native="goDetail(p.id)"
        />
      </div>
      <el-empty v-else description="暂无推荐房源" :image-size="80">
        <el-button type="primary" @click="$router.push('/search')">去搜索页看看</el-button>
      </el-empty>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search, ArrowRight } from '@element-plus/icons-vue'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import PropertyCard from '@/components/PropertyCard.vue'

const router = useRouter()
const authStore = useAuthStore()

const searchQuery = ref('')
const aiLoading = ref(false)
const loading = ref(false)
const properties = ref<any[]>([])
const sectionTitle = ref('🏠 热门房源推荐')

const quickTags = ['金文泰', 'NUS附近', '伦敦学生公寓']

// ═══════════ 搜索历史（localStorage） ═══════════
interface SearchRecord {
  id: string; query: string; type: 'ai' | 'regex'
  district?: string; price_min?: number; price_max?: number
  timestamp: number
}

function loadHistory(): SearchRecord[] {
  try {
    return JSON.parse(localStorage.getItem('searchHistory') || '[]')
  } catch { return [] }
}

function saveHistory(records: SearchRecord[]) {
  localStorage.setItem('searchHistory', JSON.stringify(records.slice(0, 20)))
}

function addHistory(query: string, type: 'ai' | 'regex', filters?: Record<string, any>) {
  const records = loadHistory()
  records.unshift({
    id: Date.now().toString(36),
    query, type,
    district: filters?.district,
    price_min: filters?.price_min,
    price_max: filters?.price_max,
    timestamp: Date.now(),
  })
  saveHistory(records)
}

function getPreferenceFilters(): Record<string, any> | null {
  const records = loadHistory()
  if (!records.length) return null
  // 取最近 5 条的偏好
  const recent = records.slice(0, 5)
  const districts = recent.filter(r => r.district).map(r => r.district)
  const priceRange = recent.filter(r => r.price_min || r.price_max)
  if (districts.length >= 2) {
    return { district: districts[0] }
  }
  if (priceRange.length >= 2) {
    const avgMin = priceRange.reduce((s, r) => s + (r.price_min || 0), 0) / priceRange.length
    const avgMax = priceRange.reduce((s, r) => s + (r.price_max || 0), 0) / priceRange.length
    if (avgMin > 0) return { price_min: Math.round(avgMin), price_max: Math.round(avgMax) }
  }
  return null
}

// ═══════════ AI 搜索 ═══════════
async function handleAiSearch() {
  const q = searchQuery.value.trim()
  if (!q) return

  aiLoading.value = true
  try {
    // 调用 AI 解析
    const r = await api.post('/ai-search/parse', { query: q })
    const { parsed_params, completeness } = r.data

    // 记录搜索历史
    addHistory(q, 'ai', parsed_params)

    if (completeness?.is_complete) {
      // 直接跳 AI 搜索结果
      router.push({ path: '/ai-search', query: { q } })
    } else {
      // 跳 AI 搜索页补全
      router.push({ path: '/ai-search', query: { q, incomplete: '1' } })
    }
  } catch {
    // AI 解析失败，fallback 到传统搜索
    addHistory(q, 'regex')
    router.push({ path: '/search', query: { keyword: q } })
  } finally {
    aiLoading.value = false
  }
}

// ═══════════ 推荐加载 ═══════════
async function loadRecommendations() {
  loading.value = true
  try {
    const prefs = getPreferenceFilters()
    const params: any = { page_size: 12 }

    if (prefs) {
      if (prefs.district) {
        params.district = prefs.district
        sectionTitle.value = `📍 根据你的偏好 — ${prefs.district}`
      }
      if (prefs.price_min) params.price_min = prefs.price_min
      if (prefs.price_max) params.price_max = prefs.price_max
      if (prefs.price_min && prefs.price_max) {
        sectionTitle.value = `💰 根据你的预算 — ¥${prefs.price_min}-${prefs.price_max}`
      }
    } else {
      // 默认推荐：按评分排序
      params.sort_by = 'rating'
      params.sort_order = 'desc'
    }

    const r = await api.get('/properties', { params })
    properties.value = (r.data.items || []).map((p: any) => ({
      ...p,
      // 兼容字段
      title: p.title || p.name || p.address,
      price_monthly: p.price_monthly || p.base_rent,
    }))
  } catch { /* */ }
  finally { loading.value = false }
}

function goDetail(id: number) {
  router.push(`/room/${id}`)
}

onMounted(() => loadRecommendations())
</script>

<style scoped>
.home-page { max-width: 1200px; margin: 0 auto; padding: 0 24px 60px }

/* ═══════════ Hero ═══════════ */
.hero {
  text-align: center;
  padding: 64px 0 48px;
  background: linear-gradient(135deg, #f0f5ff 0%, #fef7f0 50%, #f5f0ff 100%);
  border-radius: 24px;
  margin: 24px 0 48px;
}

.hero-title {
  font-size: 38px;
  font-weight: 800;
  background: linear-gradient(135deg, #e94560 0%, #6c5ce7 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 12px;
  letter-spacing: -0.5px;
}

.hero-subtitle {
  color: #6b7280;
  font-size: 17px;
  margin: 0 0 32px;
  line-height: 1.5;
}

.hero-search-bar {
  display: flex;
  gap: 10px;
  max-width: 640px;
  margin: 0 auto;
}

.search-input { flex: 1 }
.search-input :deep(.el-input__wrapper) {
  border-radius: 14px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.06);
  padding: 8px 18px;
  background: #fff;
  border: 2px solid transparent;
  transition: border-color 0.2s;
}
.search-input :deep(.el-input__wrapper:hover),
.search-input :deep(.el-input__wrapper.is-focus) {
  border-color: #6c5ce7;
  box-shadow: 0 4px 20px rgba(108,92,231,0.12);
}

.search-btn {
  border-radius: 14px;
  padding: 0 32px;
  font-weight: 600;
  font-size: 15px;
  background: linear-gradient(135deg, #6c5ce7, #e94560);
  border: none;
}
.search-btn:hover {
  opacity: 0.92;
}

.hero-tags {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: 24px;
  flex-wrap: wrap;
}

.tag-label {
  font-size: 14px;
  color: #909399;
}

.quick-tag {
  cursor: pointer;
  border-radius: 20px;
  padding: 4px 18px;
  font-size: 14px;
  font-weight: 500;
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

/* ═══════════ 推荐区块 ═══════════ */
.section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 24px;
}

.section-title {
  font-size: 22px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0;
}

/* ═══════════ 卡片网格 ═══════════ */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

@media (max-width: 768px) {
  .home-page { padding: 0 12px 40px }
  .hero {
    padding: 40px 16px 32px;
    border-radius: 16px;
    margin: 12px 0 32px;
  }
  .hero-title { font-size: 28px }
  .hero-subtitle { font-size: 15px }
  .hero-search-bar { flex-direction: column }
  .card-grid { grid-template-columns: 1fr }
}
</style>
