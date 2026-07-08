<template>
  <div class="dashboard" v-loading="loading">
    <h2>🏢 运营工作台</h2>
    <p class="subtitle">欢迎回来，{{ authStore.user?.username }}</p>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <span class="stat-icon">🏠</span>
        <div class="stat-info">
          <div class="stat-num">{{ dashboard.properties.total }}</div>
          <div class="stat-label">管理房源</div>
          <div class="stat-detail">可用{{ dashboard.properties.available }} · 已租{{ dashboard.properties.rented }} · 维护{{ dashboard.properties.maintenance }}</div>
        </div>
      </div>
      <div class="stat-card" @click="$router.push('/bookings/landlord')">
        <span class="stat-icon">📅</span>
        <div class="stat-info">
          <div class="stat-num">{{ dashboard.bookings.pending }}</div>
          <div class="stat-label">待处理预约</div>
        </div>
      </div>
      <div class="stat-card" @click="$router.push('/workspace/repairs')">
        <span class="stat-icon">🔧</span>
        <div class="stat-info">
          <div class="stat-num">{{ dashboard.repairs.pending }}</div>
          <div class="stat-label">待处理报修</div>
          <div class="stat-detail">维修中 {{ dashboard.repairs.in_progress }}</div>
        </div>
      </div>
      <div class="stat-card" @click="$router.push('/workspace/workers')">
        <span class="stat-icon">👷</span>
        <div class="stat-info">
          <div class="stat-num">{{ dashboard.workers.total }}</div>
          <div class="stat-label">维修师傅</div>
          <div class="stat-detail">可用 {{ dashboard.workers.available }}</div>
        </div>
      </div>
    </div>

    <!-- 快捷入口 -->
    <el-card shadow="never" class="quick-card">
      <template #header>快捷操作</template>
      <div class="quick-actions">
        <el-button type="primary" @click="$router.push('/property/create')">➕ 发布房源</el-button>
        <el-button type="warning" @click="$router.push('/workspace/repairs')">🔧 报修管理</el-button>
        <el-button type="success" @click="$router.push('/workspace/workers')">👷 维修师傅管理</el-button>
        <el-button @click="$router.push('/bookings/landlord')">📅 预约管理</el-button>
        <el-button @click="$router.push('/property/manage')">🏠 房源管理</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { dashboardService } from '@/services/dashboard'

const authStore = useAuthStore()
const loading = ref(false)

const dashboard = reactive({
  properties: { total: 0, available: 0, rented: 0, maintenance: 0 },
  bookings: { pending: 0 },
  repairs: { pending: 0, in_progress: 0 },
  workers: { total: 0, available: 0 },
})

async function fetchData() {
  loading.value = true
  try {
    Object.assign(dashboard, await dashboardService.getLandlord())
  } catch { /* ignore */ }
  finally { loading.value = false }
}

onMounted(fetchData)
</script>

<style scoped>
.dashboard { max-width: 1000px; margin: 0 auto; }
.subtitle { color: var(--text-muted); font-size: 14px; margin-bottom: 20px; }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-card { background: var(--bg-white); border-radius: var(--radius); border: 1px solid var(--border); padding: 18px; display: flex; align-items: center; gap: 14px; cursor: pointer; transition: all 0.2s; }
.stat-card:hover { border-color: var(--primary); transform: translateY(-2px); box-shadow: var(--shadow); }
.stat-icon { font-size: 28px; }
.stat-num { font-size: 24px; font-weight: 700; color: var(--text-primary); }
.stat-label { font-size: 13px; color: var(--text-muted); }
.stat-detail { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.quick-card { border-radius: var(--radius); }
.quick-actions { display: flex; gap: 12px; flex-wrap: wrap; }
</style>
