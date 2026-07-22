<template>
  <div class="page-container">
    <div class="page-header">
      <h2>户型管理</h2>
      <div style="display:flex;gap:10px;align-items:center">
        <el-radio-group v-model="viewMode" size="small">
          <el-radio-button value="active">📋 管理中</el-radio-button>
          <el-radio-button value="trash">🗑️ 回收站</el-radio-button>
        </el-radio-group>
        <el-button v-if="viewMode==='active'" type="primary" @click="$router.push('/unit-type/create')">+ 发布户型</el-button>
      </div>
    </div>

    <!-- 回收站模式 -->
    <div v-if="viewMode==='trash'" v-loading="trashLoading">
      <div v-if="!trashItems.length && !trashLoading" style="text-align:center;padding:40px;color:#909399">🗑️ 回收站为空</div>
      <div class="ut-cards" v-if="trashItems.length">
        <div v-for="ut in trashItems" :key="ut.id" class="ut-card trash-item">
          <div class="utc-thumb">
            <img v-if="ut.image_urls?.[0]" :src="ut.image_urls[0]" alt="" />
            <span v-else>🏠</span>
          </div>
          <div class="utc-info">
            <div class="utc-name">{{ ut.name }}</div>
            <div class="utc-meta">
              <span class="utc-tag">{{ ut.bedrooms }}室{{ ut.hall_count }}厅{{ ut.bathrooms }}卫</span>
              <span class="utc-tag">{{ ut.area_sqm }}㎡</span>
              <span class="utc-tag">🏢 {{ ut.institute_name || '未知公寓' }}</span>
              <el-tag size="small" type="info">已删除</el-tag>
            </div>
          </div>
          <div class="utc-right">
            <el-tag size="small" type="info" style="margin-bottom:6px">已删除</el-tag>
            <div class="trash-time" v-if="ut.deleted_at" style="margin-bottom:6px">{{ fmtTime(ut.deleted_at) }}</div>
            <el-button size="small" type="primary" @click="restoreUnitType(ut.id)">🔄 恢复</el-button>
            <el-popconfirm title="确定永久删除？不可恢复！" @confirm="hardDeleteUnitType(ut.id)">
              <template #reference>
                <el-button size="small" type="danger" plain>💥 硬删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>
    </div>

    <!-- 筛选栏（仅管理模式） -->
    <template v-if="viewMode==='active'">
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
            <!-- 户型卡片列表 — 无需横向滚动，全部信息一目了然 -->
            <div class="ut-cards" v-if="getBuildingUnitTypes(b.id).length">
              <div v-for="ut in getBuildingUnitTypes(b.id)" :key="ut.id" class="ut-card">
                <!-- 左侧：户型图 -->
                <div class="utc-thumb">
                  <el-image v-if="ut.image_urls?.[0]" :src="ut.image_urls[0]" preview-teleported :preview-src-list="ut.image_urls" fit="cover" style="width:100%;height:100%" />
                  <span v-else class="utc-thumb-placeholder">🏠</span>
                </div>
                <!-- 中间：核心信息 -->
                <div class="utc-info">
                  <div class="utc-name">{{ ut.name }}</div>
                  <div class="utc-meta">
                    <span class="utc-tag">{{ ut.bedrooms }}室{{ ut.hall_count }}厅{{ ut.bathrooms }}卫</span>
                    <span class="utc-tag">{{ ut.area_sqm }}㎡</span>
                    <span class="utc-tag" v-if="ut.room_count > 0">{{ ut.room_count }}间房</span>
                    <el-tag size="small" :type="ut.status==='available'?'success':'info'">{{ ut.status==='available'?'可租':'已租' }}</el-tag>
                  </div>
                  <div class="utc-amenities" v-if="ut.amenities?.length">
                    <span v-for="a in ut.amenities.slice(0, 6)" :key="a" class="utc-amenity">{{ a }}</span>
                    <span v-if="ut.amenities.length > 6" class="utc-amenity">+{{ ut.amenities.length - 6 }}</span>
                  </div>
                </div>
                <!-- 右侧：价格 + 操作 -->
                <div class="utc-right">
                  <div class="utc-price">
                    <span class="utc-price-val">{{ currencySym(ut.currency) }}{{ Number(ut.base_rent).toLocaleString() }}</span>
                    <span class="utc-price-unit">/月</span>
                  </div>
                  <div class="utc-deposit" v-if="ut.deposit_amount">
                    押金 {{ currencySym(ut.currency) }}{{ Number(ut.deposit_amount).toLocaleString() }}
                  </div>
                  <div class="utc-lease" v-if="ut.lease_start || ut.lease_end">
                    {{ ut.lease_start || '?' }} ~ {{ ut.lease_end || '?' }}
                  </div>
                  <div class="utc-actions">
                    <el-button size="small" @click="$router.push(`/unit-type/${ut.id}/edit`)">编辑</el-button>
                    <el-button size="small" @click="$router.push(`/unit-type/${ut.id}/copy`)">复制</el-button>
                    <el-button size="small" type="danger" plain @click="handleDelete(ut)">删除</el-button>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="utc-empty">该公寓暂无户型</div>
          </div>
        </el-card>
      </template>
    </div>
    </template>

    <el-empty v-if="!loading && !allUnitTypes.length && viewMode==='active'" description="暂无户型数据">
      <el-button type="primary" @click="$router.push('/unit-type/create')">发布第一个户型</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/services/api'
