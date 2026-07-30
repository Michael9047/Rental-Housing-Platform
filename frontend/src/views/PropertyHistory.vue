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
            <el-option label="创建房间" value="创建房间" />
            <el-option label="编辑房间" value="编辑房间" />
            <el-option label="删除房间" value="删除房间" />
            <el-option label="恢复房间" value="恢复房间" />
            <el-option label="创建户型" value="创建户型" />
            <el-option label="编辑户型" value="编辑户型" />
            <el-option label="删除户型" value="删除户型" />
            <el-option label="恢复户型" value="恢复户型" />
            <el-option label="创建公寓" value="创建公寓" />
            <el-option label="编辑公寓" value="编辑公寓" />
            <el-option label="删除公寓" value="删除公寓" />
            <el-option label="恢复公寓" value="恢复公寓" />
            <el-option label="硬删除房间" value="硬删除房间" />
            <el-option label="硬删除户型" value="硬删除户型" />
            <el-option label="硬删除公寓" value="硬删除公寓" />
            <el-option label="批量操作" value="batch" />
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
      size="540px"
    >
      <div v-if="detailItem" class="detail-content">

        <!-- 操作摘要卡片 -->
        <div class="summary-card">
          <span class="summary-icon">{{ summaryIcon }}</span>
          <span class="summary-text">{{ operationSummary }}</span>
        </div>

        <!-- 房源信息 -->
        <div class="section" v-if="detailItem.property_title || detailItem.property_address">
          <div class="section-title">🏠 房源信息</div>
          <div class="info-list">
            <div class="info-item" v-if="detailItem.property_title">
              <span class="label">名称</span>
              <span class="value">{{ detailItem.property_title }}</span>
            </div>
            <div class="info-item" v-if="detailItem.institute_name">
              <span class="label">公寓</span>
              <span class="value">{{ detailItem.institute_name }}</span>
            </div>
            <div class="info-item" v-if="detailItem.property_address">
              <span class="label">地址</span>
              <span class="value">{{ detailItem.property_address }}</span>
            </div>
            <div class="info-item" v-if="detailItem.resource_id">
              <span class="label">ID</span>
              <el-link class="value" type="primary" :underline="false" @click="goProperty(detailItem.resource_id); detailVisible = false">#{{ detailItem.resource_id }}</el-link>
            </div>
          </div>
        </div>

        <!-- 字段变更对比表（仅 property_update 且有 old_values/new_values） -->
        <div class="section" v-if="changedFields.length > 0">
          <div class="section-title">📝 字段变更（{{ changedCount }} 个字段变动）</div>
          <div class="diff-table">
            <div class="diff-header">
              <span class="diff-label-col">字段</span>
              <span class="diff-val-col">旧值</span>
              <span class="diff-arrow-col"></span>
              <span class="diff-val-col">新值</span>
            </div>
            <div
              v-for="f in visibleChangedFields"
              :key="f.field"
              class="diff-row"
              :class="{ 'diff-highlight': f.changed }"
            >
              <span class="diff-label-col">{{ f.label }}</span>
              <span class="diff-val-col old">{{ f.old }}</span>
              <span class="diff-arrow-col">→</span>
              <span class="diff-val-col new">{{ f.new }}</span>
            </div>
          </div>
          <el-button
            v-if="changedFields.length > visibleChangedFields.length"
            text size="small" type="primary" class="toggle-diff-btn"
            @click="showAllFields = !showAllFields"
          >
            {{ showAllFields ? '收起未变化字段' : `展开全部 ${changedFields.length} 个字段` }}
          </el-button>
        </div>

        <!-- 批量操作房源列表 -->
        <div class="section" v-if="batchProperties.length > 0">
          <div class="section-title">📋 涉及房源（{{ batchProperties.length }}）</div>
          <div class="batch-prop-list">
            <div v-for="bp in batchProperties" :key="bp.id" class="batch-prop-item">
              <span class="bp-id">#{{ bp.id }}</span>
              <span class="bp-title">{{ bp.title }}</span>
              <span class="bp-addr">{{ bp.institute_name ? bp.institute_name + ' · ' : '' }}{{ bp.address }}</span>
            </div>
          </div>
        </div>

        <!-- 撤销信息（property_revert） -->
        <div class="section" v-if="detailItem.action === 'property_revert' && detailItem.details">
          <div class="section-title">↩ 撤销详情</div>
          <div class="info-list">
            <div class="info-item">
              <span class="label">撤销操作</span>
              <span class="value">{{ actionLabel(detailItem.details.reverted_action || '') }}</span>
            </div>
            <div class="info-item">
              <span class="label">结果</span>
              <span class="value">{{ detailItem.details.message || '-' }}</span>
            </div>
          </div>
        </div>

        <!-- 操作记录元信息 -->
        <div class="section">
          <div class="section-title">⚙️ 操作记录</div>
          <div class="info-list">
            <div class="info-item">
              <span class="label">操作人</span>
              <span class="value">{{ operatorName }}</span>
            </div>
            <div class="info-item">
              <span class="label">时间</span>
              <span class="value">{{ formatTime(detailItem.created_at) }}</span>
            </div>
            <div class="info-item" v-if="detailItem.ip_address">
              <span class="label">IP</span>
              <span class="value">{{ detailItem.ip_address }}</span>
            </div>
          </div>
        </div>

        <!-- 原始 JSON（折叠） -->
        <el-collapse v-if="detailItem.details && Object.keys(detailItem.details).length > 0" class="raw-json-collapse">
          <el-collapse-item title="🔍 原始数据（JSON）">
            <pre class="raw-json">{{ JSON.stringify(detailItem.details, null, 2) }}</pre>
          </el-collapse-item>
        </el-collapse>

        <!-- 操作按钮 -->
        <div class="drawer-actions">
          <el-button
            v-if="detailItem.resource_id"
            @click="goProperty(detailItem.resource_id); detailVisible = false"
          >查看房源</el-button>
        </div>

      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Refresh, RefreshLeft } from '@element-plus/icons-vue'
