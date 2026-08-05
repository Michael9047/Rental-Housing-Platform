<template>
  <div class="admin-detail-page" v-loading="loading">
    <div class="page-head">
      <div>
        <h2>异常中心</h2>
        <span>只接收系统明确报错和接口运行异常</span>
      </div>
      <div class="head-actions">
        <el-button :icon="Refresh" @click="loadData">刷新</el-button>
        <el-button
          type="primary"
          :icon="Check"
          :disabled="!unreadAlerts.length"
          :loading="markingAll"
          @click="markAllUnread"
        >
          一键已读
        </el-button>
      </div>
    </div>

    <div class="summary-grid">
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

    <el-tabs v-model="activeTab" class="alert-tabs">
      <el-tab-pane :label="`未读 ${unreadAlerts.length}`" name="unread">
        <section class="section-panel">
          <div class="section-head">
            <h3>未读异常</h3>
            <span>{{ filteredUnreadAlerts.length }} 条</span>
          </div>
          <div v-if="filteredUnreadAlerts.length" class="card-list">
            <article
              v-for="alert in filteredUnreadAlerts"
              :key="alert.id"
              class="alert-card"
              :class="`alert-${alert.severity}`"
            >
              <div class="card-top">
                <el-tag :type="severityTag(alert.severity)" size="small">{{ severityLabel(alert.severity) }}</el-tag>
                <span>{{ alert.category }}</span>
              </div>
              <h4>{{ alert.title }}</h4>
              <p>{{ alert.summary }}</p>
              <div class="meta-row">
                <span>类型：{{ alert.category }}</span>
                <span>位置：{{ alert.location || `${alert.source} / ${alert.source_id}` }}</span>
              </div>
              <div class="card-foot">
                <span>{{ formatDateTime(alert.updated_at) }}</span>
                <div class="card-actions">
                  <el-button size="small" text :icon="View" @click="openAlert(alert)">查看</el-button>
                  <el-button
                    size="small"
                    type="primary"
                    :loading="markingId === alert.id"
                    @click="markRead(alert)"
                  >
                    标为已读
                  </el-button>
                </div>
              </div>
            </article>
          </div>
          <el-empty v-else description="暂无未读异常" />
        </section>
      </el-tab-pane>

      <el-tab-pane :label="`已读 ${readAlerts.length}`" name="read">
        <section class="section-panel">
          <div class="section-head">
            <h3>已读异常</h3>
            <span>{{ filteredReadAlerts.length }} 条</span>
          </div>
          <div v-if="filteredReadAlerts.length" class="card-list">
            <article
              v-for="alert in filteredReadAlerts"
              :key="alert.id"
              class="alert-card is-read"
              :class="`alert-${alert.severity}`"
              @click="openAlert(alert)"
            >
              <div class="card-top">
                <el-tag :type="severityTag(alert.severity)" size="small">{{ severityLabel(alert.severity) }}</el-tag>
                <span>{{ alert.category }}</span>
              </div>
              <h4>{{ alert.title }}</h4>
              <p>{{ alert.summary }}</p>
              <div class="meta-row">
                <span>类型：{{ alert.category }}</span>
                <span>位置：{{ alert.location || `${alert.source} / ${alert.source_id}` }}</span>
              </div>
            </article>
          </div>
          <el-empty v-else description="暂无已读异常" />
        </section>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="dialogVisible" title="异常详情" width="min(720px, 92vw)">
      <div v-if="selectedAlert" class="record-dialog">
        <div class="dialog-title-row">
          <el-tag :type="severityTag(selectedAlert.severity)" size="small">
            {{ severityLabel(selectedAlert.severity) }}
          </el-tag>
          <strong>{{ selectedAlert.title }}</strong>
        </div>
        <dl>
          <div>
            <dt>类型</dt>
            <dd>{{ selectedAlert.category }}</dd>
          </div>
          <div>
            <dt>位置</dt>
            <dd>{{ selectedAlert.location || `${selectedAlert.source} / ${selectedAlert.source_id}` }}</dd>
          </div>
          <div class="full-row">
            <dt>报错内容 / 运行详情</dt>
            <dd>
              <div class="extra-blocks">
                <div v-for="item in alertLocationItems(selectedAlert)" :key="item.label" class="extra-block">
                  <strong>{{ item.label }}</strong>
                  <p>{{ item.value }}</p>
                </div>
              </div>
            </dd>
          </div>
        </dl>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">关闭</el-button>
        <el-button
          v-if="selectedAlert && !selectedAlert.read"
          type="primary"
          :loading="markingId === selectedAlert.id"
          @click="markSelectedRead"
        >
          标为已读
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Check, Refresh, View } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { adminService } from '@/services/admin'
import type { SystemAlert, SystemAlertSeverity } from '@/types/admin'

