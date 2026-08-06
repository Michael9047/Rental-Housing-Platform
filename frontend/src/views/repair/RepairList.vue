<template>
  <div class="repair-list-page">
    <div class="page-toolbar">
      <div class="toolbar-left">
        <h2>报修工单</h2>
        <span class="toolbar-sub" v-if="repairs.length">共 {{ repairs.length }} 条记录</span>
      </div>
      <el-button type="primary" @click="showNewRepair = true" :icon="Plus">我要报修</el-button>
    </div>

    <el-empty v-if="!loading && repairs.length === 0" description="没有报修记录，一切正常 👍" />
    <el-table v-else :data="repairs" stripe v-loading="loading" class="repair-table">
      <el-table-column label="房源" min-width="140">
        <template #default="{ row }">{{ row.property_title || `房源#${row.property_id}` }}</template>
      </el-table-column>
      <el-table-column label="问题类型" width="110">
        <template #default="{ row }">
          <el-tag size="small" type="warning">{{ issueTypeLabel(row.issue_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="描述" min-width="160">
        <template #default="{ row }">{{ row.description?.slice(0, 30) }}{{ row.description?.length > 30 ? '...' : '' }}</template>
      </el-table-column>
      <el-table-column label="提交时间" width="110">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="repairTag(row.status)" size="small">{{ repairStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="router.push(`/repairs/${row.id}`)">查看详情</el-button>
          <el-button v-if="row.status === 'pending'" size="small" text type="danger" @click="cancelRepair(row)">取消</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建报修弹窗 -->
    <el-dialog v-model="showNewRepair" title="我要报修" width="460px">
      <el-form label-width="80px">
        <el-form-item label="房源">
          <el-select v-model="repairForm.property_id" style="width:100%" placeholder="选择需要维修的房源">
            <el-option v-for="b in bookings" :key="b.id" :label="`房源 #${b.property_id}`" :value="b.property_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="问题类型">
          <el-select v-model="repairForm.issue_type" style="width:100%" placeholder="选择问题类型">
            <el-option v-for="(label, key) in ISSUE_TYPE_LABELS" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="问题描述">
          <el-input v-model="repairForm.description" type="textarea" :rows="3" placeholder="简单描述一下哪里出了问题..." />
        </el-form-item>
        <el-form-item label="预约时间">
          <el-input v-model="repairForm.scheduled_time" placeholder="例如：8月10日 上午（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNewRepair = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRepair">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { repairService } from '@/services/repair'
import { bookingService } from '@/services/booking'
import type { Booking } from '@/types/booking'
import type { RepairRead, RepairIssueType } from '@/types/repair'
import { ISSUE_TYPE_LABELS, REPAIR_STATUS_LABELS, REPAIR_STATUS_TAGS } from '@/types/repair'

const router = useRouter()

const loading = ref(false)
const repairs = ref<RepairRead[]>([])
const bookings = ref<Booking[]>([])
const showNewRepair = ref(false)
const submitting = ref(false)
const repairForm = ref({
  property_id: 0,
  issue_type: 'other' as RepairIssueType,
  description: '',
  scheduled_time: '',
})

const repairTag = (s: string) => ((REPAIR_STATUS_TAGS as Record<string, string>)[s] || 'info') as 'danger' | 'warning' | 'success' | 'info' | ''
const issueTypeLabel = (t: string) => (ISSUE_TYPE_LABELS as Record<string, string>)[t] || t
const repairStatusLabel = (s: string) => ((REPAIR_STATUS_LABELS as Record<string, string>)[s] || s)

function formatDate(d: string): string {
  return d ? new Date(d).toLocaleDateString('zh-CN') : ''
}

async function fetchRepairs() {
  loading.value = true
  try {
    repairs.value = await repairService.list()
  } catch {
    repairs.value = []
  } finally {
    loading.value = false
  }
}

async function fetchBookings() {
  try {
    bookings.value = await bookingService.list()
  } catch {
    bookings.value = []
  }
}

async function submitRepair() {
  if (!repairForm.value.property_id) { ElMessage.warning('请选择房源'); return }
  if (!repairForm.value.description.trim()) { ElMessage.warning('请描述问题'); return }
  submitting.value = true
  try {
    await repairService.create({
      property_id: repairForm.value.property_id,
      issue_type: repairForm.value.issue_type,
      description: repairForm.value.description,
      scheduled_time: repairForm.value.scheduled_time || undefined,
    })
    ElMessage.success('报修已提交，房东会尽快处理')
    showNewRepair.value = false
    repairForm.value = { property_id: 0, issue_type: 'other', description: '', scheduled_time: '' }
    await fetchRepairs()
  } catch {
    ElMessage.error('提交失败，请重试')
  } finally {
    submitting.value = false
  }
}

async function cancelRepair(row: RepairRead) {
  try {
    await ElMessageBox.confirm('确定取消这个报修吗？', '取消报修', { confirmButtonText: '确定', cancelButtonText: '我再想想', type: 'warning' })
    await repairService.cancel(row.id)
    ElMessage.success('报修已取消')
    await fetchRepairs()
  } catch { /* cancelled */ }
}

onMounted(() => {
  fetchRepairs()
  fetchBookings()
})
</script>

<style scoped>
.repair-list-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 28px 0 40px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.toolbar-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.toolbar-left h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.toolbar-sub {
  font-size: 13px;
  color: var(--text-muted);
}

.repair-table {
  background: var(--bg-white);
  border-radius: var(--radius);
  border: 1px solid var(--border);
}
</style>
