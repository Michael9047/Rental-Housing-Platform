<template>
  <div class="worker-orders" v-loading="loading">
    <h2>🔧 我的工单</h2>

    <div class="tab-toolbar">
      <el-radio-group v-model="statusFilter" size="small">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="assigned">待接收</el-radio-button>
        <el-radio-button value="in_progress">进行中</el-radio-button>
        <el-radio-button value="completed">已完成</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="filteredOrders" stripe>
      <el-table-column label="工单号" width="80"><template #default="{ row }">#{{ row.id }}</template></el-table-column>
      <el-table-column label="房源" min-width="140"><template #default="{ row }">{{ row.property_title || `#${row.property_id}` }}</template></el-table-column>
      <el-table-column label="租客" width="90"><template #default="{ row }">{{ row.tenant_name || '-' }}</template></el-table-column>
      <el-table-column label="问题描述" min-width="150">
        <template #default="{ row }">
          <el-tag size="small" type="warning" style="margin-right:4px">{{ issueLabel(row.issue_type) }}</el-tag>
          {{ row.description?.slice(0, 30) }}{{ row.description?.length > 30 ? '...' : '' }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }"><el-tag :type="tagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button v-if="row.status === 'assigned'" size="small" type="primary" @click="doStart(row)">开始工作</el-button>
          <el-button v-if="row.status === 'in_progress'" size="small" type="success" @click="showComplete(row)">完成工单</el-button>
          <el-button size="small" text type="primary" @click="$router.push(`/repairs/${row.id}`)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 完成工单弹窗 -->
    <el-dialog v-model="completeVisible" title="填写维修记录" width="420px">
      <el-form label-width="70px">
        <el-form-item label="维修记录">
          <el-input v-model="workRecord" type="textarea" :rows="4" placeholder="记录维修过程、更换了哪些配件等..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completeVisible = false">取消</el-button>
        <el-button type="primary" :loading="completeLoading" @click="doComplete">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { repairService } from '@/services/repair'
import { ISSUE_TYPE_LABELS, REPAIR_STATUS_LABELS, REPAIR_STATUS_TAGS } from '@/types/repair'
import type { RepairRead } from '@/types/repair'

const orders = ref<RepairRead[]>([])
const loading = ref(false)
const statusFilter = ref('')
const completeVisible = ref(false)
const completeLoading = ref(false)
const currentOrder = ref<RepairRead | null>(null)
const workRecord = ref('')

const labels = REPAIR_STATUS_LABELS as Record<string, string>
const tagsRec = REPAIR_STATUS_TAGS as Record<string, string>
const issueRec = ISSUE_TYPE_LABELS as Record<string, string>

const filteredOrders = computed(() => {
  if (!statusFilter.value) return orders.value
  return orders.value.filter(o => o.status === statusFilter.value)
})

function issueLabel(t: string) { return issueRec[t] || t }
function statusLabel(s: string) { return labels[s] || s }
function tagType(s: string): string { return tagsRec[s] || 'info' }

async function fetchData() {
  loading.value = true
  try { orders.value = await repairService.list({ limit: 200 }) } catch { orders.value = [] }
  loading.value = false
}

async function doStart(row: RepairRead) {
  try {
    await repairService.startWork(row.id)
    ElMessage.success('已标记为工作中')
    await fetchData()
  } catch { ElMessage.error('操作失败') }
}

function showComplete(row: RepairRead) {
  currentOrder.value = row
  workRecord.value = ''
  completeVisible.value = true
}

async function doComplete() {
  if (!currentOrder.value || !workRecord.value.trim()) {
    ElMessage.warning('请填写维修记录'); return
  }
  completeLoading.value = true
  try {
    await repairService.completeWork(currentOrder.value.id, workRecord.value.trim())
    ElMessage.success('工单已完成，你已恢复可调度状态')
    completeVisible.value = false
    await fetchData()
  } catch { ElMessage.error('操作失败') }
  finally { completeLoading.value = false }
}

onMounted(fetchData)
</script>

<style scoped>
.worker-orders { max-width: 1000px; margin: 0 auto; }
.tab-toolbar { margin-bottom: 16px; }
</style>
