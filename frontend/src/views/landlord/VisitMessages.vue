<template>
  <BmPageShell
    eyebrow="BM WORKSPACE"
    title="预约管理"
    description="集中处理租客从房源详情页提交的看房意向，优先跟进尚未处理的申请。"
  >
    <template #actions>
      <el-button :icon="Refresh" :loading="loading" @click="fetchMessages">刷新</el-button>
    </template>

    <template #summary>
      <BmSummaryStrip :items="summaryItems" :active-key="statusFilter" @select="selectStatus" />
    </template>

    <template #toolbar>
      <div class="filter-bar">
        <el-input v-model="keyword" :prefix-icon="Search" clearable placeholder="搜索手机号、公寓或留言" />
        <el-select v-model="selectedAptId" clearable placeholder="全部公寓">
          <el-option v-for="building in buildings" :key="building.id" :label="building.name" :value="building.id" />
        </el-select>
        <span class="filter-result">当前显示 {{ filteredMessages.length }} 条</span>
      </div>
    </template>

    <el-table :data="filteredMessages" v-loading="loading" stripe table-layout="fixed" empty-text="当前筛选条件下暂无预约申请" class="work-table">
      <el-table-column label="申请人" min-width="150">
        <template #default="{ row }">
          <div class="primary-cell"><strong>{{ row.guest_phone }}</strong><span>{{ formatTime(row.created_at) }}</span></div>
        </template>
      </el-table-column>
      <el-table-column prop="apartment_name" label="意向公寓" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.apartment_name || '公寓信息待补充' }}</template>
      </el-table-column>
      <el-table-column prop="guest_message" label="租客留言" min-width="260" show-overflow-tooltip>
        <template #default="{ row }">{{ row.guest_message || '未填写留言' }}</template>
      </el-table-column>
      <el-table-column label="处理状态" width="110" align="center">
        <template #default="{ row }">
          <BmStatusTag domain="visit" :status="row.is_read ? 'processed' : 'pending'" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="132" fixed="right">
        <template #default="{ row }">
          <el-button v-if="!row.is_read" link type="primary" @click="markRead(row.id)">标记已处理</el-button>
          <span v-else class="completed-text">已完成跟进</span>
        </template>
      </el-table-column>
    </el-table>
  </BmPageShell>
</template>

<script setup lang="ts">
// BM 看房预约工作台：将消息读取状态转换为明确的业务待办视图。
import { computed, onMounted, ref, watch } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import BmPageShell from '@/components/bm/BmPageShell.vue'
import BmSummaryStrip, { type BmSummaryItem } from '@/components/bm/BmSummaryStrip.vue'
import BmStatusTag from '@/components/bm/BmStatusTag.vue'
import api from '@/services/api'
import { buildingService, type Building } from '@/services/building'

interface VisitMessage { id:number; apartment_id:number; apartment_name?:string|null; guest_phone:string; guest_message?:string|null; is_read:boolean; created_at:string }

const buildings = ref<Building[]>([])
const selectedAptId = ref<number | null>(null)
const messages = ref<VisitMessage[]>([])
const loading = ref(false)
const keyword = ref('')
const statusFilter = ref<'all' | 'pending' | 'processed'>('pending')

const filteredMessages = computed(() => {
  const query = keyword.value.trim().toLowerCase()
  return messages.value.filter((message) => {
    if (selectedAptId.value && message.apartment_id !== selectedAptId.value) return false
    if (statusFilter.value === 'pending' && message.is_read) return false
    if (statusFilter.value === 'processed' && !message.is_read) return false
    if (!query) return true
    return [message.guest_phone, message.apartment_name, message.guest_message].some((value) => value?.toLowerCase().includes(query))
  })
})
const summaryItems = computed<BmSummaryItem[]>(() => [
  { key: 'pending', label: '待处理', value: messages.value.filter((item) => !item.is_read).length, note: '建议优先联系' },
  { key: 'processed', label: '已处理', value: messages.value.filter((item) => item.is_read).length, note: '已完成初次跟进' },
  { key: 'all', label: '全部申请', value: messages.value.length, note: '当前账号可见' },
])

function selectStatus(key:string) { statusFilter.value = key as typeof statusFilter.value }
function formatTime(value:string) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-' }
async function fetchBuildings() { try { buildings.value = await buildingService.list({ limit: 200 }) } catch { buildings.value = [] } }
async function fetchMessages() {
  loading.value = true
  try { const response = await api.get('/apartment/admin/getVisitMessageList'); messages.value = response.data || [] }
  catch { messages.value = []; ElMessage.error('预约申请加载失败，请稍后重试') }
  finally { loading.value = false }
}
async function markRead(id:number) {
  try { await api.put('/apartment/admin/markVisitMsgRead', null, { params: { messageId: id } }); ElMessage.success('已标记为处理完成'); await fetchMessages() }
  catch { ElMessage.error('状态更新失败，请重试') }
}
watch(selectedAptId, () => { keyword.value = '' })
onMounted(async () => { await Promise.all([fetchBuildings(), fetchMessages()]) })
</script>

<style scoped>
.filter-bar { display: grid; grid-template-columns: minmax(260px, 1fr) 240px auto; align-items: center; gap: 12px; }
.filter-result { color: var(--text-muted); font-size: 13px; white-space: nowrap; }
.work-table { width: 100%; overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius); }
.primary-cell { display: grid; gap: 4px; }
.primary-cell strong { color: var(--text-primary); font-size: 14px; }
.primary-cell span, .completed-text { color: var(--text-muted); font-size: 12px; }
@media (max-width: 720px) { .filter-bar { grid-template-columns: 1fr; } }
</style>
