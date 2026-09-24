<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>户型列表 — {{ buildingName }}</h2>
        <p class="sub">{{ buildingAddress }}</p>
        <el-alert v-if="parentVisibilityHint(buildingStatus)" :title="parentVisibilityHint(buildingStatus)" type="warning" :closable="false" show-icon />
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
        <template #default="{ row }">{{ formatPrice(row.base_rent, row.currency) }}{{ (row as any).rent_period === 'weekly' ? '/周' : '/月' }}</template>
      </el-table-column>
      <el-table-column prop="deposit_amount" label="押金" width="100">
        <template #default="{ row }">{{ row.deposit_amount ? formatPrice(row.deposit_amount, row.currency) : '-' }}</template>
      </el-table-column>
      <el-table-column prop="room_count" label="绑定房间" width="90" align="center" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="listingStatusTag(row.status)">{{ listingStatusLabel('unitType', row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/unit-type/${row.id}/edit`)">编辑</el-button>
          <el-button size="small" @click="$router.push(`/unit-type/${row.id}/copy`)">复制</el-button>
          <el-button size="small" type="primary" plain @click="$router.push(`/rooms/manage?unit_type_id=${row.id}`)">查看房间</el-button>
          <el-button v-if="listingPrimaryAction(row.status)==='offline'" size="small" type="warning" plain @click="changeLifecycle(row, 'offline')">下架</el-button>
          <el-button v-if="listingPrimaryAction(row.status)==='publish'" size="small" type="success" plain @click="changeLifecycle(row, 'publish')">重新上架</el-button>
          <el-dropdown trigger="click" @command="(command:string)=>command==='delete'&&handleDelete(row)"><el-button size="small">更多⌄</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="delete">移入回收站</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
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
import api, { toUserFriendly } from '@/services/api'
import { formatPrice } from '@/data/currency'
import { propertyService } from '@/services/property'
import { listingPrimaryAction, listingStatusLabel, listingStatusTag, parentVisibilityHint } from '@/utils/listingStatus'

const route = useRoute()
const buildingId = Number(route.params.id)
const buildingName = ref('')
const buildingAddress = ref('')
const buildingStatus = ref('')
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
  try { const r = await api.get('/buildings/' + buildingId); buildingName.value = r.data.name; buildingAddress.value = r.data.address || ''; buildingStatus.value = r.data.status || '' } catch { /* */ }
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

async function changeLifecycle(row:any, action:'offline'|'publish') {
  try {
    if (action === 'offline') await propertyService.offline(row.id)
    else await propertyService.publish(row.id)
    ElMessage.success(action === 'offline' ? '户型已下架，已有订单不受影响' : '户型已重新上架')
    await fetchList()
  } catch (e:any) {
    if (e.config) e.config._handled = true
    const message = toUserFriendly(e)
    if (action === 'publish') {
      await ElMessageBox.confirm(message, '资料尚未完善', { confirmButtonText: '前往编辑', cancelButtonText: '取消' })
      location.href = `/unit-type/${row.id}/edit`
    } else ElMessage.error(message)
  }
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px }
h2 { font-size: 22px; color: #303133; margin: 0 }
.sub { color: #909399; font-size: 13px; margin: 4px 0 0 }
</style>
