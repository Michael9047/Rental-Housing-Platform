<template>
  <div class="history-page" v-loading="loading">
    <div class="page-header">
      <h2>📜 修改记录</h2>
      <p class="subtitle">查看自己所有房源的最近操作历史</p>
    </div>

    <!-- 筛选区 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filter" @submit.prevent>
        <el-form-item label="操作类型">
          <el-select v-model="filter.action" placeholder="全部" clearable style="width:160px">
            <el-option label="创建房源" value="property_create" />
            <el-option label="修改房源" value="property_update" />
            <el-option label="删除房源" value="property_delete" />
            <el-option label="恢复房源" value="property_restore" />
            <el-option label="硬删除" value="property_hard_delete" />
            <el-option label="批量操作" value="batch" />
            <el-option label="管理员审核" value="property_moderate" />
          </el-select>
        </el-form-item>
        <el-form-item label="房源 ID">
          <el-input v-model.number="filter.resourceId" placeholder="如: 123" style="width:160px" clearable />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filter.dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            style="width:340px"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="onSearch">查询</el-button>
          <el-button :icon="RefreshLeft" @click="onReset">重置</el-button>
          <el-button :icon="Refresh" @click="loadList">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 列表 -->
    <el-card shadow="never" class="list-card">
      <template #header>
        <div class="card-header">
          <span>共 {{ total }} 条记录</span>
          <div style="display:flex;gap:8px">
            <el-button
              :type="batchMode ? 'warning' : 'default'"
              size="small"
              @click="toggleBatchMode"
            >{{ batchMode ? '取消批量操作' : '📋 批量删除' }}</el-button>
            <el-popconfirm
              title="确定清空所有修改记录吗？此操作不可恢复"
              confirm-button-text="清空"
              cancel-button-text="取消"
              @confirm="clearAll"
            >
              <template #reference>
                <el-button size="small" type="danger" :loading="clearing">🗑 一键清空</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </template>

      <el-empty v-if="!loading && list.length === 0" description="暂无修改记录" />

      <el-table v-else :data="list" stripe size="small" style="width:100%">
        <el-table-column v-if="batchMode" width="40">
          <template #default="{ row }">
            <el-checkbox :model-value="selectedIds.has(row.id)" @change="toggleSelect(row.id)" />
          </template>
        </el-table-column>
        <el-table-column label="时间" width="180" sortable>
          <template #default="{ row }">
            <span class="time-cell">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130">
          <template #default="{ row }">
            <el-tag size="small" :type="actionTagType(row.action)">{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="房源 ID" width="90">
          <template #default="{ row }">
            <el-link v-if="row.resource_id" type="primary" :underline="false" @click="goProperty(row.resource_id)">
              #{{ row.resource_id }}
            </el-link>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作人" width="100">
          <template #default="{ row }">#{{ row.user_id ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="变更详情" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="details-cell">{{ detailsSummary(row.details) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="showDetail(row)">查看详情</el-button>
            <el-button
              size="small" text type="warning"
              :disabled="!canRevert(row)"
              :loading="revertingId === row.id"
              @click="confirmRevert(row)"
            >撤销</el-button>
            <el-popconfirm
              title="确定删除该记录？"
              confirm-button-text="删除"
              cancel-button-text="取消"
              @confirm="deleteLog(row)"
            >
              <template #reference>
                <el-button size="small" text type="danger" :loading="deletingId === row.id">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top:16px;justify-content:flex-end;display:flex"
        @current-change="loadList"
        @size-change="onSizeChange"
      />
    </el-card>

    <!-- 批量操作底栏 -->
    <transition name="batch-slide">
      <div v-if="batchMode && selectedIds.size > 0" class="batch-bar">
        <div class="batch-bar-inner">
          <span class="batch-count">已选择 <strong>{{ selectedIds.size }}</strong> 条记录</span>
          <el-popconfirm
            title="确定批量删除已选记录吗？"
            confirm-button-text="确认删除"
            cancel-button-text="取消"
            @confirm="batchDelete"
          >
            <template #reference>
              <el-button type="danger" :loading="batchDeleting">🗑 批量删除</el-button>
            </template>
          </el-popconfirm>
          <el-button text @click="toggleBatchMode">取消</el-button>
        </div>
      </div>
    </transition>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="detailVisible"
      title="操作详情"
      direction="rtl"
      size="480px"
    >
      <div v-if="detailItem" class="detail-content">
        <div class="detail-row"><span class="label">操作类型</span><el-tag :type="actionTagType(detailItem.action)">{{ actionLabel(detailItem.action) }}</el-tag></div>
        <div class="detail-row"><span class="label">操作时间</span><span>{{ formatTime(detailItem.created_at) }}</span></div>
        <div class="detail-row"><span class="label">房源 ID</span><el-link v-if="detailItem.resource_id" type="primary" :underline="false" @click="goProperty(detailItem.resource_id); detailVisible = false">#{{ detailItem.resource_id }}</el-link><span v-else>-</span></div>
        <div class="detail-row"><span class="label">操作人</span><span>#{{ detailItem.user_id ?? '-' }}</span></div>
        <div class="detail-row"><span class="label">IP 地址</span><span>{{ detailItem.ip_address || '-' }}</span></div>
        <div class="detail-row vertical">
          <span class="label">变更详情</span>
          <pre v-if="detailItem.details && Object.keys(detailItem.details).length > 0">{{ JSON.stringify(detailItem.details, null, 2) }}</pre>
          <span v-else class="empty">无</span>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Refresh, RefreshLeft } from '@element-plus/icons-vue'
