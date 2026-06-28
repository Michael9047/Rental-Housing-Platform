<template>
  <div class="dashboard" v-loading="loading">
    <h2>管理后台</h2>

    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="用户总数" :value="stats.total_users" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="房源总数" :value="stats.total_properties" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="预约总数" :value="stats.total_bookings" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="待处理预约" :value="stats.pending_bookings">
            <template #suffix>
              <el-tag v-if="stats.pending_bookings > 0" type="warning" size="small">待处理</el-tag>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="stats.properties_by_district?.length" shadow="never" class="chart-card">
      <template #header>各区域房源分布</template>
      <div class="district-list">
        <div v-for="d in stats.properties_by_district" :key="d.district" class="district-item">
          <span class="district-name">{{ d.district }}</span>
          <el-progress :percentage="districtPercent(d.count)" :stroke-width="16" :text-inside="true" />
          <span class="district-count">{{ d.count }} 套</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminService } from '@/services/admin'
import type { AdminStats } from '@/types/admin'

const loading = ref(false)
const stats = ref<AdminStats>({
  total_users: 0,
  total_properties: 0,
  total_bookings: 0,
  pending_bookings: 0,
  properties_by_district: [],
})

function districtPercent(count: number) {
  const max = Math.max(...stats.value.properties_by_district.map((d) => d.count), 1)
  return Math.round((count / max) * 100)
}

async function fetchStats() {
  loading.value = true
  try {
    stats.value = await adminService.getStats()
  } finally {
    loading.value = false
  }
}

onMounted(fetchStats)
</script>

<style scoped>
.dashboard {
  max-width: 1100px;
  margin: 0 auto;
}

.dashboard h2 {
  font-size: 22px;
  color: #303133;
  margin-bottom: 24px;
}

.stats-row {
  margin-bottom: 24px;
}

.chart-card {
  margin-top: 24px;
}

.district-item {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.district-name {
  width: 80px;
  font-weight: 600;
  color: #303133;
}

.district-count {
  width: 60px;
  text-align: right;
  font-size: 14px;
  color: #909399;
}

:deep(.el-progress) {
  flex: 1;
}
</style>
