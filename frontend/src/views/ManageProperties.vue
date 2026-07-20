<template>
  <div class="page-container">
    <div class="page-header">
      <h2>户型管理</h2>
      <el-button type="primary" @click="$router.push('/unit-type/create')">+ 发布户型</el-button>
    </div>

    <!-- 筛选栏 -->
    <el-card shadow="never" style="margin-bottom:16px">
      <el-row :gutter="12" align="middle">
        <el-col :span="4">
          <el-select v-model="filterInstituteId" placeholder="筛选公寓" clearable filterable style="width:100%">
            <el-option v-for="b in buildings" :key="b.id" :label="`${b.name} (${getUnitTypeCount(b.id)}个户型)`" :value="b.id" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-input-number v-model="filterRentMin" placeholder="最低租金" :min="0" controls-position="right" style="width:100%" />
        </el-col>
        <el-col :span="3">
          <el-input-number v-model="filterRentMax" placeholder="最高租金" :min="0" controls-position="right" style="width:100%" />
        </el-col>
        <el-col :span="3">
          <el-input-number v-model="filterAreaMin" placeholder="最小面积" :min="0" controls-position="right" style="width:100%" />
        </el-col>
        <el-col :span="3">
          <el-input-number v-model="filterAreaMax" placeholder="最大面积" :min="0" controls-position="right" style="width:100%" />
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="fetchList">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-col>
        <el-col :span="4" style="text-align:right">
          <el-button size="small" @click="expandAll">全部展开</el-button>
          <el-button size="small" @click="collapseAll">全部折叠</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 按公寓分组 -->
    <div v-loading="loading">
      <template v-for="b in groupedBuildings" :key="b.id">
        <el-card v-if="getBuildingUnitTypes(b.id).length" shadow="never" class="building-card" style="margin-bottom:16px">
          <div class="building-header" @click="toggleExpand(b.id)">
            <div class="building-info">
              <span class="building-icon">🏢</span>
              <span class="building-name">{{ b.name }}</span>
              <el-tag size="small" type="info">{{ getBuildingUnitTypes(b.id).length }} 个户型</el-tag>
              <span v-if="b.address" class="building-addr">{{ b.address }}</span>
            </div>
            <div class="building-actions" @click.stop>
              <el-button size="small" @click="$router.push(`/unit-type/create?institute_id=${b.id}`)">+ 新增户型</el-button>
              <el-button size="small" @click="$router.push(`/buildings/${b.id}/unit-types`)">查看全部</el-button>
            </div>
            <div class="building-toggle">
              <span style="color:#909399;font-size:12px;margin-right:4px">{{ expandedIds.has(b.id) ? '收起' : '展开' }}</span>
              <span :class="{ rotated: expandedIds.has(b.id) }">▼</span>
            </div>
          </div>

          <div v-show="expandedIds.has(b.id)" class="building-table">
            <el-table :data="getBuildingUnitTypes(b.id)" stripe size="small">
              <el-table-column prop="name" label="户型名称" min-width="160" />
              <el-table-column label="室/厅/卫" width="120">
                <template #default="{ row }">{{ row.bedrooms }}室{{ row.hall_count }}厅{{ row.bathrooms }}卫</template>
              </el-table-column>
              <el-table-column prop="area_sqm" label="面积(㎡)" width="90" />
              <el-table-column label="标准租金" width="110">
                <template #default="{ row }">¥{{ Number(row.base_rent).toLocaleString() }}/月</template>
              </el-table-column>
              <el-table-column prop="deposit_amount" label="押金" width="100">
                <template #default="{ row }">¥{{ row.deposit_amount ? Number(row.deposit_amount).toLocaleString() : '-' }}</template>
              </el-table-column>
              <el-table-column prop="room_count" label="房间数" width="80" align="center" />
              <el-table-column prop="status" label="状态" width="80">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.status==='available'?'success':'info'">{{ row.status==='available'?'可租':'已租' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="户型图" width="70">
                <template #default="{ row }">
                  <el-image v-if="row.image_urls?.length" :src="row.image_urls[0]" style="width:40px;height:40px;border-radius:4px;object-fit:cover" preview-teleported :preview-src-list="row.image_urls" />
                  <span v-else style="color:#c0c4cc">-</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="280" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" @click="$router.push(`/unit-type/${row.id}/edit`)">编辑</el-button>
                  <el-button size="small" @click="$router.push(`/unit-type/${row.id}/copy`)">复制</el-button>
                  <el-button size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>
      </template>
    </div>

    <el-empty v-if="!loading && !allUnitTypes.length" description="暂无户型数据">
      <el-button type="primary" @click="$router.push('/unit-type/create')">发布第一个户型</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/services/api'
