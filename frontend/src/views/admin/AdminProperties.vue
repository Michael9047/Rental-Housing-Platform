<template>
  <div class="admin-properties" v-loading="loading">
    <h2>房源审核</h2>

    <el-input
      v-model="search"
      placeholder="搜索房源标题..."
      clearable
      class="search-box"
      @input="fetchProperties"
    />

    <el-table :data="filteredProperties" stripe style="width: 100%; margin-top: 16px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column prop="district" label="区域" width="100" />
      <el-table-column prop="price_monthly" label="月租" width="100">
        <template #default="{ row }">{{ row.price_monthly }} 元</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-select
            :model-value="row.status"
            size="small"
            @change="(val: string) => handleStatusChange(row.id, val)"
          >
            <el-option label="可租" value="available" />
            <el-option label="已租" value="rented" />
            <el-option label="维护中" value="maintenance" />
            <el-option label="下架" value="offline" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="发布时间" width="120">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { adminService } from '@/services/admin'
import { propertyService } from '@/services/property'
import type { Property } from '@/types/property'

const properties = ref<Property[]>([])
const loading = ref(false)
const search = ref('')

const filteredProperties = computed(() => {
  if (!search.value) return properties.value
  const q = search.value.toLowerCase()
  return properties.value.filter(
    (p) => p.title.toLowerCase().includes(q) || p.district.toLowerCase().includes(q)
  )
})

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

async function fetchProperties() {
  loading.value = true
  try {
    properties.value = await propertyService.list({ limit: 100 })
  } finally {
    loading.value = false
  }
}

async function handleStatusChange(propertyId: number, status: string) {
  try {
    await adminService.moderateProperty(propertyId, status)
    ElMessage.success('状态已更新')
    await fetchProperties()
  } catch {
    ElMessage.error('更新失败')
  }
}

onMounted(fetchProperties)
</script>

<style scoped>
.admin-properties {
  max-width: 1100px;
  margin: 0 auto;
}

.admin-properties h2 {
  font-size: 22px;
  color: #303133;
  margin-bottom: 16px;
}

.search-box {
  max-width: 400px;
}
</style>
