<template>
  <div class="manage-page">
    <div class="page-header">
      <h2>房源管理</h2>
      <el-button type="primary" :icon="Plus" @click=".push('/property/create')">
        发布新房源
      </el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="properties" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="district" label="区域" width="100" />
        <el-table-column label="月租" width="120">
          <template #default="{ row }">
            <span style="color: #f56c6c; font-weight: 600">{{ row.price_monthly }}</span> 元
          </template>
        </el-table-column>
        <el-table-column label="户型" width="100">
          <template #default="{ row }">
            {{ row.bedrooms }}室{{ row.bathrooms }}卫
          </template>
        </el-table-column>
        <el-table-column prop="property_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ typeLabels[row.property_type] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTagType(row.status)">
              {{ statusLabels[row.status] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="editProperty(row.id)">
              编辑
            </el-button>
            <el-button size="small" text type="warning" @click="toggleStatus(row)">
              {{ row.status === 'offline' ? '上架' : '下架' }}
            </el-button>
            <el-popconfirm
              title="确定删除该房源吗？"
              confirm-button-text="删除"
              cancel-button-text="取消"
              @confirm="deleteProperty(row.id)"
            >
              <template #reference>
                <el-button size="small" text type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { usePropertyStore } from '@/stores/property'
import { storeToRefs } from 'pinia'
import type { Property, PropertyStatus, PropertyType } from '@/types/property'

const router = useRouter()
const propertyStore = usePropertyStore()
const { properties, loading } = storeToRefs(propertyStore)

const statusLabels: Record<PropertyStatus, string> = {
  available: '可租',
  rented: '已租',
  maintenance: '维护中',
  offline: '已下架',
}

const typeLabels: Record<PropertyType, string> = {
  apartment: '公寓',
  house: '别墅',
  studio: '单间',
  shared: '合租',
}

function statusTagType(status: PropertyStatus): string {
  const map: Record<PropertyStatus, string> = {
    available: 'success',
    rented: 'warning',
    maintenance: 'info',
    offline: 'danger',
  }
  return map[status]
}

function editProperty(id: number) {
  router.push(/property/)
}

async function toggleStatus(property: Property) {
  const newStatus: PropertyStatus = property.status === 'offline' ? 'available' : 'offline'
  try {
    await propertyStore.update(property.id, { status: newStatus })
    ElMessage.success(newStatus === 'offline' ? '已下架' : '已上架')
    propertyStore.fetchList()
  } catch {
    // handled by interceptor
  }
}

async function deleteProperty(id: number) {
  try {
    await propertyStore.remove(id)
    ElMessage.success('房源已删除')
  } catch {
    // handled by interceptor
  }
}

onMounted(() => {
  propertyStore.fetchList({ limit: 100 })
})
</script>

<style scoped>
.manage-page {
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 22px;
  color: #303133;
}
</style>
