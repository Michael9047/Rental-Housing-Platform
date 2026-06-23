<template>
  <div class="admin-embeddings" v-loading="loading">
    <h2>Embedding 管理</h2>

    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="总数" :value="stats.total" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="已完成" :value="stats.completed">
            <template #suffix><el-tag type="success" size="small">OK</el-tag></template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="失败" :value="stats.failed">
            <template #suffix>
              <el-tag v-if="stats.failed > 0" type="danger" size="small">!</el-tag>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="待处理" :value="stats.pending">
            <template #suffix>
              <el-tag v-if="stats.pending > 0" type="warning" size="small">...</el-tag>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <div class="actions">
      <el-button type="primary" :loading="reindexing" @click="handleReindexAll">
        <el-icon><Refresh /></el-icon> 重建全部索引
      </el-button>
      <el-input-number
        v-model="reindexPropId"
        placeholder="房源 ID"
        :min="1"
        controls-position="right"
        style="width: 160px; margin-left: 12px"
      />
      <el-button :loading="reindexing" @click="handleReindexOne">重建单个索引</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { adminService } from '@/services/admin'
import type { EmbeddingStats } from '@/types/admin'

const stats = ref<EmbeddingStats>({ total: 0, completed: 0, failed: 0, pending: 0 })
const loading = ref(false)
const reindexing = ref(false)
const reindexPropId = ref<number | null>(null)

async function fetchStats() {
  loading.value = true
  try {
    stats.value = await adminService.getEmbeddingStats()
  } finally {
    loading.value = false
  }
}

async function handleReindexAll() {
  reindexing.value = true
  try {
    await adminService.triggerReindex()
    ElMessage.success('全量重建已触发')
    setTimeout(fetchStats, 2000)
  } finally {
    reindexing.value = false
  }
}

async function handleReindexOne() {
  if (!reindexPropId.value) {
    ElMessage.warning('请输入房源 ID')
    return
  }
  reindexing.value = true
  try {
    await adminService.triggerReindex(reindexPropId.value)
    ElMessage.success(`房源 ${reindexPropId.value} 重建已触发`)
    setTimeout(fetchStats, 2000)
  } finally {
    reindexing.value = false
  }
}

onMounted(fetchStats)
</script>

<style scoped>
.admin-embeddings {
  max-width: 900px;
  margin: 0 auto;
}

.admin-embeddings h2 {
  font-size: 22px;
  color: #303133;
  margin-bottom: 24px;
}

.stats-row {
  margin-bottom: 24px;
}

.actions {
  display: flex;
  align-items: center;
}
</style>
