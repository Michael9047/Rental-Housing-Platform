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

    <section class="section-panel">
      <div class="section-head">
        <h3>当前异常</h3>
        <span>{{ filteredAlerts.length }} 条</span>
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
          <h4>{{ alert.title }}</h4>
          <p>{{ alert.summary }}</p>
          <p class="detail">{{ alert.detail }}</p>
          <div class="meta-row">
            <span>来源：{{ alert.source }}</span>
            <span>编号：{{ alert.source_id }}</span>
          </div>
          <div class="card-foot">
            <span>{{ formatDateTime(alert.updated_at) }}</span>
            <el-button v-if="alert.action" size="small" type="primary" @click="runAlertAction(alert)">
              {{ alert.action.label }}
            </el-button>
          </div>
        </article>
      </div>
      <el-empty v-else :description="alerts.length ? '当前分类暂无异常' : '暂无系统异常'" />
    </section>

    <section class="section-panel">
      <div class="section-head">
        <h3>处理记录</h3>
        <span>{{ records.length }} 条</span>
      </div>

      <div class="record-query">
        <el-input
          v-model="recordQuery.keyword"
          clearable
          placeholder="搜索标题、来源、编号、备注"
          @keyup.enter="queryRecords"
        />
        <el-select v-model="recordQuery.category" clearable placeholder="分类">
          <el-option v-for="item in recordCategories" :key="item" :label="item" :value="item" />
        </el-select>
        <el-select v-model="recordQuery.action_type" clearable placeholder="处理动作">
          <el-option
            v-for="item in actionOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-button type="primary" @click="queryRecords">查询</el-button>
        <el-button @click="resetRecordQuery">重置</el-button>
      </div>

      <div v-if="records.length" class="record-grid">
        <article
          v-for="record in records"
          :key="record.id"
          class="record-card"
          tabindex="0"
          @click="openRecord(record)"
          @keyup.enter="openRecord(record)"
        >
          <div class="record-card-head">
            <el-tag :type="severityTag(record.severity)" size="small">
              {{ severityLabel(record.severity) }}
            </el-tag>
            <span>#{{ record.id }}</span>
          </div>
          <h4>{{ record.title }}</h4>
          <p>{{ actionLabel(record.action_type) }}</p>
          <div class="status-flow">
            <span>{{ record.status_before || '-' }}</span>
            <b>→</b>
            <span>{{ record.status_after || '-' }}</span>
          </div>
          <div class="record-card-meta">
            <span>{{ record.category }}</span>
            <span>{{ record.source }} / {{ record.source_id || '-' }}</span>
            <span>{{ formatDateTime(record.created_at) }}</span>
          </div>
        </article>
      </div>
      <el-empty v-else description="暂无处理记录" />
    </section>

    <el-dialog
      v-model="recordDialogVisible"
      title="处理记录详情"
      width="min(720px, 92vw)"
    >
      <div v-if="selectedRecord" class="record-dialog">
        <div class="dialog-title-row">
          <el-tag :type="severityTag(selectedRecord.severity)" size="small">
            {{ severityLabel(selectedRecord.severity) }}
          </el-tag>
          <strong>{{ selectedRecord.title }}</strong>
        </div>
        <dl>
          <div>
            <dt>记录编号</dt>
            <dd>{{ selectedRecord.id }}</dd>
          </div>
          <div>
            <dt>异常键</dt>
            <dd>{{ selectedRecord.alert_key }}</dd>
          </div>
          <div>
            <dt>分类</dt>
            <dd>{{ selectedRecord.category }}</dd>
          </div>
          <div>
            <dt>处理动作</dt>
            <dd>{{ actionLabel(selectedRecord.action_type) }}</dd>
          </div>
          <div>
            <dt>来源</dt>
            <dd>{{ selectedRecord.source }} / {{ selectedRecord.source_id || '-' }}</dd>
          </div>
          <div>
            <dt>状态变化</dt>
            <dd>{{ selectedRecord.status_before || '-' }} → {{ selectedRecord.status_after || '-' }}</dd>
          </div>
          <div>
            <dt>处理人</dt>
            <dd>{{ selectedRecord.handled_by_id || '-' }}</dd>
          </div>
          <div>
            <dt>处理时间</dt>
            <dd>{{ formatDateTime(selectedRecord.created_at) }}</dd>
          </div>
          <div class="full-row">
            <dt>备注</dt>
            <dd>{{ selectedRecord.note || '-' }}</dd>
          </div>
          <div class="full-row">
            <dt>详细内容</dt>
            <dd>
              <pre>{{ formatExtra(selectedRecord.extra) }}</pre>
            </dd>
          </div>
        </dl>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { adminService } from '@/services/admin'
import type { SystemAlert, SystemAlertProcessRecord, SystemAlertSeverity } from '@/types/admin'

const loading = ref(false)
const alerts = ref<SystemAlert[]>([])
const records = ref<SystemAlertProcessRecord[]>([])
const selectedCategory = ref('全部')
const recordDialogVisible = ref(false)
const selectedRecord = ref<SystemAlertProcessRecord | null>(null)
const recordQuery = reactive({
  keyword: '',
  category: '',
  action_type: '',
})

const recordCategories = ['预约', '维修', '合同', '支付', '对接', '通知', '接口', '系统']
const actionOptions = [
  { label: '处理业务异常', value: 'resolve_generated_alert' },
  { label: '处理系统异常', value: 'resolve_system_alert' },
  { label: '重新发送通知', value: 'retry_notification' },
  { label: '重新同步 PMS', value: 'retry_pms_sync' },
]

