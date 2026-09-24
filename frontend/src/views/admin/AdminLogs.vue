<template>
  <div class="admin-logs" v-loading="loading">
    <div class="page-head">
      <div>
        <h2>审计日志</h2>
        <p>按日期归档，再按操作类型细分，所有记录只读留痕。</p>
      </div>
      <el-tag type="info">{{ logs.length }} 条</el-tag>
    </div>

    <div class="filters">
      <el-select v-model="filterAction" placeholder="操作类型" clearable @change="fetchLogs">
        <el-option
          v-for="item in actionOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
    </div>

    <div v-if="groupedLogs.length" class="log-timeline">
      <section v-for="dateGroup in groupedLogs" :key="dateGroup.date" class="date-group">
        <div class="date-head">
          <strong>{{ dateGroup.date }}</strong>
          <span>{{ dateGroup.total }} 条记录</span>
        </div>

        <div class="type-groups">
          <article v-for="typeGroup in dateGroup.types" :key="typeGroup.action" class="type-group">
            <div class="type-head">
              <el-tag size="small">{{ actionLabel(typeGroup.action) }}</el-tag>
              <span>{{ typeGroup.items.length }} 条</span>
            </div>

            <div class="log-list">
              <div v-for="log in typeGroup.items" :key="log.id" class="log-row">
                <div class="log-time">{{ formatTime(log.created_at) }}</div>
                <div class="log-main">
                  <div class="log-title">
                    <span>用户 {{ log.user_id || '系统' }}</span>
                    <small>{{ resourceLabel(log) }}</small>
                  </div>
                  <div class="details-text">{{ formatDetails(log.details) }}</div>
                </div>
                <div class="log-ip">{{ log.ip_address || '-' }}</div>
              </div>
            </div>
          </article>
        </div>
      </section>
    </div>

    <el-empty v-else description="暂无审计记录" />

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
import { computed, onMounted, ref } from 'vue'
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
  property_info_audit: '房源信息复核',
  user_role_change: '角色变更',
  embedding_reindex: '重建索引',
  login: '登录',
  register: '注册',
}

const actionOptions = computed(() => {
  const actions = new Set([...Object.keys(actionLabels), ...logs.value.map((item) => item.action)])
  return Array.from(actions).map((value) => ({ label: actionLabel(value), value }))
})

const groupedLogs = computed(() => {
  const dateMap = new Map<string, Map<string, AuditLog[]>>()
  logs.value.forEach((log) => {
    const date = formatDate(log.created_at)
    if (!dateMap.has(date)) dateMap.set(date, new Map())
    const typeMap = dateMap.get(date)!
    if (!typeMap.has(log.action)) typeMap.set(log.action, [])
    typeMap.get(log.action)!.push(log)
  })

  return Array.from(dateMap.entries()).map(([date, typeMap]) => {
    const types = Array.from(typeMap.entries()).map(([action, items]) => ({
      action,
      items: [...items].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    }))
    const total = types.reduce((sum, item) => sum + item.items.length, 0)
    return { date, total, types }
  })
})

function actionLabel(action: string) {
  return actionLabels[action] || action
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
  })
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function resourceLabel(log: AuditLog) {
  const type = log.resource_type || '未指定对象'
  return log.resource_id ? `${type} #${log.resource_id}` : type
}

function formatDetails(details: Record<string, unknown> | null) {
  if (!details || !Object.keys(details).length) return '无详情'
  return Object.entries(details)
    .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
    .join('；')
}

async function fetchLogs() {
  loading.value = true
  try {
    logs.value = await adminService.getLogs({
      skip: page.value * pageSize,
      limit: pageSize,
      action: filterAction.value || undefined,
    })
    total.value = logs.value.length < pageSize && page.value === 0
      ? logs.value.length
      : Math.max(total.value, page.value * pageSize + logs.value.length)
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
  max-width: 1120px;
  margin: 0 auto;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}

.admin-logs h2 {
  font-size: 22px;
  color: #303133;
  margin: 0 0 6px;
}

.page-head p {
  margin: 0;
  color: #7a7f8c;
}

.filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.log-timeline {
  display: grid;
  gap: 14px;
}

.date-group {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
}

.date-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid #edf0f5;
}

.date-head span,
.type-head span {
  color: #8a9099;
  font-size: 13px;
}

.type-groups {
  display: grid;
  gap: 12px;
  padding: 12px;
}

.type-group {
  border: 1px solid #edf0f5;
  border-radius: 8px;
  background: #fafbfc;
}

.type-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
}

.log-list {
  display: grid;
}

.log-row {
  display: grid;
  grid-template-columns: 86px minmax(0, 1fr) 120px;
  gap: 12px;
  padding: 10px 12px;
  border-top: 1px solid #edf0f5;
  align-items: start;
}

.log-time {
  color: #606266;
  font-variant-numeric: tabular-nums;
}

.log-title {
  display: flex;
  gap: 10px;
  align-items: baseline;
  margin-bottom: 4px;
}

.log-title span {
  color: #303133;
  font-weight: 600;
}

.log-title small,
.details-text,
.log-ip {
  color: #8a9099;
  font-size: 12px;
}

.details-text {
  line-height: 1.5;
  word-break: break-word;
}

.log-ip {
  text-align: right;
}

@media (max-width: 720px) {
  .log-row {
    grid-template-columns: 1fr;
  }

  .log-ip {
    text-align: left;
  }
}
</style>
