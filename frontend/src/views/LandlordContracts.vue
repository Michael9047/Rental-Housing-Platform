<template>
  <BmPageShell
    eyebrow="BM WORKSPACE"
    title="合约管理"
    description="从房号确认到合同签署，在一个工作台跟踪每份合约的当前阶段。"
  >
    <template #actions>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      <el-button v-if="contractTemplateManagementEnabled" @click="$router.push('/contracts/templates')">合同模板</el-button>
    </template>

    <template #summary>
      <BmSummaryStrip :items="summaryItems" :active-key="activeStage" @select="selectStage" />
    </template>

    <template #toolbar>
      <div class="contract-toolbar">
        <el-input v-if="activeStage !== 'room'" v-model="keyword" :prefix-icon="Search" clearable placeholder="搜索合同编号、租客或户型" />
        <span class="toolbar-note">{{ stageDescription }}</span>
      </div>
    </template>

    <template v-if="activeStage === 'room'">
      <el-alert title="确认房号后会锁定房间，并自动生成合同发送给租客。操作前请核对租客和户型信息。" type="warning" :closable="false" show-icon />
      <el-table v-loading="loading" :data="displayedRoomQueue" stripe table-layout="fixed" empty-text="当前没有待确认房号的订单" class="work-table room-table">
        <el-table-column label="订单 / 租客" min-width="160">
          <template #default="{ row }"><div class="primary-cell"><strong>#{{ row.booking_id }} · {{ row.tenant_name }}</strong><span>{{ row.tenant_phone || '未填写电话' }}</span></div></template>
        </el-table-column>
        <el-table-column label="公寓 / 户型" min-width="190">
          <template #default="{ row }"><div class="primary-cell"><strong>{{ row.institute_name }}</strong><span>{{ row.unit_type_name || '未关联户型' }}</span></div></template>
        </el-table-column>
        <el-table-column label="确认房号" min-width="230">
          <template #default="{ row }"><el-input v-model="roomNumbers[row.booking_id]" placeholder="例如 1401" clearable /><div class="field-hint">首次确认即登记并锁定</div></template>
        </el-table-column>
        <el-table-column label="操作" width="176" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" :disabled="!isValidRoom(row)" :loading="confirmingBookingId === row.booking_id" @click="confirmRoom(row)">确认房号</el-button>
            <el-dropdown trigger="click" @command="cancelBooking(row)"><el-button text>更多</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="cancel" class="danger-item">取消订单</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
          </template>
        </el-table-column>
      </el-table>
    </template>

    <el-table v-else v-loading="loading" :data="filteredContracts" stripe table-layout="fixed" empty-text="当前阶段暂无合约" class="work-table">
      <el-table-column label="合同" min-width="180">
        <template #default="{ row }"><div class="primary-cell"><strong>{{ row.agreement_number || row.id }}</strong><span>{{ formatTime(row.generated_at) }} 生成</span></div></template>
      </el-table-column>
      <el-table-column prop="tenant_name" label="租客" min-width="140"><template #default="{ row }">{{ row.tenant_name || '未填写' }}</template></el-table-column>
      <el-table-column prop="unit_type_name" label="户型" min-width="160"><template #default="{ row }">{{ row.unit_type_name || '未关联户型' }}</template></el-table-column>
      <el-table-column label="当前状态" width="120" align="center"><template #default="{ row }"><BmStatusTag domain="contract" :status="row.status || ''" /></template></el-table-column>
      <el-table-column label="签署时间" min-width="170"><template #default="{ row }">{{ formatTime(row.signed_at) }}</template></el-table-column>
      <el-table-column label="操作" width="110" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="$router.push(`/my-contracts/${row.id}`)">查看合同</el-button></template></el-table-column>
    </el-table>

    <div v-if="activeStage !== 'room' && contractTotal > pageSize" class="pagination">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="contractTotal" layout="total, prev, pager, next" @current-change="loadContracts" />
    </div>
  </BmPageShell>
</template>

<script setup lang="ts">
// BM 合约工作台：统一承载房号确认队列与已生成合同的生命周期视图。
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import BmPageShell from '@/components/bm/BmPageShell.vue'
import BmSummaryStrip, { type BmSummaryItem } from '@/components/bm/BmSummaryStrip.vue'
import BmStatusTag from '@/components/bm/BmStatusTag.vue'
import api, { toUserFriendly } from '@/services/api'
import { contractTemplateManagementEnabled } from '@/config/features'

interface Room { id:string; room_number:string; floor:string|null; status:string; unit_type_id:number|null }
interface QueueItem { booking_id:number; tenant_name:string; tenant_phone:string|null; institute_name:string; unit_type_name:string|null; available_rooms:Room[] }
interface ContractItem { id:string; agreement_number:string|null; tenant_name:string|null; unit_type_name:string|null; status:string|null; signed_at:string|null; generated_at:string|null }

