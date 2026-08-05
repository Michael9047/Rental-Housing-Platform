<template>
  <div class="repair-detail" v-loading="loading">
    <el-page-header @back="$router.back()" content="报修工单详情" style="margin-bottom:20px" />

    <el-card v-if="repair" shadow="never" class="detail-card">
      <!-- 状态 + 信息 -->
      <div class="repair-header">
        <div>
          <h3>工单 #{{ repair.id }}</h3>
          <span class="repair-meta">{{ repair.created_at ? formatDate(repair.created_at) : '' }} 提交</span>
        </div>
        <el-tag :type="statusTag(repair.status)" size="large" effect="dark">
          {{ labelsRecord[repair.status] }}
        </el-tag>
      </div>

      <el-divider />

      <!-- 基本信息 -->
      <el-descriptions :column="2" border>
        <el-descriptions-item label="房源">{{ repair.property_title || `房源#${repair.property_id}` }}</el-descriptions-item>
        <el-descriptions-item label="问题类型">
          <el-tag size="small">{{ issueRecord[repair.issue_type] }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="严重程度">
          <el-tag :type="sevTag(repair.severity)" size="small">{{ sevLabel(repair.severity) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="报修人">{{ repair.tenant_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="房东">{{ repair.landlord_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="公寓联系人">{{ repair.institute_contact || '未填写' }}</el-descriptions-item>
        <el-descriptions-item label="预约时间">{{ repair.scheduled_time || '未指定' }}</el-descriptions-item>
        <el-descriptions-item label="问题描述" :span="2">{{ repair.description }}</el-descriptions-item>
      </el-descriptions>

      <!-- 维修记录 -->
      <template v-if="repair.work_record">
        <el-divider />
        <h4>📝 维修记录</h4>
        <el-alert type="success" :closable="false" show-icon>
          <template #title>{{ repair.work_record }}</template>
        </el-alert>
        <div style="margin-top:4px;color:var(--text-muted);font-size:13px">完成时间：{{ repair.completed_at || '-' }}</div>
      </template>

      <!-- 维修照片 -->
      <template v-if="repair.work_images && repair.work_images.length">
        <el-divider />
        <h4>📸 维修照片</h4>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <el-image v-for="(img, idx) in repair.work_images" :key="idx" :src="img" :preview-src-list="repair.work_images" style="width:120px;height:120px;border-radius:8px" fit="cover" />
        </div>
      </template>

      <!-- 驳回原因 -->
      <template v-if="repair.reject_reason">
        <el-divider />
        <el-alert type="warning" :closable="false" show-icon title="租客驳回过此维修">
          <template #default>原因：{{ repair.reject_reason }}</template>
        </el-alert>
      </template>

      <!-- 租客操作 -->
      <template v-if="isTenant && repair.status === 'pending'">
        <el-divider />
        <el-button type="danger" plain @click="handleCancel">取消报修</el-button>
      </template>
      <template v-if="isTenant && repair.status === 'completed'">
        <el-divider />
        <div style="text-align:center">
          <p style="color:var(--text-muted);margin-bottom:12px">维修师傅已标记完成，请确认是否修好</p>
          <el-button type="success" size="large" :loading="confirmLoading" @click="handleConfirm">✅ 确认修好</el-button>
          <el-button type="danger" size="large" plain style="margin-left:12px" @click="showReject = true">❌ 驳回</el-button>
        </div>
      </template>
      <template v-if="repair.status === 'confirmed'">
        <el-divider />
        <el-alert type="success" :closable="false" show-icon title="✅ 已确认 — 工单已关闭" />
      </template>
      <template v-if="repair.status === 'in_progress' && repair.reject_reason">
        <el-divider />
        <el-alert type="warning" :closable="false" show-icon title="🔧 维修中（被驳回后重新处理）" />
      </template>
    </el-card>

    <!-- 驳回弹窗 -->
    <el-dialog v-model="showReject" title="驳回维修" width="420px">
      <p style="color:var(--text-muted);font-size:14px;margin-bottom:12px">请说明为什么认为维修不合格：</p>
      <el-input v-model="rejectReason" type="textarea" :rows="4" placeholder="例如：漏水没有完全修好，水龙头还是坏的" />
      <template #footer>
        <el-button @click="showReject = false">取消</el-button>
        <el-button type="danger" :loading="rejectLoading" @click="handleReject">确认驳回</el-button>
      </template>
    </el-dialog>

    <el-empty v-if="!repair && !loading" description="工单不存在" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { repairService } from '@/services/repair'
import { useAuthStore } from '@/stores/auth'
import { ISSUE_TYPE_LABELS, REPAIR_STATUS_LABELS, REPAIR_STATUS_TAGS, SEVERITY_LABELS, SEVERITY_TAGS } from '@/types/repair'
import type { RepairRead } from '@/types/repair'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const repair = ref<RepairRead | null>(null)
const loading = ref(false)
const confirmLoading = ref(false)
const rejectLoading = ref(false)
const showReject = ref(false)
const rejectReason = ref('')

const isTenant = computed(() => authStore.user?.role === 'tenant')

const tagsRecord = REPAIR_STATUS_TAGS as Record<string, string>
const labelsRecord = REPAIR_STATUS_LABELS as Record<string, string>
const issueRecord = ISSUE_TYPE_LABELS as Record<string, string>
const sevLabels = SEVERITY_LABELS as Record<string, string>
const sevTags = SEVERITY_TAGS as Record<string, string>

function statusTag(s: string): string {
  return tagsRecord[s] || 'info'
}

function sevLabel(s: string): string {
  return sevLabels[s] || s
}

function sevTag(s: string): string {
  return sevTags[s] || 'info'
}

function formatDate(d: string): string {
  return d ? new Date(d).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''
}

async function fetchDetail() {
  loading.value = true
  try {
    repair.value = await repairService.get(Number(route.params.id))
  } catch {
    repair.value = null
  } finally {
    loading.value = false
  }
}

async function handleCancel() {
  if (!repair.value) return
  try {
    await ElMessageBox.confirm('确定取消这个报修吗？', '取消报修', {
      confirmButtonText: '确定', cancelButtonText: '我再想想', type: 'warning',
    })
    await repairService.cancel(repair.value.id)
    ElMessage.success('报修已取消')
    router.push('/profile?tab=repairs')
  } catch { /* cancelled */ }
}

async function handleConfirm() {
  if (!repair.value) return
  confirmLoading.value = true
  try {
    await repairService.confirm(repair.value.id)
    ElMessage.success('已确认维修完成，工单已关闭')
    await fetchDetail()
  } catch { ElMessage.error('确认失败，请重试') }
  finally { confirmLoading.value = false }
}

async function handleReject() {
  if (!repair.value) return
  if (!rejectReason.value.trim()) { ElMessage.warning('请填写驳回原因'); return }
  rejectLoading.value = true
  try {
    await repairService.reject(repair.value.id, rejectReason.value.trim())
    ElMessage.success('已驳回，维修工将重新处理')
    showReject.value = false
    rejectReason.value = ''
    await fetchDetail()
  } catch { ElMessage.error('驳回失败，请重试') }
  finally { rejectLoading.value = false }
}

onMounted(fetchDetail)
</script>

<style scoped>
.repair-detail { max-width: 800px; margin: 0 auto; }
.detail-card { border-radius: var(--radius); }
.repair-header { display: flex; justify-content: space-between; align-items: center; }
.repair-header h3 { margin: 0 0 4px 0; font-size: 20px; }
.repair-meta { font-size: 13px; color: var(--text-muted); }
</style>
