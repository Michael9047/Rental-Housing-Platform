<template>
  <div class="admin-home" v-loading="loading">
    <div class="page-head">
      <div>
        <h2>管理员控制台</h2>
        <span>{{ authStore.user?.username }}</span>
      </div>
      <el-button :icon="Refresh" @click="loadData">刷新</el-button>
    </div>

    <section class="section">
      <div class="section-head">
        <h3>用户管理</h3>
        <el-button text type="primary" @click="router.push('/admin/users')">打开</el-button>
      </div>
      <div class="role-grid">
        <button class="role-card" @click="openUsers('admin')">
          <span>管理员</span>
          <strong>{{ overview?.users.by_role.admin || 0 }}</strong>
        </button>
        <button class="role-card" @click="openUsers('tenant')">
          <span>租客</span>
          <strong>{{ overview?.users.by_role.tenant || 0 }}</strong>
        </button>
        <button class="role-card" @click="openUsers('landlord')">
          <span>房东</span>
          <strong>{{ overview?.users.by_role.landlord || 0 }}</strong>
        </button>
        <button class="role-card" @click="openUsers('maintenance_worker')">
          <span>维修工</span>
          <strong>{{ overview?.users.by_role.maintenance_worker || 0 }}</strong>
        </button>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <h3>信息中心</h3>
        <el-tag :type="systemAlerts.length ? 'warning' : 'success'" size="small">
          {{ systemAlerts.length ? `${systemAlerts.length} 条异常` : '正常' }}
        </el-tag>
      </div>
      <div v-if="systemAlerts.length" class="alert-grid">
        <article
          v-for="alert in systemAlerts"
          :key="alert.id"
          class="alert-card"
          :class="`alert-${alert.severity}`"
        >
          <div class="alert-top">
            <el-tag :type="severityTag(alert.severity)" size="small">{{ severityLabel(alert.severity) }}</el-tag>
            <span>{{ alert.category }}</span>
          </div>
          <h4>{{ alert.title }}</h4>
          <p class="alert-summary">{{ alert.summary }}</p>
          <p class="alert-detail">{{ alert.detail }}</p>
          <div class="alert-foot">
            <span>{{ formatDateTime(alert.updated_at) }}</span>
            <el-button
              v-if="alert.action"
              size="small"
              type="primary"
              @click="runAlertAction(alert)"
            >
              {{ alert.action.label }}
            </el-button>
          </div>
        </article>
      </div>
      <el-empty v-else description="暂无系统异常" />
    </section>

    <section class="section">
      <div class="section-head">
        <h3>审计日志</h3>
        <el-button text type="primary" @click="router.push('/admin/logs')">打开</el-button>
      </div>
      <el-table :data="overview?.recent_logs || []" stripe>
        <el-table-column prop="action" label="操作" width="160" />
        <el-table-column prop="user_id" label="用户ID" width="90" />
        <el-table-column prop="resource_type" label="对象" width="110" />
        <el-table-column prop="resource_id" label="对象ID" width="90" />
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="详情" min-width="220">
          <template #default="{ row }">
            <span class="details">{{ formatDetails(row.details) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { adminService } from '@/services/admin'
import { useAuthStore } from '@/stores/auth'
import type { AdminOverview, SystemAlert, SystemAlertSeverity } from '@/types/admin'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const overview = ref<AdminOverview | null>(null)
const systemAlerts = ref<SystemAlert[]>([])

function formatDateTime(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

function formatDetails(details: Record<string, unknown> | null) {
  if (!details) return '-'
  return Object.entries(details).map(([key, value]) => `${key}: ${String(value)}`).join('，')
}

function openUsers(role: string) {
  router.push({ path: '/admin/users', query: { role } })
}

async function retryOutbox(id: string) {
  await adminService.retryNotification(id)
  ElMessage.success('已重新加入发送队列')
  await loadData()
}

function severityTag(severity: SystemAlertSeverity) {
  return ({ high: 'danger', medium: 'warning', low: 'info' }[severity] || 'info') as 'danger' | 'warning' | 'info'
}

function severityLabel(severity: SystemAlertSeverity) {
  return ({ high: '紧急', medium: '提醒', low: '关注' }[severity] || '关注')
}

async function runAlertAction(alert: SystemAlert) {
  if (!alert.action) return
  if (alert.action.type === 'retry_notification') {
    await retryOutbox(String(alert.action.resource_id))
    return
  }
  if (alert.action.type === 'retry_pms_sync') {
    await adminService.triggerPmsSync(Number(alert.action.resource_id))
    ElMessage.success('已触发 PMS 重新同步')
    await loadData()
  }
  if (alert.action.type === 'resolve_system_alert') {
    await adminService.resolveSystemAlert(Number(alert.action.resource_id))
    ElMessage.success('已标记处理')
    await loadData()
  }
}

async function loadData() {
  loading.value = true
  try {
    const [overviewData, alerts] = await Promise.all([
      adminService.getOverview(),
      adminService.getSystemAlerts(),
    ])
    overview.value = overviewData
    systemAlerts.value = alerts
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.admin-home {
  max-width: 1160px;
  margin: 0 auto;
}

.page-head,
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-head {
  margin-bottom: 16px;
}

h2,
h3 {
  margin: 0;
  color: #303133;
}

.page-head span {
  color: #909399;
  font-size: 13px;
}

.section {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 18px;
  margin-bottom: 16px;
}

.role-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 14px 0;
}

.role-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fafafa;
  padding: 16px;
  text-align: left;
}

.role-card {
  cursor: pointer;
}

.role-card:hover {
  border-color: #f06f3d;
  background: #fff7f2;
}

.role-card span {
  display: block;
  color: #606266;
  margin-bottom: 8px;
}

.role-card strong {
  font-size: 24px;
  color: #303133;
}

.alert-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.alert-card {
  border: 1px solid #ebeef5;
  border-left-width: 4px;
  border-radius: 8px;
  padding: 14px;
  background: #fff;
}

.alert-high {
  border-left-color: #f56c6c;
}

.alert-medium {
  border-left-color: #e6a23c;
}

.alert-low {
  border-left-color: #909399;
}

.alert-top,
.alert-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.alert-top span,
.alert-foot span {
  color: #909399;
  font-size: 12px;
}

.alert-card h4 {
  margin: 10px 0 6px;
  color: #303133;
  font-size: 16px;
}

.alert-summary,
.alert-detail {
  margin: 0;
  line-height: 1.6;
}

.alert-summary {
  color: #303133;
}

.alert-detail {
  color: #606266;
  font-size: 13px;
  margin-top: 6px;
}

.details {
  color: #606266;
  font-size: 12px;
}

@media (max-width: 900px) {
  .role-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .alert-grid {
    grid-template-columns: 1fr;
  }
}
</style>
