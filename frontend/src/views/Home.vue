<template>
  <div class="home-page">
    <!-- ═══════════ Hero — AI 搜索主入口 ═══════════ -->
    <section class="hero">
      <h1 class="hero-title">智能找房，一句话就够了</h1>
      <p class="hero-subtitle">告诉 AI 你的预算、位置和需求，秒级匹配最适合你的公寓</p>
      <div class="hero-search-bar">
        <el-input v-model="searchQuery" placeholder="试试：NUS附近两居室 预算3000..." size="large" clearable @keyup.enter="handleAiSearch" class="search-input">
          <template #prefix><span style="font-size:18px">🔍</span></template>
        </el-input>
        <el-button type="primary" size="large" @click="handleAiSearch" :loading="aiLoading" class="search-btn">
          <span v-if="!aiLoading">✨ AI 找房</span>
        </el-button>
      </div>
      <div class="hero-tags">
        <el-tag v-for="tag in quickTags" :key="tag" @click="searchQuery = tag; handleAiSearch()" class="quick-tag">{{ tag }}</el-tag>
      </div>
    </section>

    <!-- ═══════════ 推荐公寓 ═══════════ -->
    <section class="recommend-section">
      <div class="section-header">
        <h2 class="section-title">🏠 热门公寓推荐</h2>
        <el-link type="primary" :underline="false" @click="$router.push('/search')">查看更多 →</el-link>
      </div>

      <div v-if="loading" class="loading-grid">
        <div v-for="n in 3" :key="n" class="card-skeleton" />
      </div>

      <div class="card-grid" v-else-if="buildings.length">
        <div v-for="b in buildings" :key="b.id" class="building-card" @click="goBuilding(b)">
          <div class="card-cover">
            <img v-if="b.primary_image" :src="'/api/v1/uploads/' + b.primary_image.filename" alt="" />
            <div v-else class="card-cover-placeholder">🏢</div>
            <div class="card-type-count" v-if="b.unit_type_count">📐 {{ b.unit_type_count }} 种户型</div>
          </div>
          <div class="card-body">
            <h3 class="card-name">{{ b.name_cn || b.name }}</h3>
            <p class="card-addr" v-if="b.address">📍 {{ b.address.slice(0, 60) }}{{ b.address.length > 60 ? '...' : '' }}</p>
            <div class="card-tags" v-if="b.amenities?.length">
              <span v-for="a in b.amenities.slice(0, 4)" :key="a" class="card-tag">{{ a }}</span>
            </div>
            <div class="card-special">
              <span v-if="b.female_only" class="badge badge-girls">👩 女生独栋</span>
              <span v-if="b.couples_allowed" class="badge badge-couples">💑 支持情侣</span>
            </div>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无公寓数据" :image-size="80" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'

const router = useRouter()
const searchQuery = ref('')
const aiLoading = ref(false)
const loading = ref(false)
const buildings = ref<any[]>([])
const quickTags = ['金文泰', 'NUS附近', '伦敦学生公寓']

async function handleAiSearch() {
  const q = searchQuery.value.trim()
  if (!q) return
  aiLoading.value = true
  try {
    await api.post('/ai-search/parse', { query: q })
    router.push({ path: '/ai-search', query: { q } })
  } catch {
    router.push({ path: '/search', query: { keyword: q } })
  } finally { aiLoading.value = false }
}

async function loadRecommendations() {
  loading.value = true
  try {
    // 用 /properties 按 institute 去重聚合（/public/buildings 需后端重启）
    const r = await api.get('/properties', { params: { page_size: 200 } })
    const items = r?.data?.items || r?.data || []
    const rooms = Array.isArray(items) ? items : []
    // 按 institute_id 分组去重，取每个公寓的第一个 room 作为代表
    const seen = new Map()
    rooms.forEach((p: any) => {
      const iid = p.institute_id || p.id
      if (!seen.has(iid)) {
        seen.set(iid, {
          id: iid,
          name: p.institute_name || p.title || p.address,
          address: p.address,
          amenities: p.amenities || [],
          female_only: p.female_only || false,
          couples_allowed: p.couples_allowed || false,
          unit_type_count: 1,
          primary_image: p.images?.[0] ? { filename: p.images[0].filename } : null,
        })
      } else {
        const b = seen.get(iid)
        b.unit_type_count++
      }
    })
    buildings.value = Array.from(seen.values())
  } catch (e) {
    console.error('[Home] load failed', e)
  } finally { loading.value = false }
}

