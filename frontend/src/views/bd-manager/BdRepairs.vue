<template>
  <div class="bd-repairs" v-loading="loading">
    <h2>🔧 报修管理</h2>

    <div class="tab-toolbar">
      <el-radio-group v-model="statusFilter" size="small">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="pending">待处理</el-radio-button>
        <el-radio-button value="in_progress">处理中</el-radio-button>
        <el-radio-button value="completed">待确认</el-radio-button>
        <el-radio-button value="confirmed">已确认</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="filteredRepairs" stripe>
      <el-table-column label="工单号" width="80"><template #default="{ row }">#{{ row.id }}</template></el-table-column>
      <el-table-column label="房源" min-width="130"><template #default="{ row }">{{ row.property_title || `#${row.property_id}` }}</template></el-table-column>
      <el-table-column label="租客" width="90"><template #default="{ row }">{{ row.tenant_name || '-' }}</template></el-table-column>
      <el-table-column label="严重程度" width="90">
        <template #default="{ row }"><el-tag :type="sevTag(row.severity)" size="small">{{ sevLabel(row.severity) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="问题" min-width="140">
        <template #default="{ row }">
          <el-tag size="small" type="warning" style="margin-right:4px">{{ issueLabel(row.issue_type) }}</el-tag>
          <span>{{ row.description?.slice(0, 20) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="公寓联系人" width="120"><template #default="{ row }">{{ row.institute_contact || '-' }}</template></el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }"><el-tag :type="tagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending'" size="small" type="primary" @click="doStart(row)">开始处理</el-button>
          <el-button v-if="row.status === 'in_progress'" size="small" type="success" @click="showComplete(row)">标记完成</el-button>
          <el-button size="small" text type="primary" @click="$router.push(`/repairs/${row.id}`)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && repairs.length === 0" description="暂无报修工单" />

    <!-- 标记完成弹窗 -->
    <el-dialog v-model="completeVisible" title="填写处理记录" width="480px">
      <el-form label-width="70px">
        <el-form-item label="处理记录">
          <el-input v-model="workRecord" type="textarea" :rows="4" placeholder="记录处理过程、维修结果..." />
        </el-form-item>
        <el-form-item label="处理照片">
          <ImageUploader v-model="workImages" :max-files="6" title="📸 上传处理完成照片" hint="可上传维修完成后的画面" />
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
import { ISSUE_TYPE_LABELS, REPAIR_STATUS_LABELS, REPAIR_STATUS_TAGS, SEVERITY_LABELS, SEVERITY_TAGS } from '@/types/repair'
import type { RepairRead } from '@/types/repair'
import ImageUploader from '@/components/ImageUploader.vue'

const repairs = ref<RepairRead[]>([])
const loading = ref(false)
const statusFilter = ref('')
const completeVisible = ref(false)
const completeLoading = ref(false)
const currentOrder = ref<RepairRead | null>(null)
const workRecord = ref('')
const workImages = ref<string[]>([])

const labels = REPAIR_STATUS_LABELS as Record<string, string>
const tagsRec = REPAIR_STATUS_TAGS as Record<string, string>
const issueRec = ISSUE_TYPE_LABELS as Record<string, string>
const sevLabels = SEVERITY_LABELS as Record<string, string>
const sevTags = SEVERITY_TAGS as Record<string, string>

const filteredRepairs = computed(() => {
  if (!statusFilter.value) return repairs.value
  return repairs.value.filter(r => r.status === statusFilter.value)
})

function issueLabel(t: string) { return issueRec[t] || t }
function statusLabel(s: string) { return labels[s] || s }
function tagType(s: string): string { return tagsRec[s] || 'info' }
function sevLabel(s: string) { return sevLabels[s] || s }
function sevTag(s: string) { return sevTags[s] || 'info' }

async function fetchData() {
  loading.value = true
  try { repairs.value = await repairService.list({ limit: 200 }) } catch { repairs.value = [] }
  loading.value = false
}

async function doStart(row: RepairRead) {
  try {
    await repairService.startWork(row.id)
    ElMessage.success('已标记为处理中')
    await fetchData()
  } catch { ElMessage.error('操作失败') }
}

function showComplete(row: RepairRead) {
  currentOrder.value = row
  workRecord.value = ''
  workImages.value = []
  completeVisible.value = true
}

async function doComplete() {
  if (!currentOrder.value || !workRecord.value.trim()) {
    ElMessage.warning('请填写处理记录'); return
  }
  completeLoading.value = true
  try {
    await repairService.completeWork(currentOrder.value.id, workRecord.value.trim(), workImages.value)
    ElMessage.success('已标记完成，等待租客确认')
    completeVisible.value = false
    await fetchData()
  } catch { ElMessage.error('操作失败') }
  finally { completeLoading.value = false }
}

onMounted(fetchData)
</script>

<style scoped>
.bd-repairs { max-width: 1100px; margin: 0 auto; }
.tab-toolbar { margin-bottom: 16px; }
</style>
