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
      </div>
      <el-table :data="failedNotifications" stripe>
        <el-table-column prop="event_type" label="类型" width="140" />
        <el-table-column prop="user_id" label="用户ID" width="90" />
        <el-table-column prop="booking_id" label="预约ID" width="90" />
        <el-table-column prop="attempts" label="次数" width="80" />
        <el-table-column prop="last_error" label="错误" min-width="220" show-overflow-tooltip />
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="retryOutbox(row.id)">重试</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!failedNotifications.length" description="暂无失败通知" />
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
import type { AdminOverview, NotificationOutboxItem } from '@/types/admin'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const overview = ref<AdminOverview | null>(null)
const failedNotifications = ref<NotificationOutboxItem[]>([])

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

async function loadData() {
  loading.value = true
  try {
    const [overviewData, failed] = await Promise.all([
      adminService.getOverview(),
      adminService.getFailedNotifications(),
    ])
    overview.value = overviewData
    failedNotifications.value = failed
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

.details {
  color: #606266;
  font-size: 12px;
}

@media (max-width: 900px) {
  .role-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