import { propertyService, type PropertyHistoryItem } from '@/services/property'
import { buildingService } from '@/services/building'
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

// 批量操作的房源列表（从 details.properties 提取）
interface BatchProperty {
  id: number; title: string; address: string; institute_name: string | null
}
const batchProperties = computed<BatchProperty[]>(() => {
  if (!detailItem.value?.details?.properties) return []
  return detailItem.value.details.properties as BatchProperty[]
})

// ── 详情抽屉 computed ──

/** 摘要图标 */
const summaryIcon = computed(() => {
  const a = detailItem.value?.action || ''
  if (a.includes('创建')) return '➕'
  if (a.includes('编辑')) return '✏️'
  if (a.includes('硬删除')) return '💥'
  if (a.includes('删除')) return '🗑'
  if (a.includes('恢复') || a.includes('撤销')) return '♻️'
  if (a.includes('批量')) return '📋'
  if (a.includes('create')) return '➕'
  if (a.includes('update')) return '✏️'
  if (a.includes('delete')) return '🗑'
  if (a.includes('restore')) return '♻️'
  if (a.includes('revert')) return '↩'
  return '📌'
})

/** 自然语言操作摘要 */
const operationSummary = computed(() => {
  const item = detailItem.value
  if (!item) return ''
  const who = operatorName.value
  const when = formatTime(item.created_at)
  // 优先使用 details 里的大白话描述
  if (item.details?.描述) return `${who} 于 ${when} ${item.details.描述}`
  const name = item.property_title || item.details?.title || `#${item.resource_id || '?'}`
  const resType = item.resource_type || '房源'
  switch (item.action) {
    case '创建公寓': case '创建户型': case '创建房间': return `${who} 于 ${when} 创建了${resType}「${name}」`
    case '编辑公寓': case '编辑户型': case '编辑房间': {
      const desc = item.details?.描述 || ''
      return desc ? `${who} 于 ${when} ${desc}` : `${who} 于 ${when} 修改了${resType}「${name}」`
    }
    case '删除公寓': case '删除户型': case '删除房间': return `${who} 于 ${when} 删除了${resType}「${name}」`
    case '撤销删除': case '撤销编辑': return `${who} 于 ${when} 撤销了对${resType}「${name}」的操作`
    default: return `${who} 于 ${when} 执行了「${item.action}」操作，对象：${resType}「${name}」`
  }
})

/** 操作人显示名 */
const operatorName = computed(() => {
  const item = detailItem.value
  if (!item) return '-'
  const name = item.username || `#${item.user_id}`
  return item.username ? `${name}（#${item.user_id}）` : name
})

// ── 字段级变更对比 ──

/** 字段中文标签映射 */
const fieldLabelMap: Record<string, string> = {
  title: '房源标题',
  description: '描述',
  address: '地址',
  district: '区域',
  price_monthly: '月租（¥）',
  area_sqm: '面积（㎡）',
  bedrooms: '卧室数',
  bathrooms: '卫生间数',
  property_type: '户型',
  status: '状态',
  deposit_amount: '押金（¥）',
  service_fee_rate: '服务费比例',
  room_number: '房间号',
  floor: '楼层',
  min_stay_months: '最短租期（月）',
  amenities: '配套设施',
  available_from: '可租日期',
  deposit_type: '押金方式',
  institute_id: '所属公寓',
  latitude: '纬度',
  longitude: '经度',
  country: '国家',
  landlord_id: '房东',
}