import { propertyService, type PropertyHistoryItem } from '@/services/property'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()

const list = ref<PropertyHistoryItem[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)

const filter = reactive({
  action: '',
  resourceId: null as number | null,
  dateRange: null as [string, string] | null,
})

const detailVisible = ref(false)
const detailItem = ref<PropertyHistoryItem | null>(null)
const revertingId = ref<number | null>(null)
const deletingId = ref<number | null>(null)
const revertedLogIds = ref<Set<number>>(new Set())

// 批量操作
const batchMode = ref(false)
const selectedIds = ref<Set<number>>(new Set())
const batchDeleting = ref(false)
const clearing = ref(false)

function toggleBatchMode() {
  batchMode.value = !batchMode.value
  selectedIds.value = new Set()
}

function toggleSelect(id: number) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  selectedIds.value = new Set(selectedIds.value)
}

async function batchDelete() {
  if (selectedIds.value.size === 0) return
  batchDeleting.value = true
  try {
    const r = await propertyService.batchDeleteAuditLogs(Array.from(selectedIds.value))
    ElMessage.success(`已删除 ${r.deleted} 条记录`)
    selectedIds.value = new Set()
    batchMode.value = false
    await loadList()
  } catch { /* axios interceptor handles */ }
  finally { batchDeleting.value = false }
}

async function clearAll() {
  clearing.value = true
  try {
    const r = await propertyService.clearAuditLogs()
    ElMessage.success(`已清空 ${r.deleted} 条记录`)
    await loadList()
  } catch { /* axios interceptor handles */ }
  finally { clearing.value = false }
}

const revertableActions = new Set([
  'property_create', 'property_update', 'property_delete', 'property_restore',
])

function canRevert(row: PropertyHistoryItem): boolean {
  return revertableActions.has(row.action) && row.resource_id !== null && row.resource_id > 0
    && !revertedLogIds.value.has(row.id)
}

async function confirmRevert(row: PropertyHistoryItem) {
  if (!row.resource_id) return
  const actionName = actionLabelMap[row.action] || row.action
  try {
    await ElMessageBox.confirm(
      `确定要撤销此操作吗？将撤消"${actionName}"对房源 #${row.resource_id} 的影响。`,
      '确认撤销',
      { confirmButtonText: '确定撤销', cancelButtonText: '取消', type: 'warning' },
    )
  } catch { return }
  revertingId.value = row.id
  try {
    const result = await propertyService.revertAudit(row.resource_id, row.id)
    ElMessage.success(result.message || '撤销成功')
    await loadList()
  } catch (e: any) {
    // 错误信息由 axios 拦截器自动展示
  } finally {
    revertingId.value = null
  }
}

async function deleteLog(row: PropertyHistoryItem) {
  deletingId.value = row.id
  try {
    await propertyService.deleteAuditLog(row.id)
    ElMessage.success('已删除')
    await loadList()
  } catch (e: any) {
    // 错误信息由 axios 拦截器自动展示
  } finally {
    deletingId.value = null
  }
}

function onSearch() {
  page.value = 1
  loadList()
}
function onReset() {
  filter.action = ''
  filter.resourceId = null
  filter.dateRange = null
  page.value = 1
  loadList()
}
function onSizeChange(s: number) { pageSize.value = s; page.value = 1; loadList() }

