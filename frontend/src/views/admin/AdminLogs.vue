<template>
  <div class="admin-logs" v-loading="loading">
    <h2>审计日志</h2>

    <div class="filters">
      <div class="filter-row">
        <el-select v-model="filterAction" placeholder="操作类型" clearable @change="fetchLogs">
          <el-option label="户型信息审核" value="unit_type_review" />
          <el-option label="角色变更" value="user_role_change" />
        </el-select>
        <el-input-number
          v-model="filterUserId"
          placeholder="用户 ID"
          :min="1"
          controls-position="right"
          class="filter-number"
          @change="fetchLogs"
        />
        <el-input-number
          v-model="filterResourceId"
          placeholder="表内 ID"
          :min="1"
          controls-position="right"
          class="filter-number"
          @change="fetchLogs"
        />
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          class="date-input"
          @change="fetchLogs"
        />
        <el-button type="primary" @click="fetchLogs">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </div>

    <div class="table-wrap">
      <el-table :data="logs" stripe class="data-table">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="action" label="操作" width="130">
          <template #default="{ row }">
            <el-tag size="small">{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="user_id" label="操作用户 ID" width="110" />
        <el-table-column prop="resource_type" label="数据表" width="140">
          <template #default="{ row }">{{ resourceTypeLabel(row.resource_type) }}</template>
        </el-table-column>
        <el-table-column prop="resource_id" label="表内 ID" width="90" />
        <el-table-column label="详情" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="details-text">{{ detailsText(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString('zh-CN') }}
          </template>
        </el-table-column>
      </el-table>
    </div>

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
const filterUserId = ref<number | undefined>()
const filterResourceId = ref<number | undefined>()
const dateRange = ref<[Date, Date] | null>(null)
const page = ref(0)
const pageSize = 50
const total = ref(0)

const actionLabels: Record<string, string> = {
  unit_type_review: '户型信息审核',
  unit_type_status_change: '户型状态变更',
  property_moderate: '旧房源审核',
  user_role_change: '角色变更',
  user_login: '登录',
  resolve_system_alert: '异常处理',
}

function actionLabel(action: string) {
  return actionLabels[action] || action
}

function resourceTypeLabel(type: string | null) {
  const labels: Record<string, string> = {
    unit_type: 'unit_types / 户型',
    institute: 'institutes / 公寓',
    property: 'properties / 旧房源',
    user: 'users / 用户',
  }
  return type ? labels[type] || type : '-'
}

function statusLabel(status: string | null | undefined) {
  const labels: Record<string, string> = {
    available: '可租',
    rented: '已租',
    maintenance: '维修中',
    offline: '下架',
    pending_review: '待审核',
  }
  return status ? labels[status] || status : '-'
}

function reviewResultLabel(result: string | null | undefined) {
  const labels: Record<string, string> = {
    normal: '正常',
    abnormal: '异常',
  }
  return result ? labels[result] || result : '-'
}

function detailsOf(row: AuditLog): Record<string, any> {
  if (!row.details) return {}
  if (typeof row.details === 'string') {
    try {
      return JSON.parse(row.details)
    } catch {
      return { content: row.details }
    }
  }
  return row.details as Record<string, any>
}

function detailsText(row: AuditLog) {
  const details = detailsOf(row)
  if (row.action === 'unit_type_review') {
    return [
      `户型：${details.unit_type_name || `#${row.resource_id || '-'}`}`,
      `公寓：${details.institute_name || '-'}`,
      `结果：${reviewResultLabel(details.result)}`,
      `备注：${details.note || '-'}`,
    ].join('；')
  }
  if (row.action === 'unit_type_status_change') {
    return [
      `户型：${details.unit_type_name || `#${row.resource_id || '-'}`}`,
      `公寓：${details.institute_name || '-'}`,
      `状态：${statusLabel(details.new_status)}`,
    ].join('；')
  }
  if (row.action === 'user_role_change') {
    return `用户：${row.resource_id || '-'}；角色：${details.old_role || '-'} -> ${details.new_role || '-'}`
  }
  if (row.action === 'resolve_system_alert') {
    return `异常：${row.resource_id || '-'}；处理：${details.action_label || details.action_type || '-'}`
  }
  return details.content || Object.entries(details).map(([key, value]) => `${key}: ${value}`).join('；') || '-'
}

async function fetchLogs() {
  loading.value = true
  try {
    const params: Parameters<typeof adminService.getLogs>[0] = {
      skip: page.value * pageSize,
      limit: pageSize,
    }
    if (filterAction.value) params.action = filterAction.value
    if (typeof filterUserId.value === 'number') params.user_id = filterUserId.value
    if (typeof filterResourceId.value === 'number') params.resource_id = filterResourceId.value
    if (dateRange.value?.[0]) params.start_at = dateRange.value[0].toISOString()
    if (dateRange.value?.[1]) {
      const end = new Date(dateRange.value[1])
      end.setHours(23, 59, 59, 999)
      params.end_at = end.toISOString()
    }

    logs.value = await adminService.getLogs(params)
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filterAction.value = ''
  filterUserId.value = undefined
  filterResourceId.value = undefined
  dateRange.value = null
  page.value = 0
  fetchLogs()
}

function handlePageChange(p: number) {
  page.value = p - 1
  fetchLogs()
}

onMounted(fetchLogs)
</script>

<style scoped>
.admin-logs {
  box-sizing: border-box;
  width: 100%;
}

.admin-logs h2 {
  font-size: 22px;
  color: #303133;
  margin-bottom: 16px;
}

.filters {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.filter-row {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.filter-number {
  width: 160px;
}

.date-input {
  max-width: 260px;
}

.table-wrap {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  box-sizing: border-box;
  margin-top: 16px;
  overflow-x: auto;
  width: 100%;
}

.data-table {
  min-width: 900px;
  width: 100%;
}

.details-text {
  font-size: 12px;
  color: #909399;
  overflow-wrap: anywhere;
}
</style>
