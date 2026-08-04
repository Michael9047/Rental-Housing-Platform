<template>
  <div class="admin-detail-page" v-loading="loading">
    <div class="page-head">
      <h2>异常处理</h2>
      <el-button :icon="Refresh" @click="loadData">刷新</el-button>
    </div>

    <div v-if="alerts.length" class="summary-grid">
      <button
        v-for="item in categoryStats"
        :key="item.category"
        class="summary-card"
        :class="{ active: selectedCategory === item.category }"
        @click="selectedCategory = item.category"
      >
        <span>{{ item.category }}</span>
        <strong>{{ item.count }}</strong>
        <small>{{ item.highCount ? `${item.highCount} 条紧急` : '无紧急' }}</small>
      </button>
    </div>

    <div v-if="filteredAlerts.length" class="card-list">
      <article
        v-for="alert in filteredAlerts"
        :key="alert.id"
        class="alert-card"
        :class="`alert-${alert.severity}`"
      >
        <div class="card-top">
          <el-tag :type="severityTag(alert.severity)" size="small">{{ severityLabel(alert.severity) }}</el-tag>
          <span>{{ alert.category }}</span>
        </div>
        <h3>{{ alert.title }}</h3>
        <p>{{ alert.summary }}</p>
        <p class="detail">{{ alert.detail }}</p>
        <div class="card-foot">
          <span>{{ formatDateTime(alert.updated_at) }}</span>
          <el-button v-if="alert.action" size="small" type="primary" @click="runAlertAction(alert)">
            {{ alert.action.label }}
          </el-button>
        </div>
      </article>
    </div>
    <el-empty v-else :description="alerts.length ? '当前分类暂无异常' : '暂无系统异常'" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { adminService } from '@/services/admin'
import type { SystemAlert, SystemAlertSeverity } from '@/types/admin'

const loading = ref(false)
const alerts = ref<SystemAlert[]>([])
const selectedCategory = ref('全部')

const categoryStats = computed(() => {
  const orderedCategories = ['全部', '预约', '维修', '合同', '支付', '对接', '通知', '系统']
  const seen = new Set(orderedCategories)
  const dynamicCategories = alerts.value
    .map((alert) => alert.category)
    .filter((category) => {
      if (seen.has(category)) return false
      seen.add(category)
      return true
    })

  return [...orderedCategories, ...dynamicCategories]
    .map((category) => {
      const rows = category === '全部'
        ? alerts.value
        : alerts.value.filter((alert) => alert.category === category)
      return {
        category,
        count: rows.length,
        highCount: rows.filter((alert) => alert.severity === 'high').length,
      }
    })
    .filter((item) => item.category === '全部' || item.count > 0)
})

const filteredAlerts = computed(() => (
  selectedCategory.value === '全部'
    ? alerts.value
    : alerts.value.filter((alert) => alert.category === selectedCategory.value)
))

function formatDateTime(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
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
    await adminService.retryNotification(String(alert.action.resource_id))
    ElMessage.success('已重新加入发送队列')
  }
  if (alert.action.type === 'retry_pms_sync') {
    await adminService.triggerPmsSync(Number(alert.action.resource_id))
    ElMessage.success('已触发重新同步')
  }
  if (alert.action.type === 'resolve_system_alert') {
    await adminService.resolveSystemAlert(Number(alert.action.resource_id))
    ElMessage.success('已标记处理')
  }
  await loadData()
}

async function loadData() {
  loading.value = true
  try {
    alerts.value = await adminService.getSystemAlerts()
    if (
      selectedCategory.value !== '全部' &&
      !alerts.value.some((alert) => alert.category === selectedCategory.value)
    ) {
      selectedCategory.value = '全部'
    }
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.admin-detail-page {
  box-sizing: border-box;
  width: 100%;
}

.page-head,
.card-top,
.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.page-head {
  margin-bottom: 16px;
}

h2,
h3 {
  margin: 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.summary-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  box-sizing: border-box;
  cursor: pointer;
  display: grid;
  gap: 4px;
  min-width: 0;
  padding: 12px 14px;
  text-align: left;
}

.summary-card:hover,
.summary-card.active {
  background: #fff7f2;
  border-color: #f06f3d;
}

.summary-card span {
  color: #606266;
  font-size: 13px;
}

.summary-card strong {
  color: #303133;
  font-size: 24px;
  line-height: 1.1;
}

.summary-card small {
  color: #909399;
  font-size: 12px;
}

.summary-card.active span,
.summary-card.active strong {
  color: #e76535;
}

.card-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 360px), 1fr));
  align-items: start;
  gap: 12px;
}

.alert-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-left-width: 4px;
  border-radius: 8px;
  box-sizing: border-box;
  padding: 16px;
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

.card-top span,
.card-foot span,
.detail {
  color: #909399;
  font-size: 13px;
}

.alert-card h3 {
  color: #303133;
  font-size: 16px;
  margin-top: 10px;
}

.alert-card p {
  color: #606266;
  line-height: 1.6;
  margin: 8px 0 0;
  overflow-wrap: anywhere;
}

@media (max-width: 560px) {
  .page-head,
  .card-foot {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
