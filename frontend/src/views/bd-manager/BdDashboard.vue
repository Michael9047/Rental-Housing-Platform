<template>
  <div class="bd-dashboard" v-loading="loading">
    <h2>📊 商务拓展数据台</h2>
    <p class="subtitle">{{ authStore.user?.username }}，欢迎回来</p>

    <div class="stats-grid">
      <div class="stat-card">
        <span class="stat-icon">🏢</span>
        <div class="stat-info">
          <div class="stat-num">{{ dashboard.institutes }}</div>
          <div class="stat-label">合作机构</div>
        </div>
      </div>
      <div class="stat-card">
        <span class="stat-icon">🏠</span>
        <div class="stat-info">
          <div class="stat-num">{{ dashboard.total_properties }}</div>
          <div class="stat-label">房源总数</div>
        </div>
      </div>
      <div class="stat-card">
        <span class="stat-icon">📅</span>
        <div class="stat-info">
          <div class="stat-num">{{ dashboard.pending_bookings }}</div>
          <div class="stat-label">待处理预约</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { dashboardService } from '@/services/dashboard'

const authStore = useAuthStore()
const loading = ref(false)
const dashboard = reactive({ institutes: 0, total_properties: 0, pending_bookings: 0 })

onMounted(async () => {
  loading.value = true
  try { Object.assign(dashboard, await dashboardService.getBd()) }
  catch { /* ignore */ }
  finally { loading.value = false }
})
</script>

<style scoped>
.bd-dashboard { max-width: 800px; margin: 0 auto; }
.subtitle { color: var(--text-muted); font-size: 14px; margin-bottom: 20px; }
.stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.stat-card { background: var(--bg-white); border-radius: var(--radius); border: 1px solid var(--border); padding: 18px; display: flex; align-items: center; gap: 14px; }
.stat-icon { font-size: 28px; }
.stat-num { font-size: 24px; font-weight: 700; color: var(--text-primary); }
.stat-label { font-size: 13px; color: var(--text-muted); }
</style>
