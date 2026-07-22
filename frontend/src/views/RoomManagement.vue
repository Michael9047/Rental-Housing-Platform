<template>
  <div class="page-container">
    <div class="page-header">
      <h2>房间管理</h2>
      <div style="display:flex;gap:8px;align-items:center">
        <el-radio-group v-model="viewMode" size="small">
          <el-radio-button value="active">📋 管理中</el-radio-button>
          <el-radio-button value="trash">🗑️ 回收站</el-radio-button>
        </el-radio-group>
        <template v-if="viewMode==='active'">
          <el-dropdown style="margin-right:8px">
            <el-button type="warning" size="small" :disabled="!selectedIds.length">
              批量操作{{ selectedIds.length ? ' ('+selectedIds.length+')' : '' }}
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="doBatch('available')" :disabled="!selectedIds.length">批量上架</el-dropdown-item>
                <el-dropdown-item @click="doBatch('offline')" :disabled="!selectedIds.length">批量下架</el-dropdown-item>
                <el-dropdown-item @click="doBatch('delete')" :disabled="!selectedIds.length" style="color:#f56c6c">批量删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button type="primary" @click="openAddDialog">+ 新增房间</el-button>
        </template>
      </div>
    </div>

    <!-- 回收站模式 -->
    <div v-if="viewMode==='trash'" v-loading="trashLoading">
      <div v-if="!trashRooms.length && !trashLoading" style="text-align:center;padding:40px;color:#909399">🗑️ 回收站为空</div>
      <div class="room-cards" v-if="trashRooms.length">
        <div v-for="room in trashRooms" :key="room.id" class="room-card trash-room-card">
          <div class="rmc-check">🗑️</div>
          <!-- 房间标识 -->
          <div class="rmc-id trash-room-id">
            <div class="rmc-room-number">{{ room.room_number || '-' }}</div>
            <div class="rmc-meta-line">
              <span v-if="room.building_block" class="rmc-meta-tag">🏗️ {{ room.building_block }}</span>
              <span v-if="room.floor != null" class="rmc-meta-tag">🔢 {{ room.floor }}楼</span>
            </div>
          </div>
          <!-- 归属信息：公寓 → 户型 -->
          <div class="trash-room-belong">
            <div class="trash-belong-row">
              <span class="trash-belong-icon">🏢</span>
              <span class="trash-belong-text">{{ room.institute_name || '未知公寓' }}</span>
            </div>
            <div class="trash-belong-row">
              <span class="trash-belong-icon">📐</span>
              <span class="trash-belong-text">{{ room.unit_type_name || '未知户型' }}</span>
            </div>
          </div>
          <!-- 状态+删除时间 -->
          <div class="rmc-status">
            <el-tag size="small" type="info">已删除</el-tag>
            <div class="trash-time" v-if="room.deleted_at">{{ fmtTime(room.deleted_at) }}</div>
          </div>
          <div class="rmc-actions">
            <el-button size="small" type="primary" @click="restoreRoom(room.id)">🔄 恢复</el-button>
            <el-popconfirm title="确定永久删除？不可恢复！" @confirm="hardDeleteRoom(room.id)">
              <template #reference>
                <el-button size="small" type="danger" plain>💥 硬删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>
      <!-- 分页提示 -->
      <div v-if="trashTotal > trashRooms.length" style="text-align:center;padding:12px;color:#909399;font-size:13px">
        仅显示最近 {{ trashRooms.length }} 项，回收站共 {{ trashTotal }} 项
      </div>
    </div>

    <template v-if="viewMode==='active'">
    <!-- 全局展开/折叠 -->
    <div style="margin-bottom:12px;display:flex;gap:8px">
      <el-button size="small" @click="expandAll">全部展开</el-button>
      <el-button size="small" @click="collapseAll">全部折叠</el-button>
      <el-select v-model="filterInstituteId" placeholder="筛选公寓" clearable style="width:180px" size="small" @change="onInstituteFilter">
        <el-option v-for="b in buildings" :key="b.id" :label="b.name" :value="b.id" />
      </el-select>
      <el-select v-model="filterUnitTypeId" placeholder="筛选户型" clearable style="width:180px" size="small">
        <el-option v-for="u in filteredUnitTypes" :key="u.id" :label="u.name" :value="u.id" />
      </el-select>
    </div>

    <div v-loading="loading">
      <!-- 按公寓 → 户型 → 房间 三层折叠 -->
      <template v-for="b in displayBuildings" :key="'b'+b.id">
        <el-card shadow="never" class="building-card" style="margin-bottom:12px">
          <!-- 公寓头部 -->
          <div class="level-header" @click="toggleB(b.id)">
            <span class="level-icon">🏢</span>
            <span class="level-name">{{ b.name }}</span>
            <el-tag size="small" type="info">{{ getRoomCount(b.id) }} 间</el-tag>
            <span :class="['arrow', { rotated: expandedBuildings.has(b.id) }]">▼</span>
          </div>

          <!-- 户型列表 -->
          <div v-show="expandedBuildings.has(b.id)" style="margin:8px 0 0 20px">
            <template v-for="ut in getUnitTypes(b.id)" :key="'ut'+ut.id">
              <div class="unit-type-section" style="margin-bottom:8px">
                <!-- 户型头部 -->
                <div class="level-header sub" @click="toggleU(ut.id)">
                  <span class="level-icon">📐</span>
                  <span class="level-name">{{ ut.name }} ({{ ut.bedrooms }}室{{ ut.hall_count }}厅{{ ut.bathrooms }}卫 · ¥{{ Number(ut.base_rent).toLocaleString() }})</span>
                  <el-tag size="small">{{ getUtRoomCount(ut.id) }} 间</el-tag>
                  <span :class="['arrow', { rotated: expandedUnits.has(ut.id) }]">▼</span>
                </div>

                <!-- 房间卡片列表 — 无需横向滚动 -->
                <div v-show="expandedUnits.has(ut.id)" style="margin:6px 0 0 16px">
                  <div class="room-cards" v-if="sortedRooms(ut.id).length">
                    <div v-for="room in sortedRooms(ut.id)" :key="room.id" :class="['room-card', { selected: selectedIds.includes(room.id) }]">
                      <!-- 选择框 -->
                      <div class="rmc-check" @click.stop>
                        <el-checkbox :model-value="selectedIds.includes(room.id)" @change="toggleSelect(room)" />
                      </div>
                      <!-- 房间标识 -->
                      <div class="rmc-id">
                        <div class="rmc-room-number">{{ room.room_number || '-' }}</div>
                        <div class="rmc-meta-line">
                          <span v-if="room.building_block" class="rmc-meta-tag">🏗️ {{ room.building_block }}</span>
                          <span v-if="room.floor != null" class="rmc-meta-tag">🔢 {{ room.floor }}楼</span>
                        </div>
                      </div>
                      <!-- 信息 -->
                      <div class="rmc-info">
                        <div class="rmc-info-row" v-if="room.special_discount">
                          <span class="rmc-label">优惠</span>
                          <span class="rmc-value highlight">{{ room.special_discount }}</span>
                        </div>
                        <div class="rmc-info-row" v-if="room.available_from">
                          <span class="rmc-label">可入住</span>
                          <span class="rmc-value">{{ room.available_from }}</span>
                        </div>
                      </div>
                      <!-- 状态 -->
                      <div class="rmc-status">
                        <el-tag size="small" :type="statusType(room.status)">{{ statusLabel(room.status) }}</el-tag>
                      </div>
                      <!-- 操作 -->
                      <div class="rmc-actions">
                        <el-button size="small" @click="openEdit(room)">编辑</el-button>
                        <el-button size="small" :type="room.status==='offline'?'success':'warning'" @click="toggleStatus(room)">
                          {{ room.status==='offline'?'上架':'下架' }}
                        </el-button>
                        <el-button size="small" type="danger" plain @click="handleDelete(room)">删除</el-button>
                      </div>
                    </div>
                  </div>
                  <div v-if="!getRooms(ut.id).length" style="color:#c0c4cc;padding:12px 0">该户型下暂无房间</div>
                </div>
              </div>
            </template>
            <div v-if="!getUnitTypes(b.id).length" style="color:#c0c4cc;padding:8px 0">该公寓下暂无户型</div>
          </div>
        </el-card>
      </template>
    </div>
    </template>

    <el-empty v-if="!loading && !buildings.length && viewMode==='active'" description="暂无公寓数据" />

    <!-- ═══════ 新增/编辑房间弹窗 ═══════ -->
    <el-dialog v-model="dialogVisible" :title="editingRoom ? '编辑房间' : '新增房间'" width="680px" :close-on-click-modal="false" @closed="onDialogClosed">
      <!-- 锁定显示：所属公寓和户型 -->
      <el-descriptions v-if="dialogUnitType" :column="2" border size="small" style="margin-bottom:16px">
        <el-descriptions-item label="所属公寓">{{ dialogInstitute?.name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="所属户型">{{ dialogUnitType.name }} ({{ dialogUnitType.bedrooms }}室{{ dialogUnitType.hall_count }}厅{{ dialogUnitType.bathrooms }}卫)</el-descriptions-item>
      </el-descriptions>

      <!-- 选择目标公寓和户型（新增时） -->
      <el-row :gutter="12" style="margin-bottom:16px" v-if="!editingRoom">
        <el-col :span="12">
          <el-select v-model="dialogInstituteId" placeholder="选择公寓（必选）" filterable style="width:100%" @change="onDialogInstituteChange">
            <el-option v-for="b in buildings" :key="b.id" :label="b.name" :value="b.id" />
          </el-select>
        </el-col>
        <el-col :span="12">
          <el-select v-model="roomForm.unit_type_id" placeholder="选择户型（必选）" filterable style="width:100%" @change="onDialogUnitTypeChange">
            <el-option v-for="u in dialogUnitTypes" :key="u.id" :label="`${u.name} (${u.bedrooms}室${u.hall_count}厅${u.bathrooms}卫)`" :value="u.id" />
          </el-select>
        </el-col>
      </el-row>

      <el-tabs v-model="dialogTab" v-if="!editingRoom">
        <el-tab-pane label="单个上传" name="single">
          <el-form :model="roomForm" label-width="90px">
            <el-row :gutter="12">
              <el-col :span="12"><el-form-item label="房号" required><el-input v-model="roomForm.room_number" placeholder="如 1201" maxlength="20" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="楼栋号"><el-input v-model="roomForm.building_block" placeholder="如 Block A / A栋" maxlength="20" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="8"><el-form-item label="楼层"><el-input-number v-model="roomForm.floor" :min="0" controls-position="right" style="width:100%" placeholder="选填" /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="专属优惠"><el-input v-model="roomForm.special_discount" style="width:100%" placeholder="如 早鸟减100" maxlength="200" /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="状态"><el-select v-model="roomForm.status" style="width:100%"><el-option label="可租" value="available" /><el-option label="维护中" value="maintenance" /><el-option label="已下线" value="offline" /></el-select></el-form-item></el-col>
            </el-row>
            <el-form-item label="可入住日期"><el-date-picker v-model="roomForm.available_from" type="date" placeholder="选填" style="width:100%" value-format="YYYY-MM-DD" /></el-form-item>
            <el-form-item><el-button type="primary" :loading="roomSaving" @click="saveRoom">保存</el-button></el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="批量上传" name="batch">
          <!-- Step 0: 下载模板 -->
          <div style="margin-bottom:16px">
            <el-button size="small" @click="downloadTemplate">📥 下载模板 (Excel)</el-button>
            <span style="color:#909399;font-size:12px;margin-left:8px">模板包含示范行：房号、楼层、专属优惠、可入住时间、状态</span>
          </div>
          <!-- 文件上传 -->
          <div class="drop-zone" :class="{active:isDragging}" @click="$refs.fileInput.click()" @dragover.prevent="isDragging=true" @dragleave.prevent="isDragging=false" @drop.prevent="onDrop">
            <input ref="fileInput" type="file" accept=".csv,.xlsx,.xls" style="display:none" @change="onFileChange" />
            <template v-if="!batchFile"><p>点击或拖拽文件到此处</p><p style="font-size:12px;color:#909399">.csv / .xlsx / .xls</p></template>
            <template v-else><p style="font-weight:600">{{ batchFile.name }}</p><p style="font-size:12px;color:#909399">{{ formatSize(batchFile.size) }}</p><el-button type="danger" plain size="small" @click.stop="batchFile=null;batchRows=[]">移除</el-button></template>
          </div>
          <!-- 预览 -->
          <div v-if="batchRows.length" style="margin-top:12px">
            <p style="font-weight:600;margin-bottom:4px">预览（前 5 行）：</p>
            <el-table :data="batchRows.slice(0,5)" border size="small" max-height="200">
              <el-table-column prop="room_number" label="房号" width="90" />
              <el-table-column prop="building_block" label="楼栋" width="70" />
              <el-table-column prop="floor" label="楼层" width="60" />
              <el-table-column prop="special_discount" label="专属优惠" width="90" />
              <el-table-column prop="available_from" label="可入住日期" width="110" />
              <el-table-column prop="status" label="状态" width="70" />
              <el-table-column label="校验" min-width="150">
                <template #default="{ row,$index }"><span :style="{color:row._error?'#f56c6c':'#67c23a'}">{{ row._error || '✓ 通过' }}</span></template>
              </el-table-column>
            </el-table>
            <div style="margin-top:12px">
              <span style="color:#606266">共 {{ batchRows.length }} 行，有效 {{ validCount }} 行，异常 {{ errorCount }} 行</span>
              <el-button type="primary" size="small" style="margin-left:12px" :loading="batchImporting" @click="doBatchImport" :disabled="validCount===0">确认导入 ({{ validCount }} 条)</el-button>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>

      <!-- 编辑模式（仅单个房间字段） -->
      <template v-if="editingRoom">
        <el-form :model="roomForm" label-width="90px">
          <el-descriptions :column="2" border size="small" style="margin-bottom:12px">
            <el-descriptions-item label="公寓">{{ dialogInstitute?.name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="户型">{{ dialogUnitType?.name || '—' }}</el-descriptions-item>
          </el-descriptions>
          <el-row :gutter="12">
            <el-col :span="12"><el-form-item label="房号" required><el-input v-model="roomForm.room_number" placeholder="如 1201" maxlength="20" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="楼栋号"><el-input v-model="roomForm.building_block" placeholder="如 Block A / A栋" maxlength="20" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="8"><el-form-item label="楼层"><el-input-number v-model="roomForm.floor" :min="0" controls-position="right" style="width:100%" /></el-form-item></el-col>
            <el-col :span="8"><el-form-item label="专属优惠"><el-input v-model="roomForm.special_discount" style="width:100%" maxlength="200" /></el-form-item></el-col>
            <el-col :span="8"><el-form-item label="状态"><el-select v-model="roomForm.status" style="width:100%"><el-option label="可租" value="available" /><el-option label="维护中" value="maintenance" /><el-option label="已下线" value="offline" /></el-select></el-form-item></el-col>
          </el-row>
          <el-form-item label="可入住日期"><el-date-picker v-model="roomForm.available_from" type="date" placeholder="选填" style="width:100%" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item><el-button type="primary" :loading="roomSaving" @click="saveRoom">保存</el-button></el-form-item>
        </el-form>
      </template>

      <template v-if="!editingRoom && dialogTab==='single'" #footer><span style="color:#909399;font-size:12px">房号必填 · 其余选填</span></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/services/api'
import { buildingService, type Building } from '@/services/building'
import { useAuthStore } from '@/stores/auth'
// xlsx 动态导入，避免静态 import 导致组件初始化崩溃
let XLSX: any = null
async function getXLSX() {
  if (!XLSX) { const m = await import('xlsx'); XLSX = m }
  return XLSX
}

const authStore = useAuthStore()

// ═══ 数据 ═══
const buildings = ref<Building[]>([])
const allUnitTypes = ref<any[]>([])
const allRooms = ref<any[]>([])
const trashRooms = ref<any[]>([])
const trashTotal = ref(0)
const trashLoading = ref(false)
const viewMode = ref<'active'|'trash'>('active')
const loading = ref(false)
const expandedBuildings = ref(new Set<number>())
const expandedUnits = ref(new Set<number>())
const selectedIds = ref<number[]>([])
const filterInstituteId = ref<number | undefined>()
const filterUnitTypeId = ref<number | undefined>()

// ═══ 筛选 ═══
const filteredUnitTypes = computed(() => {
  if (filterInstituteId.value) return allUnitTypes.value.filter(u => u.institute_id === filterInstituteId.value)
  return allUnitTypes.value
})
const displayBuildings = computed(() => {
  if (filterInstituteId.value) return buildings.value.filter(b => b.id === filterInstituteId.value)
  return buildings.value.filter(b => getRoomCount(b.id) > 0 || getUnitTypes(b.id).length > 0)
})

function onInstituteFilter() {
  filterUnitTypeId.value = undefined
  loadUnitTypes()
}

function getRoomCount(buildingId: number) {
  if (filterUnitTypeId.value) return getRooms(filterUnitTypeId.value).length
  const utIds = new Set(getUnitTypes(buildingId).map(u => u.id))
  return allRooms.value.filter(r => utIds.has(r.unit_type_id)).length
}
function getUnitTypes(buildingId: number) {
  let list = allUnitTypes.value.filter(u => u.institute_id === buildingId)
  if (filterUnitTypeId.value) list = list.filter(u => u.id === filterUnitTypeId.value)
  return list
}
function getUtRoomCount(utId: number) { return sortedRooms(utId).length }
function getRooms(utId: number) { return allRooms.value.filter(r => r.unit_type_id === utId) }
function sortedRooms(utId: number) {
  const rooms = getRooms(utId)
  return [...rooms].sort((a, b) => {
    // 楼栋优先：空楼栋排最前
    const ba = (a.building_block || '') as string
    const bb = (b.building_block || '') as string
    if (ba !== bb) {
      if (!ba && bb) return -1
      if (ba && !bb) return 1
      return ba.localeCompare(bb, 'zh')
    }
    // 房间号：字母开头在前，数字开头在后（数字永远大于字母）
    const ra = (a.room_number || '') as string
    const rb = (b.room_number || '') as string
    const aIsDigit = /^\d/.test(ra)
    const bIsDigit = /^\d/.test(rb)
    if (aIsDigit && !bIsDigit) return 1
    if (!aIsDigit && bIsDigit) return -1
    return ra.localeCompare(rb, undefined, { numeric: true })
  })
}

function toggleB(id: number) { const s = new Set(expandedBuildings.value); s.has(id) ? s.delete(id) : s.add(id); expandedBuildings.value = s }
function toggleU(id: number) { const s = new Set(expandedUnits.value); s.has(id) ? s.delete(id) : s.add(id); expandedUnits.value = s }
function expandAll() {
  expandedBuildings.value = new Set(buildings.value.map(b => b.id))
  expandedUnits.value = new Set(allUnitTypes.value.map(u => u.id))
}
function collapseAll() { expandedBuildings.value = new Set(); expandedUnits.value = new Set() }

function statusType(s: string) { const m: any = { available: 'success', rented: 'warning', maintenance: 'info', offline: 'danger' }; return m[s] || 'info' }
function statusLabel(s: string) { const m: any = { available: '可租', rented: '已租', maintenance: '维护中', offline: '已下线' }; return m[s] || s }

function onSelChange(rows: any[]) { selectedIds.value = rows.map(r => r.id) }
function toggleSelect(room: any) {
  const ids = [...selectedIds.value]
  const idx = ids.indexOf(room.id)
  if (idx >= 0) ids.splice(idx, 1)
  else ids.push(room.id)
  selectedIds.value = ids
}

async function doBatch(action: string) {
  if (!selectedIds.value.length) { ElMessage.warning('请先选择房间'); return }
  if (action === 'delete') { try { await ElMessageBox.confirm(`确认删除 ${selectedIds.value.length} 个房间？`, '确认', { type: 'warning' }) } catch { return } }
  try {
    if (action === 'delete') await api.post('/rooms/batch/delete', { ids: selectedIds.value })
    else await api.post('/rooms/batch/status', { ids: selectedIds.value, status: action })
    ElMessage.success('操作成功'); selectedIds.value = []; loadRooms(); loadTrashRooms()
  } catch { /* */ }
}

async function toggleStatus(row: any) {
  const newStatus = row.status === 'offline' ? 'available' : 'offline'
  try { await api.patch(`/rooms/${row.id}`, { status: newStatus, version: row.version }); ElMessage.success(newStatus === 'available' ? '已上架' : '已下架'); loadRooms() } catch { /* */ }
}

async function handleDelete(row: any) {
  try { await ElMessageBox.confirm('确定删除此房间？该房间将进入回收站。', '确认', { type: 'warning' }); await api.delete('/rooms/' + row.id); ElMessage.success('已移至回收站'); loadRooms(); loadTrashRooms() } catch { /* */ }
}

// ═══ 房间弹窗 ═══
const dialogVisible = ref(false); const editingRoom = ref<any>(null)
const dialogTab = ref('single'); const roomSaving = ref(false)
const dialogInstituteId = ref<number | undefined>(); const dialogUnitTypes = ref<any[]>([])
const dialogInstitute = ref<any>(null); const dialogUnitType = ref<any>(null)

async function onDialogInstituteChange() {
  roomForm.unit_type_id = 0; dialogUnitType.value = null
  if (dialogInstituteId.value) {
    const r = await api.get('/unit-types', { params: { institute_id: dialogInstituteId.value, page_size: 500 } })
    dialogUnitTypes.value = r.data.items || []
  } else { dialogUnitTypes.value = [] }
}

function onDialogUnitTypeChange() {
  dialogUnitType.value = dialogUnitTypes.value.find(u => u.id === roomForm.unit_type_id) || null
  dialogInstitute.value = buildings.value.find(b => b.id === dialogInstituteId.value) || null
}
const roomForm = reactive({ unit_type_id: 0, room_number: '', building_block: '' as string | undefined, floor: undefined as number | undefined, special_discount: '' as string | undefined, available_from: '' as string | undefined, status: 'available' })

function openAddDialog() {
  editingRoom.value = null; dialogTab.value = 'single'
  dialogInstitute.value = null; dialogUnitType.value = null
  Object.assign(roomForm, { unit_type_id: 0, room_number: '', building_block: undefined, floor: undefined, special_discount: undefined, available_from: undefined, status: 'available' })
  dialogVisible.value = true
}

function openEdit(row: any) {
  editingRoom.value = row
  roomForm.unit_type_id = row.unit_type_id
  roomForm.room_number = row.room_number || ''
  roomForm.building_block = row.building_block || undefined
  roomForm.floor = row.floor ?? undefined
  roomForm.special_discount = row.special_discount || ''
  roomForm.available_from = row.available_from ?? undefined
  roomForm.status = row.status
  dialogInstitute.value = buildings.value.find(b => b.id === row.institute_id) || null
  dialogUnitType.value = allUnitTypes.value.find(u => u.id === row.unit_type_id) || null
  dialogVisible.value = true
}

function onDialogClosed() {
  editingRoom.value = null
  dialogUnitType.value = null
  dialogInstitute.value = null
}

async function saveRoom() {
  if (!roomForm.unit_type_id) { ElMessage.warning('请先在弹窗顶部选择公寓和户型'); return }
  if (!roomForm.room_number.trim()) { ElMessage.warning('请输入房号'); return }

  // 查重
  if (!editingRoom.value || roomForm.room_number !== editingRoom.value.room_number) {
    try {
      const params: any = { unit_type_id: roomForm.unit_type_id, room_number: roomForm.room_number.trim() }
      if (editingRoom.value) params.exclude_id = editingRoom.value.id
      const r = await api.get('/rooms/check-duplicate', { params })
      if (r.data.duplicate) { ElMessage.warning(`房号「${roomForm.room_number.trim()}」已在当前户型下存在，请勿重复录入`); return }
    } catch { /* */ }
  }

  roomSaving.value = true
  const data: any = {
    room_number: roomForm.room_number.trim() || null,
    building_block: roomForm.building_block?.trim() || null,
    floor: roomForm.floor ?? null,
    special_discount: roomForm.special_discount || null,
    available_from: roomForm.available_from || null,
    status: roomForm.status,
  }
  // 新增时加必填字段
  if (!editingRoom.value) {
    data.unit_type_id = roomForm.unit_type_id
    data.landlord_id = authStore.user?.id
  }
  try {
    if (editingRoom.value) {
      // 不发送version，避免乐观锁冲突
      console.log('PATCH /rooms/' + editingRoom.value.id, JSON.stringify(data))
      await api.patch('/rooms/' + editingRoom.value.id, data)
    } else {
      await api.post('/rooms', data)
    }
    ElMessage.success('保存成功'); dialogVisible.value = false; loadRooms()
  } catch (e: any) {
    console.error('saveRoom error:', e)
    const detail = e?.response?.data?.detail
    // Pydantic 校验错误格式：[{msg, loc, ...}, ...]
    if (Array.isArray(detail)) {
      const msgs = detail.map((d: any) => d.loc?.join('.') + ': ' + d.msg).join('; ')
      ElMessage.error('校验失败: ' + msgs)
    } else if (typeof detail === 'string') {
      ElMessage.error(detail)
    } else if (e?.response?.data?.error?.message) {
      ElMessage.error(e.response.data.error.message)
    } else if (e?.response?.status === 422) {
      ElMessage.error('数据校验失败(422)，请检查字段格式')
    } else {
      ElMessage.error('保存失败 (HTTP ' + (e?.response?.status || '?') + ')')
    }
  } finally { roomSaving.value = false }
}

// ═══ 批量导入 ═══
const batchFile = ref<File | null>(null); const isDragging = ref(false)
const batchRows = ref<any[]>([]); const batchImporting = ref(false)

const errorCount = computed(() => batchRows.value.filter(r => r._error).length)
const validCount = computed(() => batchRows.value.filter(r => !r._error).length)

function formatSize(bytes: number) { return bytes < 1024 * 1024 ? (bytes / 1024).toFixed(1) + ' KB' : (bytes / (1024 * 1024)).toFixed(1) + ' MB' }

async function downloadTemplate() {
  const X = await getXLSX()
  const wb = X.utils.book_new()
  const ws = X.utils.json_to_sheet([
    { 房号: 'A-1201', 楼栋号: 'A栋', 楼层: 12, 专属优惠: '', 可入住时间: '2026-08-01', 状态: '可租' },
    { 房号: 'B-1202', 楼栋号: 'B栋', 楼层: 12, 专属优惠: '早鸟减100', 可入住时间: '', 状态: '可租' },
  ])
  ws['!cols'] = [{ wch: 10 }, { wch: 8 }, { wch: 8 }, { wch: 10 }, { wch: 14 }, { wch: 8 }]
  X.utils.book_append_sheet(wb, ws, '房间导入模板')
  X.writeFile(wb, '房间导入模板.xlsx')
  ElMessage.success('模板已下载')
}

function onDrop(e: DragEvent) { isDragging.value = false; if (e.dataTransfer?.files.length) parseFile(e.dataTransfer.files[0]) }
function onFileChange(e: Event) { const f = (e.target as HTMLInputElement).files?.[0]; if (f) parseFile(f) }

async function parseFile(file: File) {
  batchFile.value = file; batchRows.value = []
  try {
    const isCSV = file.name.endsWith('.csv')
    const rawData = isCSV ? await file.text() : await file.arrayBuffer()
    const X = await getXLSX()
    const wb = X.read(rawData, { type: isCSV ? 'string' : 'array' })
    const ws = wb.Sheets[wb.SheetNames[0]]
    const rows: any[] = X.utils.sheet_to_json(ws, { defval: '' })
    if (!rows.length) { ElMessage.warning('文件无数据'); return }

    // Excel日期序列号转日期字符串
    function excelDateToStr(v) {
      if (typeof v === 'number' && v > 40000 && v < 80000) {
        const d = new Date((v - 25569) * 86400 * 1000)
        return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0')
      }
      return v
    }

    // 列名映射
    const cols: Record<string, string> = { '房号': 'room_number', '楼栋号': 'building_block', '楼层': 'floor', '专属优惠': 'special_discount', '可入住时间': 'available_from', '可入住日期': 'available_from', '状态': 'status', 'room_number': 'room_number', 'building_block': 'building_block', 'floor': 'floor', 'special_discount': 'special_discount', 'available_from': 'available_from', 'status': 'status' }

    // 必填列检查（专属优惠非必填）
    const firstRow = rows[0] || {}
    const existingCols = Object.keys(firstRow)
    const mappedCols = [...new Set(existingCols.map(k => cols[k] || k))]
    const requiredCols = ['room_number', 'floor', 'available_from', 'status']
    const cnMap = { room_number: '房号', floor: '楼层', available_from: '可入住时间', status: '状态' }
    const missingCols = requiredCols.filter(c => !mappedCols.includes(c))
    if (missingCols.length) {
      ElMessage.error('文件缺少必填列：' + missingCols.map(c => cnMap[c] || c).join('、') + '，请补充后重新上传')
      return
    }

    const statusMap = { '可租': 'available', '维护中': 'maintenance', '已下线': 'offline', 'available': 'available', 'maintenance': 'maintenance', 'offline': 'offline' }
    batchRows.value = rows.map((r, i) => {
      const mapped = {}
      for (const [k, v] of Object.entries(r)) {
        const key = cols[k] || k
        mapped[key] = (v !== null && v !== undefined) ? String((key === 'available_from') ? excelDateToStr(v) : v).trim() : ''
      }
      const errors = []
      if (!mapped.room_number) errors.push('缺少房号')
      if (!mapped.floor && mapped.floor !== 0) errors.push('缺少楼层')
      else if (isNaN(Number(mapped.floor))) errors.push('楼层格式错误：' + mapped.floor)
      if (!mapped.available_from) errors.push('缺少可入住时间')
      if (!mapped.status) errors.push('缺少状态')
      else if (!statusMap[mapped.status]) errors.push('状态值无效：' + mapped.status + '（可填：可租/维护中/已下线）')
      // special_discount is free text, no validation needed
      mapped._rowIdx = i
      mapped._error = errors.length ? '第' + (i + 2) + '行: ' + errors.join('；') : null
      mapped._status = statusMap[mapped.status] || ''
      return mapped
    })

    // 批量内查重（同文件内房号重复）
    const seen = {}
    batchRows.value.forEach((r, idx) => {
      if (r._error) return
      const rn = String(r.room_number || '').trim()
      if (!rn) return
      if (seen[rn] !== undefined) {
        const prevIdx = seen[rn]
        const msg = '；房号「' + rn + '」重复（第' + (prevIdx + 2) + '行也出现）'
        batchRows.value[prevIdx]._error = (batchRows.value[prevIdx]._error || '') + msg
        r._error = (r._error || '') + msg
      } else { seen[rn] = idx }
    })
  } catch { ElMessage.error('文件解析失败，请确认文件格式正确') }
}

async function doBatchImport() {
  if (!roomForm.unit_type_id) { ElMessage.warning('请先在单个上传tab中选择公寓和户型'); return }
  const valid = batchRows.value.filter(r => !r._error)
  if (!valid.length) { ElMessage.warning('没有可导入的有效行'); return }
  batchImporting.value = true

  // 逐条查重（与数据库已有房间比对）
  const toImport = []
  for (const r of valid) {
    try {
      const rn = String(r.room_number || '').trim()
      const params = { unit_type_id: roomForm.unit_type_id, room_number: rn }
      const check = await api.get('/rooms/check-duplicate', { params })
      if (check.data.duplicate) {
        r._error = (r._error || '') + '；房号「' + rn + '」在当前户型下已存在'
        continue
      }
      toImport.push(r)
    } catch { toImport.push(r) }
  }

  if (!toImport.length) { ElMessage.warning('所有有效行均与已有房间重复，无法导入'); batchImporting.value = false; return }

  let ok = 0; let fail = 0
  for (const r of toImport) {
    try {
      await api.post('/rooms', {
        unit_type_id: roomForm.unit_type_id,
        landlord_id: authStore.user?.id,
        room_number: String(r.room_number || '').trim(),
        building_block: r.building_block != null && r.building_block !== '' ? String(r.building_block).trim() : null,
        floor: r.floor != null && r.floor !== '' ? Number(r.floor) : null,
        special_discount: r.special_discount || null,
        available_from: r.available_from && r.available_from !== '' && r.available_from !== 'None' ? String(r.available_from).slice(0, 10) : null,
        status: r._status || 'available',
      })
      ok++
    } catch (e) {
      fail++
      if (fail <= 3) {  // 只显示前3条错误，避免弹窗刷屏
        const errMsg = e?.response?.data?.detail || e?.response?.data?.error?.message || '未知错误'
        ElMessage.error('第' + (batchRows.value.indexOf(r) + 2) + '行导入失败: ' + (typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg).slice(0, 100)))
      }
    }
  }
  batchImporting.value = false
  ElMessage.success(`导入完成：成功 ${ok} 条，失败 ${fail} 条`)
  if (fail > 0 && batchRows.value.some(r => r._error)) {
    ElMessage.warning(`${batchRows.value.filter(r => r._error).length} 行有校验错误，请检查`)
  }
  batchFile.value = null; batchRows.value = []
  loadRooms()
}

// ═══ 数据加载 ═══
onMounted(() => { loadBuildings(); loadUnitTypes(); loadRooms() })
async function loadBuildings() { try { buildings.value = await buildingService.list({ limit: 200 }) } catch { /* */ } }
async function loadUnitTypes() {
  try {
    const params: any = { page_size: 500 }
    if (filterInstituteId.value) params.institute_id = filterInstituteId.value
    const r = await api.get('/unit-types', { params }); allUnitTypes.value = r.data.items || []
    // 自动展开有户型的公寓
    expandedBuildings.value = new Set(buildings.value.filter(b => getUnitTypes(b.id).length > 0).map(b => b.id))
  } catch { /* */ }
}
async function loadRooms() {
  loading.value = true
  try {
    const params: any = { page_size: 500 }
    if (filterUnitTypeId.value) params.unit_type_id = filterUnitTypeId.value
    else if (filterInstituteId.value) params.institute_id = filterInstituteId.value
    const r = await api.get('/rooms', { params }); allRooms.value = r.data.items || []
    // 自动展开有房间的户型
    const utIds = new Set(allRooms.value.map(r => r.unit_type_id))
    expandedUnits.value = new Set([...expandedUnits.value, ...utIds])
  } catch { /* */ }
  finally { loading.value = false }
}

watch(viewMode, (v) => { if (v === 'trash') loadTrashRooms() })

async function loadTrashRooms() {
  trashLoading.value = true
  try {
    const r = await api.get('/rooms/recycle-bin', { params: { page_size: 2000 } })
    trashRooms.value = r.data.items || []
    trashTotal.value = r.data.total || 0
  } catch (e: any) {
    console.error('loadTrashRooms failed:', e?.response?.status, e?.response?.data)
  } finally { trashLoading.value = false }
}

function fmtTime(iso: string): string {
  try { return new Date(iso).toLocaleString('zh-CN', { hour12: false }) } catch { return iso }
}

async function restoreRoom(id: number) {
  try {
    await api.post('/rooms/' + id + '/restore')
    ElMessage.success('已恢复')
    loadTrashRooms()
    loadRooms()
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.response?.data?.error?.message || e?.message || '恢复失败'
    ElMessage.error(typeof msg === 'string' ? msg : '恢复失败')
  }
}

async function hardDeleteRoom(id: number) {
  try {
    await api.delete('/rooms/' + id + '/hard')
    ElMessage.success('已永久删除')
    loadTrashRooms()
    loadRooms()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}
</script>

<style scoped>
h2 { font-size: 22px; color: #303133; margin: 0 }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px }

.building-card { border-left: 3px solid var(--primary, #FF6B35) }

.level-header {
  display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none;
  padding: 6px 0; border-radius: 6px; transition: background 0.15s;
}
.level-header:hover { background: #fafafa }
.level-header.sub { margin-left: 0; padding-left: 8px; border-left: 2px solid #e4e7ed }
.level-icon { font-size: 18px }
.level-name { font-weight: 600; font-size: 14px; color: #303133 }
.arrow { font-size: 11px; color: #909399; transition: transform 0.2s }
.arrow.rotated { transform: rotate(180deg) }

.drop-zone {
  border: 2px dashed #dcdfe6; border-radius: 8px; padding: 32px; text-align: center;
  cursor: pointer; transition: all 0.2s;
}
.drop-zone:hover, .drop-zone.active { border-color: var(--primary, #FF6B35); background: #fff8f2 }

/* ═══════════ 房间卡片 ═══════════ */
.room-cards {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.room-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 10px 16px;
  transition: background 0.15s, border-color 0.15s;
}

.room-card:hover {
  background: #fafbfc;
  border-color: #d0d5dd;
}

.room-card.selected {
  background: #fff9f6;
  border-color: #FF6B35;
}

/* 选择框 */
.rmc-check {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

/* 房间标识 */
.rmc-id {
  width: 130px;
  flex-shrink: 0;
}

.rmc-room-number {
  font-size: 16px;
  font-weight: 700;
  color: #1a1a2e;
  line-height: 1.3;
}

.rmc-meta-line {
  display: flex;
  gap: 6px;
  margin-top: 2px;
}

.rmc-meta-tag {
  font-size: 12px;
  color: #909399;
}

/* 信息区 */
.rmc-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
}

.rmc-info-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.rmc-label {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.rmc-value {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.rmc-value.highlight {
  color: #e6a23c;
  font-weight: 600;
}

/* 状态 */
.rmc-status {
  flex-shrink: 0;
  min-width: 60px;
  display: flex;
  justify-content: center;
}

/* 操作按钮 */
.rmc-actions {
  flex-shrink: 0;
  display: flex;
  gap: 6px;
}

/* 回收站房间专属归属信息 */
.trash-room-card {
  align-items: center;
}
.trash-room-id {
  width: 130px;
}
.trash-room-belong {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.trash-belong-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.trash-belong-icon {
  font-size: 13px;
  width: 22px;
  text-align: center;
  flex-shrink: 0;
}
.trash-belong-text {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}
.trash-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .room-card {
    flex-wrap: wrap;
    gap: 8px;
    padding: 12px;
  }
  .rmc-id { width: 100% }
  .rmc-info { width: 100% }
  .trash-room-belong { width: 100% }
  .rmc-actions { width: 100%; justify-content: flex-end }
}
</style>
