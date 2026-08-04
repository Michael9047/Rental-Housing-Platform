<template>
  <div class="admin-home" v-loading="loading">
    <div class="page-head">
      <div>
        <h2>仪表盘</h2>
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

    <div class="ops-grid">
      <section class="section ops-panel">
        <div class="section-head">
          <h3>异常中心</h3>
          <div class="head-actions">
            <el-tag :type="systemAlerts.length ? 'warning' : 'success'" size="small">
              {{ systemAlerts.length ? `${systemAlerts.length} 条异常` : '正常' }}
            </el-tag>
            <el-button text type="primary" @click="router.push('/admin/alerts')">打开</el-button>
          </div>
        </div>
        <div v-if="systemAlerts.length" class="alert-list">
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

      <section class="section ops-panel">
        <div class="section-head">
          <h3>信息通知</h3>
          <div class="head-actions">
            <el-tag :type="unreadCount ? 'warning' : 'info'" size="small">
              {{ unreadCount ? `${unreadCount} 条未读` : '无未读' }}
            </el-tag>
            <el-button text type="primary" @click="router.push('/admin/notifications')">打开</el-button>
          </div>
        </div>
        <div v-if="notifications.length" class="notice-list">
          <button
            v-for="notice in notifications"
            :key="notice.id"
            class="notice-card"
            :class="{ unread: !notice.is_read }"
            @click="markNoticeRead(notice.id)"
          >
            <span class="notice-title">{{ notice.title }}</span>
            <span class="notice-time">{{ formatDateTime(notice.created_at) }}</span>
            <span class="notice-content">{{ notice.content || notice.body || '-' }}</span>
          </button>
        </div>
        <el-empty v-else description="暂无通知" />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { adminService } from '@/services/admin'
import { notificationService } from '@/services/notification'
import { useAuthStore } from '@/stores/auth'
import type { Notification } from '@/types/booking'
import type { AdminOverview, SystemAlert, SystemAlertSeverity } from '@/types/admin'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const overview = ref<AdminOverview | null>(null)
const systemAlerts = ref<SystemAlert[]>([])
const notifications = ref<Notification[]>([])
const unreadCount = ref(0)

function formatDateTime(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
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

async function markNoticeRead(id: number) {
  const notice = notifications.value.find((item) => item.id === id)
  if (!notice || notice.is_read) return
  await notificationService.markRead(id)
  await loadData()
}

async function loadData() {
  loading.value = true
  try {
    const [overviewData, alerts, noticeData] = await Promise.all([
      adminService.getOverview(),
      adminService.getSystemAlerts(),
      notificationService.list({ page: 1, page_size: 30, unread_only: true, business_only: true }),
    ])
    overview.value = overviewData
    systemAlerts.value = alerts
    notifications.value = noticeData.items
    unreadCount.value = noticeData.total
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.admin-home {
  box-sizing: border-box;
  width: 100%;
}

.page-head,
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-width: 0;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
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
  box-sizing: border-box;
  padding: 18px;
  margin-bottom: 16px;
  min-width: 0;
}

.role-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
  gap: 12px;
  margin: 14px 0;
}

.role-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  box-sizing: border-box;
  background: #fafafa;
  padding: 16px;
  text-align: left;
  min-width: 0;
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

.ops-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr));
  gap: 16px;
  align-items: stretch;
}

.ops-panel {
  display: flex;
  flex-direction: column;
  height: clamp(360px, calc(100vh - 330px), 620px);
  min-height: 0;
}

.alert-list {
  display: grid;
  align-content: start;
  gap: 12px;
  flex: 1;
  margin-top: 14px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.alert-card {
  border: 1px solid #ebeef5;
  border-left-width: 4px;
  border-radius: 8px;
  box-sizing: border-box;
  padding: 14px;
  background: #fff;
  min-width: 0;
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

.notice-list {
  display: grid;
  align-content: start;
  gap: 10px;
  flex: 1;
  margin-top: 14px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.notice-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fff;
  box-sizing: border-box;
  cursor: pointer;
  display: grid;
  gap: 6px;
  padding: 12px;
  text-align: left;
  width: 100%;
  min-width: 0;
}

.notice-card:hover {
  border-color: #f06f3d;
}

.notice-card.unread {
  background: #fff7f2;
  border-color: #f3c3aa;
}

.notice-title {
  color: #303133;
  font-weight: 600;
}

.notice-time,
.notice-content {
  color: #909399;
  font-size: 12px;
}

.notice-content {
  color: #606266;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

@media (max-width: 900px) {
  .page-head,
  .section-head {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .ops-panel {
    height: clamp(340px, 55vh, 520px);
  }
}

@media (max-width: 520px) {
  .role-grid {
    grid-template-columns: 1fr;
  }
}
</style>