const categoryStats = computed(() => {
  const orderedCategories = ['全部', '预约', '维修', '合同', '支付', '对接', '通知', '接口', '系统']
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

function severityTag(severity: SystemAlertSeverity | string) {
  const tags: Record<string, 'danger' | 'warning' | 'info'> = { high: 'danger', medium: 'warning', low: 'info' }
  return tags[severity] || 'info'
}

function severityLabel(severity: SystemAlertSeverity | string) {
  const labels: Record<string, string> = { high: '紧急', medium: '提醒', low: '关注' }
  return labels[severity] || '关注'
}

function actionLabel(actionType: string) {
  return ({
    retry_notification: '重新发送通知',
    retry_pms_sync: '重新同步 PMS',
    resolve_system_alert: '处理系统异常',
    resolve_generated_alert: '处理业务异常',
  }[actionType] || actionType)
}

function recordQueryParams() {
  return {
    keyword: recordQuery.keyword.trim() || undefined,
    category: recordQuery.category || undefined,
    action_type: recordQuery.action_type || undefined,
    limit: 80,
  }
}

function openRecord(record: SystemAlertProcessRecord) {
  selectedRecord.value = record
  recordDialogVisible.value = true
}

function formatExtra(extra: Record<string, unknown> | null) {
  if (!extra) return '-'
  return JSON.stringify(extra, null, 2)
}

async function queryRecords() {
  records.value = await adminService.getSystemAlertRecords(recordQueryParams())
}

async function resetRecordQuery() {
  recordQuery.keyword = ''
  recordQuery.category = ''
  recordQuery.action_type = ''
  await queryRecords()
}

async function runAlertAction(alert: SystemAlert) {
  if (!alert.action) return
  if (alert.action.type === 'retry_notification') {
    await adminService.retryNotification(String(alert.action.resource_id))
    ElMessage.success('已重新加入发送队列')
  }
  if (alert.action.type === 'retry_pms_sync') {
    const result = await adminService.triggerPmsSync(Number(alert.action.resource_id))
    const errors = Number(result.errors || 0)
    if (errors > 0) {
      ElMessage.warning(`同步完成，但有 ${errors} 条失败`)
    } else {
      ElMessage.success('已触发重新同步')
    }
  }
  if (alert.action.type === 'resolve_system_alert') {
    await adminService.resolveSystemAlert(Number(alert.action.resource_id))
    ElMessage.success('已标记处理')
  }
  if (alert.action.type === 'resolve_generated_alert') {
    await adminService.resolveGeneratedSystemAlert(alert)
    ElMessage.success('已标记处理')
  }
  await loadData()
}

async function loadData() {
  loading.value = true
  try {
    const [alertRows, recordRows] = await Promise.all([
      adminService.getSystemAlerts(),
      adminService.getSystemAlertRecords(recordQueryParams()),
    ])
    alerts.value = alertRows
    records.value = recordRows
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
  display: grid;
  gap: 16px;
  width: 100%;
}

.page-head,
.section-head,
.card-top,
.card-foot,
.meta-row,
.record-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.page-head {
  margin-bottom: 0;
}

h2,
h3,
h4,
p {
  margin: 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr));
  gap: 10px;
}

.summary-card,
.section-panel,
.alert-card,
.record-card {
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

.summary-card span,
.section-head span,
.card-top span,
.card-foot span,
.meta-row,
.record-meta,
.detail {
  color: #909399;
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

.section-panel {
  display: grid;
  gap: 14px;
  padding: 16px;
}

.section-head h3 {
  color: #303133;
  font-size: 16px;
}

.record-query {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 150px 180px auto auto;
  gap: 10px;
}

.card-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 360px), 1fr));
  align-items: start;
  gap: 12px;
}

.alert-card {
  border-left-width: 4px;
  display: grid;
  gap: 10px;
  padding: 16px;
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

.record-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
  gap: 12px;
}

.record-card {
  cursor: pointer;
  display: grid;
  gap: 10px;
  padding: 14px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}

.record-card:hover,
.record-card:focus-visible {
  border-color: #f06f3d;
  box-shadow: 0 8px 20px rgb(0 0 0 / 7%);
  outline: none;
  transform: translateY(-1px);
}

.record-card-head,
.status-flow {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.record-card h4 {
  color: #303133;
  font-size: 15px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.record-card p {
  color: #606266;
  font-size: 13px;
  line-height: 1.5;
}

.record-card-head span,
.record-card-meta {
  color: #909399;
  font-size: 12px;
}

.status-flow {
  background: #f7f8fa;
  border-radius: 6px;
  color: #606266;
  font-size: 13px;
  padding: 8px 10px;
}

.status-flow span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-flow b {
  color: #c0c4cc;
  font-weight: 500;
}

.record-card-meta {
  display: grid;
  gap: 4px;
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
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

.record-dialog pre {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  box-sizing: border-box;
  color: #303133;
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
  max-height: 260px;
  overflow: auto;
  padding: 10px;
  white-space: pre-wrap;
}

@media (max-width: 680px) {
  .record-query {
    grid-template-columns: 1fr;
  }

  .page-head,
  .card-foot {
    align-items: flex-start;
  }

  .page-head,
  .card-foot,
  .meta-row {
    flex-direction: column;
  }

  .record-dialog dl {
    grid-template-columns: 1fr;
  }
}
</style>
