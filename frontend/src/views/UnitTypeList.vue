<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>户型列表 — {{ buildingName }}</h2>
        <p class="sub">{{ buildingAddress }}</p>
      </div>
      <div style="display:flex;gap:8px">
        <el-button @click="$router.push('/buildings')">← 返回公寓管理</el-button>
        <el-button type="primary" @click="$router.push(`/unit-type/create?institute_id=${buildingId}`)">+ 新增户型</el-button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <el-card shadow="never" style="margin-bottom:16px">
      <el-row :gutter="12">
        <el-col :span="6">
          <el-input-number v-model="filters.rent_min" placeholder="最低租金" :min="0" controls-position="right" style="width:100%" />
        </el-col>
        <el-col :span="6">
          <el-input-number v-model="filters.rent_max" placeholder="最高租金" :min="0" controls-position="right" style="width:100%" />
        </el-col>
        <el-col :span="4">
          <el-input-number v-model="filters.area_min" placeholder="最小面积" :min="0" controls-position="right" style="width:100%" />
        </el-col>
        <el-col :span="4">
          <el-input-number v-model="filters.area_max" placeholder="最大面积" :min="0" controls-position="right" style="width:100%" />
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="fetchList">筛选</el-button>
          <el-button @click="clearFilters">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-table :data="filteredItems" v-loading="loading" stripe>
      <el-table-column prop="name" label="户型名称" min-width="140" />
      <el-table-column label="室/厅/卫" width="130">
        <template #default="{ row }">{{ row.bedrooms }}室{{ row.hall_count }}厅{{ row.bathrooms }}卫</template>
      </el-table-column>
      <el-table-column prop="area_sqm" label="面积(㎡)" width="90" />
      <el-table-column label="标准租金" width="110">
        <template #default="{ row }">¥{{ Number(row.base_rent).toLocaleString() }}/月</template>
      </el-table-column>
      <el-table-column prop="deposit_amount" label="押金" width="100">
        <template #default="{ row }">¥{{ row.deposit_amount ? Number(row.deposit_amount).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column prop="room_count" label="绑定房间" width="90" align="center" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="row.status==='available'?'success':(row.status==='rented'?'warning':'info')">
            {{ row.status==='available'?'可租':(row.status==='rented'?'已租':'维护') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/unit-type/${row.id}/edit`)">编辑</el-button>
          <el-button size="small" @click="$router.push(`/unit-type/${row.id}/copy`)">复制</el-button>
          <el-button size="small" type="primary" plain @click="$router.push(`/rooms/manage?unit_type_id=${row.id}`)">查看房间</el-button>
          <el-button size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !filteredItems.length" description="该公寓下暂无户型" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/services/api'

const route = useRoute()
const buildingId = Number(route.params.id)
const buildingName = ref('')
const buildingAddress = ref('')
const items = ref<any[]>([])
const loading = ref(false)

const filters = ref({ rent_min: undefined as number | undefined, rent_max: undefined as number | undefined, area_min: undefined as number | undefined, area_max: undefined as number | undefined })

const filteredItems = computed(() => {
  return items.value.filter(item => {
    const rent = Number(item.base_rent)
    const area = Number(item.area_sqm)
    if (filters.value.rent_min != null && rent < filters.value.rent_min) return false
    if (filters.value.rent_max != null && rent > filters.value.rent_max) return false
    if (filters.value.area_min != null && area < filters.value.area_min) return false
    if (filters.value.area_max != null && area > filters.value.area_max) return false
    return true
  })
})

function clearFilters() { filters.value = { rent_min: undefined, rent_max: undefined, area_min: undefined, area_max: undefined } }

onMounted(() => { fetchBuilding(); fetchList() })

async function fetchBuilding() {
  try { const r = await api.get('/buildings/' + buildingId); buildingName.value = r.data.name; buildingAddress.value = r.data.address || '' } catch { /* */ }
}

async function fetchList() {
  loading.value = true
  try {
    const r = await api.get('/unit-types', { params: { institute_id: buildingId, page_size: 500 } })
    items.value = r.data.items
  } catch { /* */ }
  finally { loading.value = false }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除户型「${row.name}」？其下所有房间也将被删除。`, '警告', { type: 'warning' })
    await api.delete('/unit-types/' + row.id)
    ElMessage.success('已删除')
    fetchList()
  } catch { /* cancelled */ }
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px }
h2 { font-size: 22px; color: #303133; margin: 0 }
.sub { color: #909399; font-size: 13px; margin: 4px 0 0 }
</style>
