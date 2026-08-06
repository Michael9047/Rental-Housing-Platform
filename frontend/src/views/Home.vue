<template>
  <div class="home-page">
    <!-- Hero — 统一搜索框 -->
    <section class="hero">
      <HomeSearchBox />
    </section>

    <!-- 推荐房源 -->
    <section class="recommend-section">
      <div class="section-header">
        <h2 class="section-title">🏠 推荐房源</h2>
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

const loading = ref(true)
const rooms = ref<any[]>([])

async function loadRooms() {
  try {
    const res = await api.get('/buildings/public/search', { params: { limit: 18 } })
    const data = res.data
    rooms.value = Array.isArray(data) ? data : (data?.items || [])
  } catch (e: any) {
    console.error('[Home] load rooms failed:', e?.message || e)
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