import { buildingService, type Building } from '@/services/building'

const allUnitTypes = ref<any[]>([])
const buildings = ref<Building[]>([])
const loading = ref(false)
const expandedIds = ref(new Set<number>())

const filterInstituteId = ref<number | undefined>()
const filterRentMin = ref<number | undefined>()
const filterRentMax = ref<number | undefined>()
const filterAreaMin = ref<number | undefined>()
const filterAreaMax = ref<number | undefined>()

// 有户型的公寓
const groupedBuildings = computed(() => {
  return buildings.value.filter(b => getBuildingUnitTypes(b.id).length > 0)
})

function getUnitTypeCount(buildingId: number) {
  return allUnitTypes.value.filter(u => u.institute_id === buildingId).length
}

function getBuildingUnitTypes(buildingId: number) {
  let list = allUnitTypes.value.filter(u => u.institute_id === buildingId)
  if (filterRentMin.value != null) list = list.filter(u => Number(u.base_rent) >= filterRentMin.value!)
  if (filterRentMax.value != null) list = list.filter(u => Number(u.base_rent) <= filterRentMax.value!)
  if (filterAreaMin.value != null) list = list.filter(u => Number(u.area_sqm) >= filterAreaMin.value!)
  if (filterAreaMax.value != null) list = list.filter(u => Number(u.area_sqm) <= filterAreaMax.value!)
  return list
}

function toggleExpand(id: number) {
  if (expandedIds.value.has(id)) expandedIds.value.delete(id)
  else expandedIds.value.add(id)
  expandedIds.value = new Set(expandedIds.value)
}

function expandAll() {
  expandedIds.value = new Set(buildings.value.map(b => b.id))
}

function collapseAll() {
  expandedIds.value = new Set()
}

function resetFilters() {
  filterInstituteId.value = undefined
  filterRentMin.value = undefined; filterRentMax.value = undefined
  filterAreaMin.value = undefined; filterAreaMax.value = undefined
}

onMounted(() => { loadBuildings(); fetchList() })

async function loadBuildings() {
  try { buildings.value = await buildingService.list({ limit: 200 }) } catch { /* */ }
}

async function fetchList() {
  loading.value = true
  try {
    const params: any = { page_size: 500 }
    if (filterInstituteId.value) params.institute_id = filterInstituteId.value
    const r = await api.get('/unit-types', { params })
    allUnitTypes.value = r.data.items || []
    // 自动展开有数据的公寓
    expandedIds.value = new Set(
      buildings.value.filter(b => getBuildingUnitTypes(b.id).length > 0).map(b => b.id)
    )
  } catch { /* */ }
  finally { loading.value = false }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除户型「${row.name}」？该操作不可恢复。`, '警告', { type: 'warning' })
    await api.delete('/unit-types/' + row.id)
    ElMessage.success('已删除')
    allUnitTypes.value = allUnitTypes.value.filter(u => u.id !== row.id)
  } catch { /* cancelled */ }
}
</script>

<style scoped>
h2 { font-size: 22px; color: #303133; margin: 0 }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px }

.building-card { border-left: 3px solid var(--primary, #FF6B35) }
.building-header {
  display: flex; justify-content: space-between; align-items: center;
  cursor: pointer; user-select: none; padding: 4px 0;
}
.building-header:hover { opacity: 0.85 }
.building-info { display: flex; align-items: center; gap: 10px; flex: 1 }
.building-icon { font-size: 20px }
.building-name { font-weight: 600; font-size: 15px; color: #303133 }
.building-addr { color: #909399; font-size: 13px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap }
.building-actions { display: flex; gap: 6px; margin-right: 16px }
.building-toggle { display: flex; align-items: center; transition: transform 0.2s }
.building-toggle .rotated { transform: rotate(180deg) }
.building-table { margin-top: 12px }
</style>
