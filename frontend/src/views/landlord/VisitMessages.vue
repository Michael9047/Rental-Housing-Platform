<template>
  <div class="page">
    <h2>📅 预约看房消息</h2>

    <!-- 选择公寓 -->
    <div style="margin-bottom:16px;display:flex;gap:12px;align-items:center">
      <span>选择公寓：</span>
      <el-select v-model="selectedAptId" placeholder="请选择公寓" @change="fetchMessages" style="width:280px">
        <el-option v-for="b in buildings" :key="b.id" :label="b.name" :value="b.id" />
      </el-select>
    </div>

    <!-- 消息列表 -->
    <el-table :data="messages" v-loading="loading" stripe empty-text="暂无预约看房消息">
      <el-table-column label="提交时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="guest_phone" label="手机号码" width="140" />
      <el-table-column prop="guest_message" label="留言" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_read ? 'info' : 'warning'" size="small">{{ row.is_read ? '已读' : '未读' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button v-if="!row.is_read" size="small" type="primary" @click="markRead(row.id)">标记已读</el-button>
          <span v-else style="color:#909399">-</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/services/api'
import { buildingService, type Building } from '@/services/building'

const buildings = ref<Building[]>([])
const selectedAptId = ref<number | null>(null)
const messages = ref<any[]>([])
const loading = ref(false)

function formatTime(t: string) {
  if (!t) return ''
  return new Date(t).toLocaleString('zh-CN')
}

onMounted(async () => {
  try { buildings.value = await buildingService.list({ limit: 200 }) }
  catch { buildings.value = [] }
})

async function fetchMessages() {
  if (!selectedAptId.value) { messages.value = []; return }
  loading.value = true
  try {
    const r = await api.get('/apartment/admin/getVisitMessageList', { params: { apartmentId: selectedAptId.value } })
    messages.value = r.data || []
  } catch { messages.value = [] }
  finally { loading.value = false }
}

async function markRead(id: number) {
  try {
    await api.put('/apartment/admin/markVisitMsgRead', null, { params: { messageId: id } })
    ElMessage.success('已标记为已读')
    fetchMessages()
  } catch { ElMessage.error('操作失败') }
}
</script>

<style scoped>
.page { max-width: 1100px; margin: 0 auto; padding: 24px }
h2 { margin: 0 0 20px; font-size: 22px; color: #303133 }
</style>