const loading = ref(false)
const markingAll = ref(false)
const markingId = ref<string | null>(null)
const activeTab = ref<'unread' | 'read'>('unread')
const selectedCategory = ref('全部')
const unreadAlerts = ref<SystemAlert[]>([])
const readAlerts = ref<SystemAlert[]>([])
const dialogVisible = ref(false)
const selectedAlert = ref<SystemAlert | null>(null)

const allVisibleAlerts = computed(() => [...unreadAlerts.value, ...readAlerts.value])

const categoryStats = computed(() => {
  const orderedCategories = ['全部', '系统接口', 'AI检索', '订单信息', '合同信息', '售后处理', '预约情况', '户型信息']
  const seen = new Set(orderedCategories)
  const dynamicCategories = allVisibleAlerts.value
    .map((alert) => alert.category)
    .filter((category) => {
      if (seen.has(category)) return false
      seen.add(category)
      return true
    })
  return [...orderedCategories, ...dynamicCategories]
    .map((category) => {
      const rows = category === '全部'
        ? allVisibleAlerts.value
        : allVisibleAlerts.value.filter((alert) => alert.category === category)
      return {
        category,
        count: rows.length,
        highCount: rows.filter((alert) => alert.severity === 'high').length,
      }
    })
    .filter((item) => item.category === '全部' || item.count > 0)
})

const filteredUnreadAlerts = computed(() => (
  selectedCategory.value === '全部'
    ? unreadAlerts.value
    : unreadAlerts.value.filter((alert) => alert.category === selectedCategory.value)
))

const filteredReadAlerts = computed(() => (
  selectedCategory.value === '全部'
    ? readAlerts.value
    : readAlerts.value.filter((alert) => alert.category === selectedCategory.value)
))

function formatDateTime(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

function severityTag(severity: SystemAlertSeverity | string) {
  const tags: Record<string, 'danger' | 'warning' | 'info'> = { high: 'danger', medium: 'warning', low: 'info' }
  return tags[severity] || 'info'
}

function severityLabel(severity: SystemAlertSeverity | string) {
  const labels: Record<string, string> = { high: '紧急', medium: '提醒', low: '关注' }
  return labels[severity] || '关注'
}

function openAlert(alert: SystemAlert) {
  selectedAlert.value = alert
  dialogVisible.value = true
}

function alertLocationItems(alert: SystemAlert) {
  const source = alert.extra || {}
  const items = [
    { label: '报错位置', value: alert.location || `${alert.source} / ${alert.source_id}` },
    { label: '报错内容', value: formatExtraValue(source['报错内容'] || alert.detail || alert.summary) },
    { label: '运行详情', value: formatExtraValue(source['运行详情'] || '无') },
    { label: '异常类型', value: alert.category },
    { label: '来源表', value: alert.source },
    { label: '来源编号', value: String(alert.source_id || '-') },
  ]
  const usefulKeys = [
    '系统说明',
    '报错位置',
    '错误类型',
    '接口路径',
    '请求方法',
    'HTTP状态码',
    '请求编号',
    '代码位置',
    '任务状态',
    '错误原因',
    '异常原因',
    '接口返回',
    '运行错误',
    '接口名称',
    '通知类型',
    '尝试次数',
    '支付过期时间',
    '合同编号',
    'PDF状态',
  ]
  const seenLabels = new Set(items.map((item) => item.label))
  usefulKeys.forEach((key) => {
    if (!seenLabels.has(key) && source[key] !== undefined && source[key] !== null && source[key] !== '') {
      seenLabels.add(key)
      items.push({ label: key, value: formatExtraValue(source[key]) })
    }
  })
  return items
}

function formatExtraValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '无'
  if (Array.isArray(value)) return value.length ? value.map(formatExtraValue).join('、') : '无'
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    return entries.length ? entries.map(([key, item]) => `${key}：${formatExtraValue(item)}`).join('；') : '无'
  }
  return String(value)
}