const propertyTypeLabels: Record<string, string> = {
  studio: '单间', '1-bed': '一室', '2-bed': '两室+', shared: '合租', house: '别墅',
}
const depositTypeLabels: Record<string, string> = {
  one_month: '押一付一', one_three: '押一付三', two_month: '押二付一',
  three_month: '押三付一', half_month: '押半付一', free: '免押金', custom: '自定义',
}
const statusLabels: Record<string, string> = {
  available: '上架', pending_review: '待审核', rented: '已出租', maintenance: '维护中', offline: '已下线',
}

interface FieldChange { field: string; label: string; old: string; new: string; changed: boolean }
const showAllFields = ref(false)

const changedFields = computed<FieldChange[]>(() => {
  const item = detailItem.value
  if (!item) return []
  // 新格式：details.修改内容 = {field: {新值, 旧值}}
  const changes = item.details?.修改内容 || item.details?.changed_fields || {}
  if (typeof changes !== 'object' || Object.keys(changes).length === 0) return []
  const oldVals = item.details?.old_values as Record<string, any> | undefined
  const newVals = item.details?.new_values as Record<string, any> | undefined
  if (!oldVals || !newVals) return []

  const fields: FieldChange[] = []
  for (const key of Object.keys({ ...oldVals, ...newVals })) {
    const oldVal = oldVals[key]
    const newVal = newVals[key]
    const oldStr = formatFieldValue(key, oldVal)
    const newStr = formatFieldValue(key, newVal)
    fields.push({
      field: key,
      label: fieldLabelMap[key] || key,
      old: oldStr,
      new: newStr,
      changed: oldStr !== newStr,
    })
  }
  return fields
})

const changedCount = computed(() => changedFields.value.filter(f => f.changed).length)

/** 默认只展示有变化的字段；点击展开后显示全部 */
const visibleChangedFields = computed(() => {
  if (showAllFields.value) return changedFields.value
  return changedFields.value.filter(f => f.changed)
})

/** 公寓 ID → 名称 映射表 */
const buildingNameMap = ref<Record<number, string>>({})

async function loadBuildingNames() {
  try {
    const buildings = await buildingService.list({ limit: 200 })
    const map: Record<number, string> = {}
    for (const b of buildings) map[b.id] = b.name
    buildingNameMap.value = map
  } catch { /* 静默失败，回退显示数字 */ }
}

function formatFieldValue(key: string, val: any): string {
  if (val === null || val === undefined) return '（空）'
  if (key === 'institute_id') {
    const id = Number(val)
    if (!isNaN(id) && buildingNameMap.value[id]) return buildingNameMap.value[id]
    return String(val)
  }
  if (key === 'property_type') return propertyTypeLabels[String(val)] || String(val)
  if (key === 'status') return statusLabels[String(val)] || String(val)
  if (key === 'deposit_type') return depositTypeLabels[String(val)] || String(val)
  if (key === 'service_fee_rate' && typeof val === 'number') return `${(val * 100).toFixed(0)}%`
  if (key === 'amenities' && Array.isArray(val)) return val.join('、') || '（空）'
  return String(val)
}

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