function goBuilding(b: any) {
  router.push({ path: '/search', query: { keyword: b.name_cn || b.name } })
}

onMounted(() => loadRecommendations())
</script>

<style scoped>
.home-page { width: 100%; max-width: 1200px; margin: 0 auto; padding: 0 24px 60px }

.hero { text-align: center; padding: 64px 0 48px; background: linear-gradient(135deg, #f0f5ff 0%, #fef7f0 50%, #f5f0ff 100%); border-radius: 24px; margin: 24px 0 48px }
.hero-title { font-size: 38px; font-weight: 800; background: linear-gradient(135deg, #e94560 0%, #6c5ce7 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin: 0 0 12px }
.hero-subtitle { color: #6b7280; font-size: 17px; margin: 0 0 32px }
.hero-search-bar { display: flex; gap: 10px; max-width: 640px; margin: 0 auto }
.search-input { flex: 1 }
.search-input :deep(.el-input__wrapper) { border-radius: 14px; box-shadow: 0 2px 16px rgba(0,0,0,0.06); padding: 8px 18px; background: #fff; border: 2px solid transparent }
.search-input :deep(.el-input__wrapper:hover), .search-input :deep(.el-input__wrapper.is-focus) { border-color: #6c5ce7; box-shadow: 0 4px 20px rgba(108,92,231,0.12) }
.search-btn { border-radius: 14px; padding: 0 32px; font-weight: 600; font-size: 15px; background: linear-gradient(135deg, #6c5ce7, #e94560); border: none }
.search-btn:hover { opacity: 0.92 }
.hero-tags { display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 24px; flex-wrap: wrap }
.quick-tag { cursor: pointer; border-radius: 20px; padding: 4px 18px; font-size: 14px; font-weight: 500; border: 1px solid #e0e0f0; background: #fff; color: #6c5ce7; transition: all 0.2s }
.quick-tag:hover { background: #6c5ce7; color: #fff; border-color: #6c5ce7 }

.section-header { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 24px }
.section-title { font-size: 22px; font-weight: 700; color: #1a1a2e; margin: 0 }

.loading-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px }
.card-skeleton { height: 340px; border-radius: 16px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite }
@keyframes shimmer { 0% { background-position: 200% 0 } 100% { background-position: -200% 0 } }

.card-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px }

.building-card { border-radius: 16px; overflow: hidden; background: #fff; border: 1px solid #ebeef5; cursor: pointer; transition: all 0.25s ease }
.building-card:hover { transform: translateY(-4px); box-shadow: 0 8px 30px rgba(0,0,0,0.1); border-color: #6c5ce7 }

.card-cover { height: 200px; background: #f0f2f5; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center }
.card-cover img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.4s ease }
.building-card:hover .card-cover img { transform: scale(1.05) }
.card-cover-placeholder { font-size: 56px; opacity: 0.2 }
.card-type-count { position: absolute; bottom: 10px; right: 10px; background: rgba(0,0,0,0.65); backdrop-filter: blur(6px); color: #fff; padding: 4px 12px; border-radius: 8px; font-size: 13px; font-weight: 600 }

.card-body { padding: 16px 18px 20px }
.card-name { font-size: 17px; font-weight: 700; color: #1a1a2e; margin: 0 0 6px }
.card-addr { font-size: 13px; color: #909399; margin: 0 0 10px }
.card-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px }
.card-tag { font-size: 12px; padding: 2px 10px; background: #f5f7fa; border: 1px solid #e9ecf1; border-radius: 6px; color: #606266 }
.card-special { display: flex; gap: 8px }
.badge { font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 8px }
.badge-girls { background: #fef0f0; color: #e0485c; border: 1px solid #fcd4da }
.badge-couples { background: #f4f0fe; color: #7c3aed; border: 1px solid #e0d4fc }

@media (max-width: 1024px) { .card-grid, .loading-grid { grid-template-columns: repeat(2, 1fr) } }
@media (max-width: 768px) {
  .home-page { padding: 0 12px 40px }
  .hero { padding: 40px 16px 32px; border-radius: 16px; margin: 12px 0 32px }
  .hero-title { font-size: 28px }
  .hero-subtitle { font-size: 15px }
  .hero-search-bar { flex-direction: column }
  .card-grid, .loading-grid { grid-template-columns: 1fr }
}
</style>
