<template>
  <div class="repair-mgmt" v-loading="loading">
    <h2>🔧 报修工单管理</h2>
    <div class="tab-toolbar">
      <el-radio-group v-model="statusFilter" size="small">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="pending">待处理</el-radio-button>
        <el-radio-button value="assigned">已派单</el-radio-button>
        <el-radio-button value="in_progress">维修中</el-radio-button>
        <el-radio-button value="completed">已完成</el-radio-button>
        <el-radio-button v-if="authStore.isAdmin" value="pending_escalated">待派单</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="filteredRepairs" stripe>
      <el-table-column label="工单号" width="80"><template #default="{ row }">#{{ row.id }}</template></el-table-column>
      <el-table-column label="房源" min-width="140"><template #default="{ row }">{{ row.property_title || `房源#${row.property_id}` }}</template></el-table-column>
      <el-table-column label="租客" width="90"><template #default="{ row }">{{ row.tenant_name || '-' }}</template></el-table-column>
      <el-table-column label="问题" min-width="150">
        <template #default="{ row }">
          <el-tag size="small" type="warning" style="margin-right:4px">{{ issueLabel(row.issue_type) }}</el-tag>
          <span>{{ row.description?.slice(0, 20) }}{{ row.description?.length > 20 ? '...' : '' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="维修师傅" width="100"><template #default="{ row }">{{ row.worker_name || '未派单' }}</template></el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }"><el-tag :type="tagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="$router.push(`/repairs/${row.id}`)">详情</el-button>
          <el-button v-if="row.status === 'pending' || row.status === 'pending_escalated'" size="small" text type="warning" @click="showAssign(row)">派单</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 派单弹窗 -->
    <el-dialog v-model="assignVisible" title="指派维修师傅" width="400px">
      <el-select v-model="selectedWorkerId" style="width:100%" placeholder="选择可调度的维修师傅">
        <el-option v-for="w in availableWorkers" :key="w.id" :label="`${w.username} (${w.skills?.join(', ') || '无技能标签'})`" :value="w.user_id" />
      </el-select>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="assignLoading" @click="doAssign">确认派单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { repairService, workerService } from '@/services/repair'
import { useAuthStore } from '@/stores/auth'
import { ISSUE_TYPE_LABELS, REPAIR_STATUS_LABELS, REPAIR_STATUS_TAGS } from '@/types/repair'
import type { RepairRead, RepairWorker } from '@/types/repair'

const authStore = useAuthStore()
const repairs = ref<RepairRead[]>([])
const workers = ref<RepairWorker[]>([])
const loading = ref(false)
const statusFilter = ref('')
const assignVisible = ref(false)
const assignLoading = ref(false)
const currentRepair = ref<RepairRead | null>(null)
const selectedWorkerId = ref(0)

const labels = REPAIR_STATUS_LABELS as Record<string, string>
const tagsRec = REPAIR_STATUS_TAGS as Record<string, string>
const issueRec = ISSUE_TYPE_LABELS as Record<string, string>

const filteredRepairs = computed(() => {
  if (!statusFilter.value) return repairs.value
  return repairs.value.filter(r => r.status === statusFilter.value)
})

const availableWorkers = computed(() =>
  workers.value.filter(w => w.status === 'available')
)

function issueLabel(t: string) { return issueRec[t] || t }
function statusLabel(s: string) { return labels[s] || s }
function tagType(s: string): string { return tagsRec[s] || 'info' }

async function fetchData() {
  loading.value = true
  try { repairs.value = await repairService.list({ limit: 200 }) } catch { repairs.value = [] }
  try { workers.value = await workerService.list() } catch { workers.value = [] }
  loading.value = false
}

function showAssign(row: RepairRead) {
  currentRepair.value = row
  selectedWorkerId.value = 0
  assignVisible.value = true
}

async function doAssign() {
  if (!currentRepair.value || !selectedWorkerId.value) {
    ElMessage.warning('请选择维修师傅'); return
  }
  assignLoading.value = true
  try {
    await repairService.assignWorker(currentRepair.value.id, selectedWorkerId.value)
    ElMessage.success('派单成功，已通知维修师傅')
    assignVisible.value = false
    await fetchData()
  } catch { ElMessage.error('派单失败') }
  finally { assignLoading.value = false }
}

onMounted(fetchData)
</script>

<style scoped>
.repair-mgmt { max-width: 1100px; margin: 0 auto; }
.tab-toolbar { margin-bottom: 16px; }
</style>