// 撤销白名单：只允许撤销编辑和删除操作（创建不可撤销）
const revertableActions = new Set([
  '编辑房间', '删除房间',
  '编辑户型', '删除户型',
  '编辑公寓', '删除公寓',
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
      `确定要撤销此操作吗？将撤消"${actionName}"对 #${row.resource_id} 的影响。`,
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
    const msg = e?.response?.data?.detail || e?.message || '撤销失败，请稍后重试'
    ElMessage.error(typeof msg === 'string' ? msg : '撤销失败')
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
  showAllFields.value = false
  detailVisible.value = true
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch { return iso }
}

const actionLabelMap: Record<string, string> = {
  创建房间: '创建房间', 编辑房间: '编辑房间', 删除房间: '删除房间', 恢复房间: '恢复房间',
  创建户型: '创建户型', 编辑户型: '编辑户型', 删除户型: '删除户型', 恢复户型: '恢复户型',
  创建公寓: '创建公寓', 编辑公寓: '编辑公寓', 删除公寓: '删除公寓', 恢复公寓: '恢复公寓',
}
function actionLabel(action: string): string {
  if (actionLabelMap[action]) return actionLabelMap[action]
  if (action.includes('创建')) return action
  if (action.includes('编辑')) return action
  if (action.includes('删除')) return action
  if (action.includes('恢复')) return action
  if (action.includes('撤销')) return action
  if (action.startsWith('property_batch')) return '批量操作'
  return action
}
function actionTagType(action: string): 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  if (action.includes('硬删除')) return 'danger'
  if (action.includes('删除')) return 'danger'
  if (action.includes('编辑')) return 'primary'
  if (action.includes('创建')) return 'success'
  if (action.includes('恢复')) return 'success'
  if (action.includes('撤销')) return 'warning'
  if (action.includes('批量')) return 'info'
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

onMounted(() => { loadList(); loadBuildingNames() })
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
/* ── 抽屉内容 ── */
.detail-content{padding:0 4px;display:flex;flex-direction:column;gap:0}

/* 摘要卡片 */
.summary-card{display:flex;align-items:flex-start;gap:10px;background:linear-gradient(135deg,#ecf5ff,#f0f9ff);border:1px solid #d9ecff;border-radius:10px;padding:14px 16px;margin-bottom:16px}
.summary-icon{font-size:22px;flex-shrink:0;line-height:1.4}
.summary-text{font-size:14px;color:#303133;line-height:1.6}

/* 分区 */
.section{margin-bottom:18px}
.section-title{font-size:14px;font-weight:600;color:#303133;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #f0f0f0}

/* 信息列表 */
.info-list{display:flex;flex-direction:column;gap:8px}
.info-item{display:flex;align-items:flex-start;gap:12px;font-size:13px;line-height:1.5}
.info-item .label{color:#909399;min-width:56px;flex-shrink:0}
.info-item .value{color:#303133;word-break:break-all}

/* 字段变更对比表 */
.diff-table{border:1px solid #ebeef5;border-radius:8px;overflow:hidden;font-size:13px}
.diff-header{display:flex;align-items:center;background:#f5f7fa;padding:8px 12px;font-weight:600;color:#606266;font-size:12px}
.diff-row{display:flex;align-items:center;padding:7px 12px;border-top:1px solid #f2f3f5;transition:background .15s}
.diff-row.diff-highlight{background:#fdf6ec}
.diff-label-col{width:90px;flex-shrink:0;color:#606266;font-size:13px}
.diff-val-col{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px}
.diff-val-col.old{color:#909399;text-decoration:line-through}
.diff-val-col.new{color:#409eff;font-weight:500}
.diff-arrow-col{width:28px;text-align:center;color:#c0c4cc;flex-shrink:0;font-size:12px}
.toggle-diff-btn{margin-top:8px}

/* 批量操作房源列表 */
.batch-prop-list{width:100%;max-height:220px;overflow-y:auto;border:1px solid #ebeef5;border-radius:6px}
.batch-prop-item{display:flex;align-items:center;gap:10px;padding:7px 10px;border-bottom:1px solid #f2f3f5;font-size:13px}
.batch-prop-item:last-child{border-bottom:none}
.batch-prop-item .bp-id{color:#409eff;font-weight:500;min-width:36px}
.batch-prop-item .bp-title{color:#303133;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.batch-prop-item .bp-addr{color:#909399;font-size:12px;white-space:nowrap}

/* 原始 JSON 折叠面板 */
.raw-json-collapse{margin-top:4px}
.raw-json-collapse :deep(.el-collapse-item__header){font-size:13px;color:#909399;border:none;padding:6px 0}
.raw-json-collapse :deep(.el-collapse-item__wrap){border:none}
.raw-json{background:#f5f7fa;border:1px solid #ebeef5;border-radius:6px;padding:10px 12px;font-size:11px;color:#606266;white-space:pre-wrap;word-break:break-all;max-height:200px;overflow-y:auto;margin:0}

/* 操作按钮 */
.drawer-actions{display:flex;gap:10px;margin-top:20px;padding-top:16px;border-top:1px solid #ebeef5}

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

/* 批量操作房源列表 */
.batch-prop-list { width: 100%; max-height: 200px; overflow-y: auto; border: 1px solid #ebeef5; border-radius: 6px; }
.batch-prop-item { display: flex; align-items: center; gap: 10px; padding: 6px 10px; border-bottom: 1px solid #f2f3f5; font-size: 13px; }
.batch-prop-item:last-child { border-bottom: none; }
.batch-prop-item .bp-id { color: #409eff; font-weight: 500; min-width: 36px; }
.batch-prop-item .bp-title { color: #303133; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.batch-prop-item .bp-addr { color: #909399; font-size: 12px; white-space: nowrap; }
</style>
