<template>
  <div class="admin-logs" v-loading="loading">
    <h2>审计日志</h2>

    <div class="filters">
      <el-select v-model="filterAction" placeholder="操作类型" clearable @change="fetchLogs">
        <el-option label="房源审核" value="property_moderate" />
        <el-option label="角色变更" value="user_role_change" />
        <el-option label="重建索引" value="embedding_reindex" />
      </el-select>
    </div>

    <el-table :data="logs" stripe style="width: 100%; margin-top: 16px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="action" label="操作" width="130">
        <template #default="{ row }">
          <el-tag size="small">{{ actionLabel(row.action) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="user_id" label="操作用户 ID" width="100" />
      <el-table-column prop="resource_type" label="资源类型" width="100" />
      <el-table-column prop="resource_id" label="资源 ID" width="80" />
      <el-table-column label="详情" min-width="160">
        <template #default="{ row }">
          <span class="details-text">{{ JSON.stringify(row.details) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="170">
        <template #default="{ row }">
          {{ new Date(row.created_at).toLocaleString('zh-CN') }}
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > pageSize"
      :page-size="pageSize"
      :total="total"
      layout="prev, pager, next"
      @current-change="handlePageChange"
      style="margin-top: 16px; justify-content: center"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminService } from '@/services/admin'
import type { AuditLog } from '@/types/admin'

const logs = ref<AuditLog[]>([])
const loading = ref(false)
const filterAction = ref('')
const page = ref(0)
const pageSize = 50
const total = ref(0)

const actionLabels: Record<string, string> = {
  property_moderate: '房源审核',
  user_role_change: '角色变更',
  embedding_reindex: '重建索引',
}

function actionLabel(action: string) {
  return actionLabels[action] || action
}

async function fetchLogs() {
  loading.value = true
  try {
    logs.value = await adminService.getLogs({
      skip: page.value * pageSize,
      limit: pageSize,
      action: filterAction.value || undefined,
    })
  } finally {
    loading.value = false
  }
}

function handlePageChange(p: number) {
  page.value = p - 1
  fetchLogs()
}

onMounted(fetchLogs)
</script>

<style scoped>
.admin-logs {
  max-width: 1100px;
  margin: 0 auto;
}

.admin-logs h2 {
  font-size: 22px;
  color: #303133;
  margin-bottom: 16px;
}

.filters {
  display: flex;
  gap: 12px;
}

.details-text {
  font-size: 12px;
  color: #909399;
}
</style>
