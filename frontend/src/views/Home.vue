<template>
  <div class="home-page">
    <!-- Hero — 统一搜索框 -->
    <section class="hero">
      <HomeSearchBox />
    </section>

    <!-- 推荐房源 -->
    <section class="recommend-section">
      <div class="section-header">
        <div>
          <h2 class="section-title">🏠 推荐房源</h2>
          <p v-if="recommendationHint" class="recommendation-hint">{{ recommendationHint }}</p>
        </div>
        <el-link type="primary" :underline="false" @click="$router.push('/search')">查看更多 →</el-link>
      </div>

      <div v-if="loading" class="loading-grid">
        <div v-for="n in 6" :key="n" class="card-skeleton" />
      </div>

      <div class="card-grid" v-else>
        <PropertyCard
          v-for="room in rooms"
          :key="room.id"
          :property="room"
          entity="building"
          :show-quick-book="false"
        />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/services/api'
import PropertyCard from '@/components/PropertyCard.vue'
import HomeSearchBox from '@/components/HomeSearchBox.vue'
import { createLogger } from '@/utils/logger'
import { buildRecommendationQueries, loadRecentHousingSearch } from '@/utils/recentHousingSearch'

const log = createLogger('Home')

const loading = ref(true)
const rooms = ref<any[]>([])
const recommendationHint = ref('')

function appendUniqueRooms(target: any[], incoming: any[], limit: number): void {
  const knownIds = new Set(target.map((room) => room.id ?? room.institute_id))
  for (const room of incoming) {
    const id = room.id ?? room.institute_id
    if (id == null || knownIds.has(id)) continue
    target.push(room)
    knownIds.add(id)
    if (target.length >= limit) break
  }
}

async function loadRooms() {
  const limit = 18
  const context = loadRecentHousingSearch()
  if (context?.kind === 'school' && context.schoolName) {
    recommendationHint.value = `优先展示 ${context.schoolName} 附近房源，不足时补充 ${context.city || '同城'}房源`
  } else if (context?.kind === 'district' && context.district) {
    recommendationHint.value = `优先展示 ${context.district} 房源${context.city ? `，不足时补充 ${context.city}` : ''}`
  } else if (context?.city) {
    recommendationHint.value = `根据你最近浏览的 ${context.city} 推荐`
  }

  try {
    const recommended: any[] = []
    for (const params of buildRecommendationQueries(context, limit)) {
      if (recommended.length >= limit) break
      try {
        const res = await api.get('/buildings/public/search', { params })
        const data = res.data
        appendUniqueRooms(recommended, Array.isArray(data) ? data : (data?.items || []), limit)
      } catch (error: any) {
        log.warn('推荐房源降级查询失败', {
          params,
          error: error instanceof Error ? error.message : String(error),
        })
      }
    }
    rooms.value = recommended
  } catch (e: any) {
    log.error('加载推荐房源失败', { limit }, e)
  } finally {
    loading.value = false
  }
}

onMounted(() => loadRooms())
</script>

<style scoped>
.home-page { width: 100%; max-width: 1200px; margin: 0 auto; padding: 0 24px 60px }

.hero { text-align: center; padding: 64px 0 48px; background: linear-gradient(135deg, #f0f5ff 0%, #fef7f0 50%, #f5f0ff 100%); border-radius: 24px; margin: 24px 0 48px }

.section-header { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 24px }
.section-title { font-size: 22px; font-weight: 700; color: #1a1a2e; margin: 0 }
.recommendation-hint { margin: 5px 0 0; color: #6b7280; font-size: 13px }

.loading-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px }
.card-skeleton { height: 340px; border-radius: 16px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite }
@keyframes shimmer { 0% { background-position: 200% 0 } 100% { background-position: -200% 0 } }

.card-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px }

@media (max-width: 1024px) { .card-grid, .loading-grid { grid-template-columns: repeat(2, 1fr) } }
@media (max-width: 768px) {
  .home-page { padding: 0 12px 40px }
  .hero { padding: 40px 16px 32px; border-radius: 16px; margin: 12px 0 32px }
  .card-grid, .loading-grid { grid-template-columns: 1fr }
}
</style>
