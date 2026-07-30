<template>
  <div class="worker-mgmt" v-loading="loading">
    <h2>👷 维修师傅管理</h2>
    <div class="tab-toolbar">
      <el-button type="primary" size="small" @click="showCreate = true">➕ 新建维修师傅</el-button>
    </div>

    <el-table :data="workers" stripe>
      <el-table-column label="姓名" width="100"><template #default="{ row }">{{ row.username }}</template></el-table-column>
      <el-table-column label="电话" width="130"><template #default="{ row }">{{ row.phone }}</template></el-table-column>
      <el-table-column label="归属" width="100">
        <template #default="{ row }">
          <el-tag :type="row.scope === 'platform' ? '' : 'info'" size="small" :style="row.scope === 'platform' ? 'background-color:#8b5cf6;border-color:#8b5cf6;color:#fff' : ''">{{ scopeLabel(row.scope) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="技能" min-width="150"><template #default="{ row }">{{ (row.skills || []).join('、') || '-' }}</template></el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="workerStatusTag(row.status)" size="small">{{ workerStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="完成工单" width="90"><template #default="{ row }">{{ row.total_jobs }}</template></el-table-column>
      <el-table-column label="评分" width="70"><template #default="{ row }">{{ row.rating.toFixed(1) }}</template></el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button v-if="row.status === 'available'" size="small" text type="warning" @click="setStatus(row, 'on_leave')">设为休假</el-button>
          <el-button v-if="row.status === 'on_leave'" size="small" text type="success" @click="setStatus(row, 'available')">恢复可调度</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建弹窗 -->
    <el-dialog v-model="showCreate" title="新建维修师傅账号" width="420px">
      <el-form :model="createForm" label-width="70px">
        <el-form-item label="用户名"><el-input v-model="createForm.username" placeholder="登录用户名" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="createForm.password" type="password" placeholder="至少6位" /></el-form-item>
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
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { workerService } from '@/services/repair'
import { useAuthStore } from '@/stores/auth'
import { WORKER_SCOPE_LABELS } from '@/types/repair'
import type { RepairWorker, WorkerScope } from '@/types/repair'

const authStore = useAuthStore()
const workers = ref<RepairWorker[]>([])
const loading = ref(false)
const showCreate = ref(false)
const createLoading = ref(false)
const createForm = ref({ username: '', password: '', phone: '', scope: 'apartment' as WorkerScope })
const skillsStr = ref('')

const STATUS_LABEL: Record<string, string> = { available: '可调度', working: '工作中', on_leave: '休假中' }
const STATUS_TAG: Record<string, string> = { available: 'success', working: '', on_leave: 'warning' }

function workerStatusLabel(s: string) { return STATUS_LABEL[s] || s }
function workerStatusTag(s: string) { return STATUS_TAG[s] || 'info' }
function scopeLabel(s: string) { return (WORKER_SCOPE_LABELS as Record<string, string>)[s] || s }

async function fetchData() {
  loading.value = true
  try { workers.value = await workerService.list() } catch { workers.value = [] }
  loading.value = false
}

async function setStatus(w: RepairWorker, status: string) {
  try {
    await workerService.updateStatus(w.id, { status: status as any })
    ElMessage.success(`已将 ${w.username} 设为${STATUS_LABEL[status]}`)
    await fetchData()
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
    await fetchData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  } finally {
    createLoading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.worker-mgmt { max-width: 1000px; margin: 0 auto; }
.tab-toolbar { margin-bottom: 16px; display: flex; gap: 10px; }
</style>
