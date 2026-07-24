<template>
  <div class="escalated-repairs" v-loading="loading">
    <h2>📋 待派单工单</h2>
    <p class="subtitle">这些报修因房东无维修工而跳过房东，需由系统分配平台工人</p>

    <el-table :data="repairs" stripe>
      <el-table-column label="工单号" width="80"><template #default="{ row }">#{{ row.id }}</template></el-table-column>
      <el-table-column label="房源" min-width="140"><template #default="{ row }">{{ row.property_title || `#${row.property_id}` }}</template></el-table-column>
      <el-table-column label="租客" width="100"><template #default="{ row }">{{ row.tenant_name }}</template></el-table-column>
      <el-table-column label="房东" width="100"><template #default="{ row }">{{ row.landlord_name }}</template></el-table-column>
      <el-table-column label="问题" min-width="150">
        <template #default="{ row }">
          <el-tag size="small" type="warning" style="margin-right:4px">{{ issueLabel(row.issue_type) }}</el-tag>
          <span>{{ row.description?.slice(0, 20) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="报修时间" width="110"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="showAssign(row)">派单</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && repairs.length === 0" description="没有待派单的工单" />

    <!-- 派单弹窗 -->
    <el-dialog v-model="assignVisible" title="分配平台维修工" width="420px">
      <el-select v-model="selectedWorkerId" style="width:100%" placeholder="选择平台维修工">
        <el-option v-for="w in platformWorkers" :key="w.id" :label="`${w.username} (${(w.skills || []).join(', ') || '无技能'})`" :value="w.user_id" />
      </el-select>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="assignLoading" @click="doAssign">确认派单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { repairService, workerService } from '@/services/repair'
import { ISSUE_TYPE_LABELS } from '@/types/repair'
import type { RepairRead, RepairWorker } from '@/types/repair'

const repairs = ref<RepairRead[]>([])
const platformWorkers = ref<RepairWorker[]>([])
const loading = ref(false)
const assignVisible = ref(false)
const assignLoading = ref(false)
const currentRepair = ref<RepairRead | null>(null)
const selectedWorkerId = ref(0)

const issueRec = ISSUE_TYPE_LABELS as Record<string, string>
function issueLabel(t: string) { return issueRec[t] || t }
function formatDate(d: string) { return d ? new Date(d).toLocaleDateString('zh-CN') : '' }

async function fetchData() {
  loading.value = true
  try {
    repairs.value = await repairService.list({ status: 'pending_escalated', limit: 200 })
  } catch { repairs.value = [] }
  // 加载所有platform工人供选择
  try {
    const all = await workerService.list()
    platformWorkers.value = all.filter(w => w.scope === 'platform' && w.status === 'available')
  } catch { platformWorkers.value = [] }
  loading.value = false
}

function showAssign(row: RepairRead) {
  currentRepair.value = row
  selectedWorkerId.value = 0
  assignVisible.value = true
}

async function doAssign() {
  if (!currentRepair.value || !selectedWorkerId.value) { ElMessage.warning('请选择维修工'); return }
  assignLoading.value = true
  try {
    await repairService.assignWorker(currentRepair.value.id, selectedWorkerId.value)
    ElMessage.success('派单成功')
    assignVisible.value = false
    await fetchData()
  } catch { ElMessage.error('派单失败') }
  finally { assignLoading.value = false }
}

onMounted(fetchData)
</script>

<style scoped>
.escalated-repairs { max-width: 1100px; margin: 0 auto; }
.subtitle { color: var(--text-muted); font-size: 14px; margin-bottom: 16px; }
</style>
