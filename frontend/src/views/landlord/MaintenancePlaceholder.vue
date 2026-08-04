<template>
  <div class="page-container">
    <h2>🔧 维修工单</h2>

    <el-tabs v-model="activeTab" style="margin-top:16px">
      <!-- Tab 1: 工单管理 -->
      <el-tab-pane label="📋 工单管理" name="orders">
        <div v-loading="repairLoading">
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

          <el-table :data="filteredRepairs" stripe empty-text="暂无工单">
            <el-table-column label="工单号" width="80"><template #default="{ row }">#{{ row.id }}</template></el-table-column>
            <el-table-column label="房源" min-width="120"><template #default="{ row }">{{ row.property_title || `房源#${row.property_id}` }}</template></el-table-column>
            <el-table-column label="租客" width="90"><template #default="{ row }">{{ row.tenant_name || '-' }}</template></el-table-column>
            <el-table-column label="问题" min-width="140">
              <template #default="{ row }">
                <el-tag size="small" type="warning" style="margin-right:4px">{{ issueLabel(row.issue_type) }}</el-tag>
                <span>{{ row.description?.slice(0, 20) }}{{ row.description?.length > 20 ? '...' : '' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="师傅" width="100"><template #default="{ row }">{{ row.worker_name || '未派单' }}</template></el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }"><el-tag :type="tagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="$router.push(`/repairs/${row.id}`)">详情</el-button>
                <el-button v-if="row.status === 'pending'" size="small" text type="success" @click="approveRepair(row)">批准</el-button>
                <el-button v-if="row.status === 'pending'" size="small" text type="danger" @click="rejectRepair(row)">拒绝</el-button>
                <el-button v-if="row.status === 'pending' || row.status === 'pending_escalated'" size="small" text type="warning" @click="showAssign(row)">派单</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 派单弹窗 -->
          <el-dialog v-model="assignVisible" title="指派维修师傅" width="400px">
            <el-select v-model="selectedWorkerId" style="width:100%" placeholder="选择可调度的维修师傅">
              <el-option v-for="w in availableWorkers" :key="w.id" :label="`${w.username} (${w.skills?.join(', ') || '无技能'})`" :value="w.user_id" />
            </el-select>
            <template #footer>
              <el-button @click="assignVisible = false">取消</el-button>
              <el-button type="primary" :loading="assignLoading" @click="doAssign">确认派单</el-button>
            </template>
          </el-dialog>
        </div>
      </el-tab-pane>

      <!-- Tab 2: 维修师傅 -->
      <el-tab-pane label="👷 维修师傅" name="workers">
        <div v-loading="workerLoading">
          <div class="tab-toolbar">
            <el-button type="primary" size="small" @click="showCreate = true">➕ 新建维修师傅</el-button>
          </div>

          <el-table :data="workers" stripe empty-text="暂无维修师傅">
            <el-table-column label="姓名" width="100"><template #default="{ row }">{{ row.username }}</template></el-table-column>
            <el-table-column label="电话" width="130"><template #default="{ row }">{{ row.phone }}</template></el-table-column>
            <el-table-column label="归属" width="100">
              <template #default="{ row }">
                <el-tag :type="row.scope === 'platform' ? '' : 'info'" size="small" :style="row.scope === 'platform' ? 'background-color:#8b5cf6;border-color:#8b5cf6;color:#fff' : ''">{{ scopeLabel(row.scope) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="技能" min-width="130"><template #default="{ row }">{{ (row.skills || []).join('、') || '-' }}</template></el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="workerStatusTag(row.status)" size="small">{{ workerStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="完成" width="70"><template #default="{ row }">{{ row.total_jobs }}</template></el-table-column>
            <el-table-column label="评分" width="70"><template #default="{ row }">{{ row.rating.toFixed(1) }}</template></el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button v-if="row.status === 'available'" size="small" text type="warning" @click="setStatus(row, 'on_leave')">设为休假</el-button>
                <el-button v-if="row.status === 'on_leave'" size="small" text type="success" @click="setStatus(row, 'available')">恢复可调度</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 新建师傅弹窗 -->
          <el-dialog v-model="showCreate" title="新建维修师傅账号" width="420px">
            <el-form :model="createForm" label-width="70px">
              <el-form-item label="用户名"><el-input v-model="createForm.username" placeholder="登录用户名" /></el-form-item>
              <el-form-item label="密码"><el-input v-model="createForm.password" type="password" placeholder="至少8位" minlength="8" /></el-form-item>
              <el-form-item label="手机号"><el-input v-model="createForm.phone" placeholder="维修师傅手机号" /></el-form-item>
              <el-form-item v-if="authStore.isAdmin" label="归属范围">
                <el-select v-model="createForm.scope" style="width:100%" placeholder="选择归属范围">
                  <el-option label="网站管理（全局可见）" value="platform" />
                  <el-option label="公寓管理（仅你可见）" value="apartment" />
                </el-select>
              </el-form-item>
              <el-form-item label="技能"><el-input v-model="skillsStr" placeholder="用逗号分隔：水电,家电,门窗" /></el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="showCreate = false">取消</el-button>
              <el-button type="primary" :loading="createLoading" @click="doCreate">创建</el-button>
            </template>
          </el-dialog>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { repairService, workerService } from '@/services/repair'
import { useAuthStore } from '@/stores/auth'
import { ISSUE_TYPE_LABELS, REPAIR_STATUS_LABELS, REPAIR_STATUS_TAGS, WORKER_SCOPE_LABELS } from '@/types/repair'
import type { RepairRead, RepairWorker, WorkerScope } from '@/types/repair'

const authStore = useAuthStore()
const activeTab = ref('orders')

// ── 工单管理 ──
const repairs = ref<RepairRead[]>([])
const repairLoading = ref(false)
const statusFilter = ref('')
const assignVisible = ref(false)
const assignLoading = ref(false)
const currentRepair = ref<RepairRead | null>(null)
const selectedWorkerId = ref(0)

const filteredRepairs = computed(() => {
  if (!statusFilter.value) return repairs.value
  return repairs.value.filter(r => r.status === statusFilter.value)
})

const issueRec = ISSUE_TYPE_LABELS as Record<string, string>
const labels = REPAIR_STATUS_LABELS as Record<string, string>
const tagsRec = REPAIR_STATUS_TAGS as Record<string, string>
function issueLabel(t: string) { return issueRec[t] || t }
function statusLabel(s: string) { return labels[s] || s }
function tagType(s: string): string { return tagsRec[s] || 'info' }

async function fetchRepairs() {
  repairLoading.value = true
  try { repairs.value = await repairService.list({ limit: 200 }) } catch { repairs.value = [] }
  repairLoading.value = false
}

function showAssign(row: RepairRead) { currentRepair.value = row; selectedWorkerId.value = 0; assignVisible.value = true }

async function approveRepair(row: RepairRead) {
  try {
    await repairService.updateStatus(row.id, 'approved')
    ElMessage.success('工单已批准')
    fetchRepairs()
  } catch { ElMessage.error('操作失败') }
}

async function rejectRepair(row: RepairRead) {
  try {
    await repairService.updateStatus(row.id, 'rejected')
    ElMessage.success('工单已拒绝')
    fetchRepairs()
  } catch { ElMessage.error('操作失败') }
}

async function doAssign() {
  if (!currentRepair.value || !selectedWorkerId.value) { ElMessage.warning('请选择维修师傅'); return }
  assignLoading.value = true
  try {
    await repairService.assignWorker(currentRepair.value.id, selectedWorkerId.value)
    ElMessage.success('派单成功')
    assignVisible.value = false
    await fetchRepairs()
  } catch { ElMessage.error('派单失败') }
  finally { assignLoading.value = false }
}

// ── 维修师傅 ──
const workers = ref<RepairWorker[]>([])
const workerLoading = ref(false)
const showCreate = ref(false)
const createLoading = ref(false)
const createForm = ref({ username: '', password: '', phone: '', scope: 'apartment' as WorkerScope })
const skillsStr = ref('')

const STATUS_LABEL: Record<string, string> = { available: '可调度', working: '工作中', on_leave: '休假中' }
const STATUS_TAG: Record<string, string> = { available: 'success', working: '', on_leave: 'warning' }
function workerStatusLabel(s: string) { return STATUS_LABEL[s] || s }
function workerStatusTag(s: string) { return STATUS_TAG[s] || 'info' }
function scopeLabel(s: string) { return (WORKER_SCOPE_LABELS as Record<string, string>)[s] || s }

const availableWorkers = computed(() => workers.value.filter(w => w.status === 'available'))

async function fetchWorkers() {
  workerLoading.value = true
  try { workers.value = await workerService.list() } catch { workers.value = [] }
  workerLoading.value = false
}

async function setStatus(w: RepairWorker, status: string) {
  try {
    await workerService.updateStatus(w.id, { status: status as any })
    ElMessage.success(`已将 ${w.username} 设为${STATUS_LABEL[status]}`)
    await fetchWorkers()
  } catch { ElMessage.error('操作失败') }
}

async function doCreate() {
  if (!createForm.value.username || !createForm.value.password || !createForm.value.phone) {
    ElMessage.warning('请填写完整信息'); return
  }
  createLoading.value = true
  try {
    const skills = skillsStr.value ? skillsStr.value.split(',').map(s => s.trim()).filter(Boolean) : []
    await workerService.create({ ...createForm.value, skills })
    ElMessage.success('维修师傅账号已创建')
    showCreate.value = false
    createForm.value = { username: '', password: '', phone: '', scope: 'apartment' }
    skillsStr.value = ''
    await fetchWorkers()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (Array.isArray(detail)) {
      ElMessage.error(detail.map((d: any) => d.msg || '').filter(Boolean).join('；') || '创建失败')
    } else {
      ElMessage.error(typeof detail === 'string' ? detail : '创建失败')
    }
  } finally { createLoading.value = false }
}

onMounted(() => { fetchRepairs(); fetchWorkers() })
</script>

<style scoped>
.page-container { max-width: 1100px; margin: 0 auto; padding: 24px }
.tab-toolbar { margin-bottom: 16px; display: flex; gap: 10px; align-items: center }
</style>
