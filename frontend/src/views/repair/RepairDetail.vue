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
        <el-descriptions-item label="报修人">{{ repair.tenant_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="房东">{{ repair.landlord_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="维修师傅">{{ repair.worker_name || '待派单' }}</el-descriptions-item>
        <el-descriptions-item label="预约时间">{{ repair.scheduled_time || '未指定' }}</el-descriptions-item>
        <el-descriptions-item label="问题描述" :span="2">{{ repair.description }}</el-descriptions-item>
      </el-descriptions>

      <!-- 维修记录 -->
      <template v-if="repair.status === 'completed' && repair.work_record">
        <el-divider />
        <h4>📝 维修记录</h4>
        <el-alert type="success" :closable="false" show-icon>
          <template #title>{{ repair.work_record }}</template>
        </el-alert>
        <div style="margin-top:4px;color:var(--text-muted);font-size:13px">完成时间：{{ repair.completed_at || '-' }}</div>
      </template>

      <!-- 租客操作 -->
      <template v-if="isTenant && repair.status === 'pending'">
        <el-divider />
        <el-button type="danger" plain @click="handleCancel">取消报修</el-button>
      </template>
    </el-card>

    <el-empty v-if="!repair && !loading" description="工单不存在" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { repairService } from '@/services/repair'
import { useAuthStore } from '@/stores/auth'
import { ISSUE_TYPE_LABELS, REPAIR_STATUS_LABELS, REPAIR_STATUS_TAGS } from '@/types/repair'
import type { RepairRead } from '@/types/repair'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const repair = ref<RepairRead | null>(null)
const loading = ref(false)

const isTenant = computed(() => authStore.user?.role === 'tenant')

const tagsRecord = REPAIR_STATUS_TAGS as Record<string, string>
const labelsRecord = REPAIR_STATUS_LABELS as Record<string, string>
const issueRecord = ISSUE_TYPE_LABELS as Record<string, string>

function statusTag(s: string): string {
  return tagsRecord[s] || 'info'
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

onMounted(fetchDetail)
</script>

<style scoped>
.repair-detail { max-width: 800px; margin: 0 auto; }
.detail-card { border-radius: var(--radius); }
.repair-header { display: flex; justify-content: space-between; align-items: center; }
.repair-header h3 { margin: 0 0 4px 0; font-size: 20px; }
.repair-meta { font-size: 13px; color: var(--text-muted); }
</style>