async function markRead(alert: SystemAlert) {
  markingId.value = alert.id
  try {
    await adminService.markSystemAlertRead(alert)
    ElMessage.success('已标为已读')
    await loadData()
  } finally {
    markingId.value = null
  }
}

async function markSelectedRead() {
  if (!selectedAlert.value) return
  await markRead(selectedAlert.value)
  dialogVisible.value = false
}

async function markAllUnread() {
  if (!unreadAlerts.value.length) return
  markingAll.value = true
  try {
    await Promise.all(unreadAlerts.value.map((alert) => adminService.markSystemAlertRead(alert)))
    ElMessage.success('未读异常已全部标记为已读')
    await loadData()
  } finally {
    markingAll.value = false
  }
}

async function loadData() {
  loading.value = true
  try {
    const rows = await adminService.getSystemAlerts({ read_status: 'all' })
    unreadAlerts.value = rows.filter((alert) => !alert.read)
    readAlerts.value = rows.filter((alert) => alert.read)
    if (
      selectedCategory.value !== '全部' &&
      !allVisibleAlerts.value.some((alert) => alert.category === selectedCategory.value)
    ) {
      selectedCategory.value = '全部'
    }
  } catch (error) {
    unreadAlerts.value = []
    readAlerts.value = []
    selectedCategory.value = '全部'
    ElMessage.error('异常中心数据读取失败，请稍后刷新')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.admin-detail-page {
  box-sizing: border-box;
  display: grid;
  gap: 16px;
  width: 100%;
}

.page-head,
.section-head,
.card-top,
.card-foot,
.meta-row {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: space-between;
  min-width: 0;
}

.head-actions,
.card-actions {
  align-items: center;
  display: flex;
  gap: 8px;
}

h2,
h3,
h4,
p {
  margin: 0;
}

.page-head h2 {
  color: #303133;
}

.page-head span,
.section-head span,
.card-top span,
.card-foot span,
.meta-row {
  color: #909399;
  font-size: 13px;
}

.summary-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr));
}

.summary-card,
.section-panel,
.alert-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  box-sizing: border-box;
  min-width: 0;
}

.summary-card {
  cursor: pointer;
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  text-align: left;
}

.summary-card:hover,
.summary-card.active {
  background: #fff7f2;
  border-color: #f06f3d;
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

.alert-tabs {
  min-width: 0;
}

.section-panel {
  display: grid;
  gap: 14px;
  padding: 16px;
}

.section-head h3 {
  color: #303133;
  font-size: 16px;
}

.card-list {
  align-items: start;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 360px), 1fr));
}

.alert-card {
  border-left-width: 4px;
  cursor: default;
  display: grid;
  gap: 10px;
  padding: 16px;
}

.alert-card.is-read {
  cursor: pointer;
  opacity: 0.78;
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

.alert-card h4 {
  color: #303133;
  font-size: 16px;
}

.alert-card p {
  color: #606266;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.record-dialog {
  display: grid;
  gap: 16px;
}

.dialog-title-row {
  align-items: center;
  display: flex;
  gap: 10px;
}

.dialog-title-row strong {
  color: #303133;
  font-size: 16px;
}

.record-dialog dl {
  display: grid;
  gap: 10px 14px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin: 0;
}

.record-dialog dl > div {
  background: #f7f8fa;
  border-radius: 6px;
  box-sizing: border-box;
  min-width: 0;
  padding: 10px 12px;
}

.record-dialog .full-row {
  grid-column: 1 / -1;
}

.record-dialog dt {
  color: #909399;
  font-size: 12px;
  margin-bottom: 5px;
}

.record-dialog dd {
  color: #303133;
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
  overflow-wrap: anywhere;
}

.extra-blocks {
  display: grid;
  gap: 10px;
}

.extra-block {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  box-sizing: border-box;
  display: grid;
  gap: 6px;
  padding: 10px;
}

.extra-block strong {
  color: #606266;
  font-size: 13px;
}

.extra-block p {
  color: #303133;
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
  max-height: 220px;
  overflow: auto;
  overflow-wrap: anywhere;
}

@media (max-width: 680px) {
  .page-head,
  .card-foot,
  .meta-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .record-dialog dl {
    grid-template-columns: 1fr;
  }
}
</style>
