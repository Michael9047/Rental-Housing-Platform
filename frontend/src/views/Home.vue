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
          <template #prefix><span style="font-size:18px">🔍</span></template>
        </el-input>
        <el-button type="primary" size="large" @click="handleAiSearch" :loading="aiLoading" class="search-btn">
          <span v-if="!aiLoading">✨ AI 找房</span>
        </el-button>
      </div>
      <div class="hero-tags">
        <el-tag v-for="tag in quickTags" :key="tag" @click="searchQuery = tag; handleAiSearch()" class="quick-tag">
          {{ tag }}
        </el-tag>
      </div>
    </section>

    <!-- ═══════════ 推荐房源 ═══════════ -->
    <section class="recommend-section">
      <div class="section-header">
        <h2 class="section-title">{{ sectionTitle }}</h2>
        <el-link type="primary" :underline="false" @click="$router.push('/search')">
          查看更多 →
        </el-link>
      </div>

      <div v-if="loading" class="loading-grid">
        <div v-for="n in 3" :key="n" class="card-skeleton" />
      </div>

      <div class="card-grid" v-else-if="properties.length">
        <div
          v-for="b in properties"
          :key="b.id"
          class="card-wrapper"
          @click="goBuilding(b)"
        >
          <PropertyCard
            :property="cardProp(b)"
            :show-quick-book="false"
          />
        </div>
      </div>

      <el-empty v-else description="暂无推荐房源" :image-size="80">
        <el-button type="primary" @click="$router.push('/search')">去搜索页看看</el-button>
      </el-empty>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
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

// ═══════════ AI 搜索 ═══════════
async function handleAiSearch() {
  const q = searchQuery.value.trim()
  if (!q) return
  aiLoading.value = true
  try {
    await api.post('/ai-search/parse', { query: q })
    router.push({ path: '/ai-search', query: { q } })
  } catch {
    router.push({ path: '/search', query: { keyword: q } })
  } finally {
    aiLoading.value = false
  }
}

// ═══════════ 推荐加载 ═══════════
async function loadRecommendations() {
  loading.value = true
  try {
    const r = await api.get('/buildings/public', { params: { limit: 12 } })
    // API 直接返回 list[dict]
    const items = Array.isArray(r.data) ? r.data : []
    properties.value = items.map((b: any) => ({
      ...b,
      title: b.name_cn || b.name,
      price_monthly: null, // 公寓层面没有单个价格
      primary_image: b.primary_image,
    }))
    console.log('[Home] loaded', properties.value.length, 'buildings')
  } catch (e) {
    console.error('[Home] load failed', e)
    properties.value = []
  } finally {
    loading.value = false
  }
}

function cardProp(b: any) {
  return {
    id: b.id,
    title: b.name_cn || b.name,
    address: b.address,
    price_monthly: null,
    images: b.primary_image ? [{ filename: b.primary_image.filename, is_primary: true }] : [],
    amenities: b.amenities || [],
    female_only: b.female_only,
    couples_allowed: b.couples_allowed,
    unit_type_count: b.unit_type_count,
  }
}

function goBuilding(b: any) {
  router.push({ path: '/search', query: { keyword: b.name_cn || b.name } })
}
}

onMounted(() => loadRecommendations())
</script>

<style scoped>
.home-page { width: 100%; max-width: 1200px; margin: 0 auto; padding: 0 24px 60px }

/* ═══════════ Hero ═══════════ */
.hero {
  text-align: center;
  padding: 64px 0 48px;
  background: linear-gradient(135deg, #f0f5ff 0%, #fef7f0 50%, #f5f0ff 100%);
  border-radius: 24px;
  margin: 24px 0 48px;
}
.hero-title {
  font-size: 38px; font-weight: 800;
  background: linear-gradient(135deg, #e94560 0%, #6c5ce7 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 12px; letter-spacing: -0.5px;
}
.hero-subtitle { color: #6b7280; font-size: 17px; margin: 0 0 32px; }
.hero-search-bar { display: flex; gap: 10px; max-width: 640px; margin: 0 auto; }
.search-input { flex: 1 }
.search-input :deep(.el-input__wrapper) {
  border-radius: 14px; box-shadow: 0 2px 16px rgba(0,0,0,0.06);
  padding: 8px 18px; background: #fff; border: 2px solid transparent;
}
.search-input :deep(.el-input__wrapper:hover),
.search-input :deep(.el-input__wrapper.is-focus) {
  border-color: #6c5ce7; box-shadow: 0 4px 20px rgba(108,92,231,0.12);
}
.search-btn {
  border-radius: 14px; padding: 0 32px; font-weight: 600; font-size: 15px;
  background: linear-gradient(135deg, #6c5ce7, #e94560); border: none;
}
.search-btn:hover { opacity: 0.92 }
.hero-tags { display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 24px; flex-wrap: wrap }
.quick-tag { cursor: pointer; border-radius: 20px; padding: 4px 18px; font-size: 14px; font-weight: 500; border: 1px solid #e0e0f0; background: #fff; color: #6c5ce7 }
.quick-tag:hover { background: #6c5ce7; color: #fff; border-color: #6c5ce7 }

/* ═══════════ 推荐区块 ═══════════ */
.section-header { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 24px }
.section-title { font-size: 22px; font-weight: 700; color: #1a1a2e; margin: 0 }

/* ═══════════ 加载骨架 ═══════════ */
.loading-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px }
.card-skeleton { height: 360px; border-radius: 16px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite }
@keyframes shimmer { 0% { background-position: 200% 0 } 100% { background-position: -200% 0 } }

/* ═══════════ 卡片网格 ═══════════ */
.card-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px }
.card-wrapper { cursor: pointer }

@media (max-width: 1024px) { .card-grid { grid-template-columns: repeat(2, 1fr) } }
@media (max-width: 768px) {
  .home-page { padding: 0 12px 40px }
  .hero { padding: 40px 16px 32px; border-radius: 16px; margin: 12px 0 32px }
  .hero-title { font-size: 28px }
  .hero-subtitle { font-size: 15px }
  .hero-search-bar { flex-direction: column }
  .card-grid, .loading-grid { grid-template-columns: 1fr }
}
</style>