import { buildingService, type Building } from '@/services/building'

const allUnitTypes = ref<any[]>([])
const trashItems = ref<any[]>([])
const trashLoading = ref(false)
const viewMode = ref<'active'|'trash'>('active')
const currencyMap: Record<string, string> = { CNY:'¥', USD:'$', GBP:'£', EUR:'€', AUD:'A$', SGD:'S$', CAD:'C$', HKD:'HK$', JPY:'¥', KRW:'₩' }
function currencySym(code?: string) { return currencyMap[code || 'CNY'] || '¥' }
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

watch(viewMode, (v) => { if (v === 'trash') loadTrash() })
onMounted(() => { loadBuildings(); fetchList() })

async function loadTrash() {
  trashLoading.value = true
  try {
    const r = await api.get('/unit-types/recycle-bin', { params: { page_size: 2000 } })
    trashItems.value = r.data.items || []
  } catch { /* */ }
  finally { trashLoading.value = false }
}

function fmtTime(iso: string): string { try { return new Date(iso).toLocaleString('zh-CN', { hour12: false }) } catch { return iso } }

async function restoreUnitType(id: number) {
  try {
    await api.post('/unit-types/' + id + '/restore')
    ElMessage.success('已恢复')
    loadTrash()
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '恢复失败')
  }
}

async function hardDeleteUnitType(id: number) {
  try {
    await api.delete('/unit-types/' + id + '/hard')
    ElMessage.success('已永久删除')
    loadTrash()
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

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
    await ElMessageBox.confirm(`确定删除户型「${row.name}」？该户型将进入回收站。`, '警告', { type: 'warning' })
    await api.delete('/unit-types/' + row.id)
    ElMessage.success('已移至回收站')
    allUnitTypes.value = allUnitTypes.value.filter(u => u.id !== row.id)
    loadTrash()
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
.building-toggle { display: flex; align-items: center; transition: transform 0.2s; cursor: pointer }
.building-toggle .rotated { transform: rotate(180deg) }
.building-table { margin-top: 12px }

/* ═══════════ 户型卡片 ═══════════ */
.ut-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ut-card {
  display: flex;
  align-items: stretch;
  gap: 0;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  overflow: hidden;
  transition: box-shadow 0.15s;
}

.ut-card:hover {
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}

/* 左侧缩略图 */
.utc-thumb {
  width: 100px;
  flex-shrink: 0;
  background: #f5f6f8;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 32px;
  color: #c0c4cc;
}

.utc-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.utc-thumb-placeholder {
  font-size: 32px;
  color: #c0c4cc;
}

/* 中间信息 */
.utc-info {
  flex: 1;
  min-width: 0;
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}

.utc-name {
  font-size: 16px;
  font-weight: 700;
  color: #1a1a2e;
  line-height: 1.3;
}

.utc-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.utc-tag {
  font-size: 13px;
  color: #606266;
  background: #f5f7fa;
  padding: 2px 10px;
  border-radius: 6px;
  font-weight: 500;
}

.utc-amenities {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.utc-amenity {
  font-size: 11px;
  color: #909399;
  background: #fafafa;
  border: 1px solid #eee;
  padding: 2px 8px;
  border-radius: 4px;
}

/* 右侧价格+操作 */
.utc-right {
  flex-shrink: 0;
  padding: 14px 18px;
  border-left: 1px solid #f0f2f5;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  gap: 4px;
  min-width: 170px;
}

.utc-price {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.utc-price-val {
  font-size: 20px;
  font-weight: 700;
  color: #f56c6c;
}

.utc-price-unit {
  font-size: 13px;
  color: #909399;
}

.utc-deposit {
  font-size: 12px;
  color: #909399;
}

.utc-lease {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.utc-actions {
  display: flex;
  gap: 6px;
  margin-top: 4px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.utc-empty {
  padding: 24px;
  text-align: center;
  color: #c0c4cc;
  font-size: 14px;
}
.trash-time {
  font-size: 11px;
  color: #c0c4cc;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .ut-card {
    flex-direction: column;
  }
  .utc-thumb {
    width: 100%;
    height: 140px;
  }
  .utc-right {
    border-left: none;
    border-top: 1px solid #f0f2f5;
    flex-direction: row;
    flex-wrap: wrap;
    justify-content: flex-start;
    gap: 10px;
    padding: 12px 18px;
  }
}
</style>
