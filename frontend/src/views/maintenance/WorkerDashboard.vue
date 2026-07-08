<template>
  <div class="worker-dashboard" v-loading="loading">
    <h2>🔧 工单中心</h2>
    <p class="subtitle">{{ authStore.user?.username }}，欢迎回来</p>

    <!-- 状态标签 -->
    <div style="margin-bottom:20px">
      <el-tag :type="STATUS_TAG[dashboard.worker_status]" size="large" effect="dark">
        {{ STATUS_LABEL[dashboard.worker_status] || dashboard.worker_status }}
      </el-tag>
      <span style="margin-left:8px;color:var(--text-muted)">评分：⭐ {{ dashboard.worker_rating.toFixed(1) }}</span>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card" @click="$router.push('/worker/orders')">
        <span class="stat-icon">📋</span>
        <div class="stat-info">
          <div class="stat-num">{{ dashboard.today_orders }}</div>
          <div class="stat-label">待处理工单</div>
        </div>
      </div>
      <div class="stat-card">
        <span class="stat-icon">✅</span>
        <div class="stat-info">
          <div class="stat-num">{{ dashboard.completed }}</div>
          <div class="stat-label">已完成</div>
        </div>
      </div>
      <div class="stat-card">
        <span class="stat-icon">📊</span>
        <div class="stat-info">
          <div class="stat-num">{{ dashboard.total_orders }}</div>
          <div class="stat-label">全部工单</div>
        </div>
      </div>
    </div>

    <el-button type="primary" size="large" @click="$router.push('/worker/orders')">进入工单列表 →</el-button>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { dashboardService } from '@/services/dashboard'

const authStore = useAuthStore()
const loading = ref(false)
const dashboard = reactive({ today_orders: 0, completed: 0, total_orders: 0, worker_status: 'available', worker_rating: 5.0 })

const STATUS_LABEL: Record<string, string> = { available: '可调度', working: '工作中', on_leave: '休假中' }
const STATUS_TAG: Record<string, string> = { available: 'success', working: 'danger', on_leave: 'warning' }

async function fetchData() {
  loading.value = true
  try { Object.assign(dashboard, await dashboardService.getMaintenance()) }
  catch { /* ignore */ }
  finally { loading.value = false }
}

onMounted(fetchData)
</script>

<style scoped>
.worker-dashboard { max-width: 800px; margin: 0 auto; }
.subtitle { color: var(--text-muted); font-size: 14px; margin-bottom: 20px; }
.stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-card { background: var(--bg-white); border-radius: var(--radius); border: 1px solid var(--border); padding: 18px; display: flex; align-items: center; gap: 12px; cursor: pointer; transition: all 0.2s; }
.stat-card:hover { border-color: var(--primary); transform: translateY(-2px); }
.stat-icon { font-size: 24px; }
.stat-num { font-size: 22px; font-weight: 700; color: var(--text-primary); }
.stat-label { font-size: 13px; color: var(--text-muted); }
</style>
