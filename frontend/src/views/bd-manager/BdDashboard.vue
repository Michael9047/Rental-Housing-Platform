<template>
  <div class="bd-dashboard">
    <h2>📊 商务拓展数据台</h2>
    <p class="subtitle">{{ authStore.user?.username }}，欢迎回来</p>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <span class="stat-icon">🏢</span>
        <div class="stat-info">
          <div class="stat-num">—</div>
          <div class="stat-label">合作机构</div>
        </div>
      </div>
      <div class="stat-card">
        <span class="stat-icon">🏠</span>
        <div class="stat-info">
          <div class="stat-num">—</div>
          <div class="stat-label">房源总数</div>
        </div>
      </div>
      <div class="stat-card">
        <span class="stat-icon">📋</span>
        <div class="stat-info">
          <div class="stat-num">—</div>
          <div class="stat-label">本月新增</div>
        </div>
      </div>
      <div class="stat-card">
        <span class="stat-icon">⏳</span>
        <div class="stat-info">
          <div class="stat-num">—</div>
          <div class="stat-label">申请中房源</div>
        </div>
      </div>
    </div>

    <el-card shadow="never" style="border-radius:var(--radius)">
      <template #header>📈 区域分布</template>
      <p style="color:var(--text-muted);text-align:center;padding:40px">
        数据对接开发中，敬请期待...
      </p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
const authStore = useAuthStore()
</script>

<style scoped>
.bd-dashboard { max-width: 1000px; margin: 0 auto; }
.subtitle { color: var(--text-muted); font-size: 14px; margin-bottom: 20px; }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-card { background: var(--bg-white); border-radius: var(--radius); border: 1px solid var(--border); padding: 18px; display: flex; align-items: center; gap: 14px; }
.stat-icon { font-size: 28px; }
.stat-num { font-size: 24px; font-weight: 700; color: var(--text-primary); }
.stat-label { font-size: 13px; color: var(--text-muted); }
</style>