const loading = ref(false)
const route = useRoute()
const confirmingBookingId = ref<number|null>(null)
const roomQueue = ref<QueueItem[]>([])
const contracts = ref<ContractItem[]>([])
const contractStatusCounts = ref<Record<string,number>>({})
const roomNumbers = ref<Record<number,string>>({})
const activeStage = ref<'room'|'pending'|'signed'>('room')
const keyword = ref('')
const page = ref(1)
const pageSize = 20
const contractTotal = ref(0)
const targetOrderId = computed(() => Number(route.query.order_id) || null)
const displayedRoomQueue = computed(() => {
  if (!targetOrderId.value) return roomQueue.value
  return [...roomQueue.value].sort((left, right) =>
    Number(right.booking_id === targetOrderId.value) - Number(left.booking_id === targetOrderId.value))
})

const signedCount = computed(() => ['signed','active','effective'].reduce((total,status)=>total+(contractStatusCounts.value[status] || 0),0))
const pendingCount = computed(() => Object.entries(contractStatusCounts.value).reduce((total,[status,count])=>total+(isSigned(status) ? 0 : count),0))
const summaryItems = computed<BmSummaryItem[]>(() => [
  { key:'room', label:'待确认房号', value:roomQueue.value.length, note:'合同生成前' },
  { key:'pending', label:'待签署', value:pendingCount.value, note:'合同已生成' },
  { key:'signed', label:'已签署', value:signedCount.value, note:'签署流程完成' },
])
const stageDescription = computed(() => ({ room:'确认可交付房间，完成后自动进入合同签署。', pending:'跟踪已生成但尚未完成签署的合同。', signed:'查看已经完成签署的合同记录。' }[activeStage.value]))
const filteredContracts = computed(() => {
  const query = keyword.value.trim().toLowerCase()
  return contracts.value.filter((item) => {
    if (activeStage.value === 'pending' && isSigned(item.status)) return false
    if (activeStage.value === 'signed' && !isSigned(item.status)) return false
    return !query || [item.id, item.agreement_number, item.tenant_name, item.unit_type_name].some((value) => value?.toLowerCase().includes(query))
  })
})

function selectStage(key:string) { activeStage.value = key as typeof activeStage.value }
function isSigned(status:string|null) { return ['signed', 'active', 'effective'].includes(status || '') }
function formatTime(value:string|null) { return value ? new Date(value).toLocaleString('zh-CN', { hour12:false }) : '-' }
function isValidRoom(item:QueueItem) { return Boolean(roomNumbers.value[item.booking_id]?.trim()) }
async function loadRoomQueue() { const { data } = await api.get('/room-confirmations/pending'); roomQueue.value = data.items || [] }
async function loadContracts() { const { data } = await api.get('/contracts/landlord', { params:{ page:page.value, page_size:pageSize } }); contracts.value = data.items || []; contractTotal.value = data.total || 0; contractStatusCounts.value = data.status_counts || {} }
async function loadAll() {
  loading.value = true
  try { await Promise.all([loadRoomQueue(), loadContracts()]) }
  catch (error:unknown) { ElMessage.error(toUserFriendly(error) || '合约工作台加载失败，请重试') }
  finally { loading.value = false }
}
async function confirmRoom(item:QueueItem) {
  if (!isValidRoom(item)) return
  const roomNumber = roomNumbers.value[item.booking_id].trim(); confirmingBookingId.value = item.booking_id
  try { await api.post(`/room-confirmations/${item.booking_id}/confirm`, { room_number:roomNumber }); ElMessage.success(`房号 ${roomNumber} 已锁定，合同已生成`); delete roomNumbers.value[item.booking_id]; await loadAll() }
  catch (error:unknown) { ElMessage.error(toUserFriendly(error) || '房号确认失败，请稍后重试') }
  finally { confirmingBookingId.value = null }
}
async function cancelBooking(item:QueueItem) {
  try { await ElMessageBox.confirm(`确定取消订单 #${item.booking_id}？此操作会通知租客。`, '取消订单', { type:'warning', confirmButtonText:'确认取消' }); await api.post(`/room-confirmations/${item.booking_id}/cancel`); ElMessage.success('订单已取消'); await loadAll() }
  catch (error:unknown) { if (error !== 'cancel') ElMessage.error(toUserFriendly(error)) }
}
onMounted(loadAll)
</script>

<style scoped>
.contract-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.contract-toolbar .el-input { max-width: 360px; }
.toolbar-note { color: var(--text-muted); font-size: 13px; text-align: right; }
.work-table { width: 100%; overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius); }
.room-table { margin-top: 14px; }
.primary-cell { display: grid; gap: 4px; }
.primary-cell strong { color: var(--text-primary); }
.primary-cell span, .field-hint { color: var(--text-muted); font-size: 12px; }
.field-hint { margin-top: 5px; }
.pagination { display: flex; justify-content: flex-end; margin-top: 20px; }
:deep(.danger-item) { color: var(--danger); }
@media (max-width: 820px) { .contract-toolbar { grid-template-columns: 1fr; } .toolbar-note { text-align: left; } }
</style>
