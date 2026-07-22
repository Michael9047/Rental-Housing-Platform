<template>
  <div class="page-container">
    <div class="page-header">
      <h2>房间流转记录</h2>
      <el-button @click="$router.push('/rooms/manage')">← 返回房间管理</el-button>
    </div>

    <el-alert type="info" :closable="false" show-icon style="margin-bottom:16px">
      <template #title>房间 #{{ roomId }} 的历史流转记录（只读，不可删除）</template>
    </el-alert>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="from_status" label="原状态" width="100">
        <template #default="{ row }"><el-tag size="small" type="info">{{ row.from_status || '—' }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="to_status" label="新状态" width="100">
        <template #default="{ row }"><el-tag size="small">{{ row.to_status }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
      <el-table-column prop="operator_id" label="操作人ID" width="100" />
      <el-table-column prop="created_at" label="操作时间" width="180">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !items.length" description="暂无流转记录" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'

const route = useRoute()
const roomId = Number(route.params.id)
const items = ref<any[]>([])
const loading = ref(false)

onMounted(() => fetchList())

async function fetchList() {
  loading.value = true
  try { const r = await api.get(`/rooms/${roomId}/transfers`); items.value = r.data || [] } catch { /* */ }
  finally { loading.value = false }
}
</script>

<style scoped>
h2 { font-size: 22px; color: #303133; margin: 0 }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px }
</style>