async function loadList() {
  loading.value = true
  try {
    const params: any = { skip: (page.value - 1) * pageSize.value, limit: pageSize.value }
    if (filter.action) params.action = filter.action === 'batch' ? undefined : filter.action
    if (filter.resourceId) params.resource_id = filter.resourceId
    if (filter.dateRange) {
      params.start = filter.dateRange[0]
      params.end = filter.dateRange[1]
    }
    const data = await propertyService.getRecentAudit(pageSize.value)
    let arr = data
    // 客户端再过滤一下服务端未支持的 action 聚合
    if (filter.action === 'batch') arr = arr.filter(a => a.action.startsWith('property_batch'))
    else if (filter.action) arr = arr.filter(a => a.action === filter.action)
    if (filter.resourceId) arr = arr.filter(a => a.resource_id === filter.resourceId)
    if (filter.dateRange) {
      const [s, e] = filter.dateRange
      arr = arr.filter(a => a.created_at >= s && a.created_at <= e)
    }
    list.value = arr
    total.value = arr.length
    // 收集已被撤销的审计日志 ID
    const revoked = new Set<number>()
    for (const item of arr) {
      if (item.action === 'property_revert' && item.details?.reverted_audit_log_id) {
        revoked.add(item.details.reverted_audit_log_id)
      }
    }
    revertedLogIds.value = revoked
  } catch (e: any) {
    ElMessage.error('加载修改记录失败')
  } finally {
    loading.value = false
  }
}

function showDetail(row: PropertyHistoryItem) {
  detailItem.value = row
  detailVisible.value = true
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch { return iso }
}

const actionLabelMap: Record<string, string> = {
  property_create: '创建房源',
  property_update: '修改房源',
  property_delete: '删除房源',
  property_restore: '恢复房源',
  property_hard_delete: '硬删除',
  property_batch_status: '批量状态',
  property_batch_delete: '批量删除',
  property_batch_restore: '批量恢复',
  property_batch_hard_delete: '批量硬删除',
  property_moderate: '管理员审核',
  property_revert: '撤销操作',
}
function actionLabel(action: string): string {
  if (action.startsWith('property_batch')) return '批量操作'
  return actionLabelMap[action] || action
}
function actionTagType(action: string): 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  if (action.includes('hard_delete')) return 'danger'
  if (action.includes('delete')) return 'warning'
  if (action.includes('revert')) return 'warning'
  if (action.includes('restore')) return 'success'
  if (action.includes('update')) return 'primary'
  if (action.includes('create')) return 'success'
  if (action.includes('moderate')) return 'info'
  if (action.includes('batch')) return 'info'
  return 'info'
}
function detailsSummary(details: Record<string, any> | null): string {
  if (!details || Object.keys(details).length === 0) return '-'
  const parts: string[] = []
  for (const [k, v] of Object.entries(details).slice(0, 3)) {
    let s: string
    if (typeof v === 'string') s = v
    else if (Array.isArray(v)) s = `[${v.length}项]`
    else s = JSON.stringify(v)
    if (s.length > 30) s = s.slice(0, 30) + '…'
    parts.push(`${k}: ${s}`)
  }
  if (Object.keys(details).length > 3) parts.push('…')
  return parts.join('；')
}
function goProperty(id: number) {
  router.push('/property/' + id + '/edit')
}

onMounted(() => { loadList() })
</script>

<style scoped>
.history-page{max-width:1200px;margin:0 auto}
.page-header{margin-bottom:16px}
.page-header h2{font-size:24px;color:#303133;margin:0 0 4px}
.page-header .subtitle{color:#909399;font-size:14px;margin:0}
.filter-card{border-radius:8px;margin-bottom:16px}
.list-card{border-radius:8px}
.card-header{display:flex;justify-content:space-between;align-items:center}
.time-cell{font-size:13px;color:#606266}
.details-cell{color:#909399;font-size:13px}
.detail-content{padding:0 8px}
.detail-row{display:flex;align-items:center;gap:12px;margin-bottom:14px;font-size:14px}
.detail-row.vertical{flex-direction:column;align-items:flex-start;gap:6px}
.detail-row .label{width:80px;color:#909399;flex-shrink:0}
.detail-row pre{background:#f5f7fa;border:1px solid #ebeef5;border-radius:6px;padding:10px 12px;margin:0;font-size:12px;color:#606266;white-space:pre-wrap;word-break:break-all;max-height:300px;overflow-y:auto;width:100%;box-sizing:border-box}
.detail-row .empty{color:#c0c4cc}

/* 批量操作底栏 */
.batch-bar {
  position: fixed; bottom: 0; left: 200px; right: 0; z-index: 300;
  background: #fff; border-top: 2px solid #e6a23c;
  box-shadow: 0 -4px 20px rgba(0,0,0,.12);
}
.batch-bar-inner {
  max-width: 1200px; margin: 0 auto;
  display: flex; align-items: center; gap: 16px; padding: 14px 24px;
}
.batch-count { font-size: 15px; color: #303133; white-space: nowrap; }
.batch-count strong { color: #e6a23c; font-size: 18px; }
.batch-slide-enter-active, .batch-slide-leave-active { transition: transform .3s ease, opacity .3s ease; }
.batch-slide-enter-from, .batch-slide-leave-to { transform: translateY(100%); opacity: 0; }
</style>
