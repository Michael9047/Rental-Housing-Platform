<template>
  <div class="landlord-status" v-loading="loading">
    <h2>👷 房东维修工看板</h2>
    <p class="subtitle">展示各房东是否拥有自己的维修工</p>

    <el-table :data="statusList" stripe>
      <el-table-column label="房东" min-width="150"><template #default="{ row }">{{ row.landlord_name }}</template></el-table-column>
      <el-table-column label="是否有维修工" width="130">
        <template #default="{ row }">
          <el-tag :type="row.has_workers ? 'success' : 'danger'" size="small">
            {{ row.has_workers ? 'YES' : 'NO' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="工人总数" width="100"><template #default="{ row }">{{ row.worker_count }}</template></el-table-column>
      <el-table-column label="可调度" width="100">
        <template #default="{ row }">
          <span :style="{ color: row.available_count > 0 ? 'var(--success)' : 'var(--text-muted)' }">{{ row.available_count }}</span>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && statusList.length === 0" description="无数据" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/services/api'

interface LandlordStatus { landlord_id: number; landlord_name: string; has_workers: boolean; worker_count: number; available_count: number }
const statusList = ref<LandlordStatus[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try { statusList.value = (await api.get('/admin/landlord-workers-status')).data }
  catch { statusList.value = [] }
  finally { loading.value = false }
})
</script>

<style scoped>
.landlord-status { max-width: 800px; margin: 0 auto; }
.subtitle { color: var(--text-muted); font-size: 14px; margin-bottom: 16px; }
</style>
