<template>
  <BmPageShell eyebrow="BM WORKSPACE" title="租客管理" description="以当前租住关系为中心管理租客资料、房间分配和租期状态。">
    <template #actions>
      <el-button :icon="Refresh" :loading="loading" @click="fetchList">刷新</el-button>
      <el-button type="primary" @click="openDialog()">补录租客</el-button>
    </template>
    <template #summary><BmSummaryStrip :items="summaryItems" :active-key="statusFilter" @select="selectStatus" /></template>
    <template #toolbar>
      <div class="tenant-toolbar">
        <el-input v-model="keyword" :prefix-icon="Search" placeholder="搜索姓名、电话或学校" clearable @keyup.enter="search" @clear="search" />
        <el-select v-model="buildingFilter" clearable placeholder="全部公寓">
          <el-option v-for="building in buildings" :key="building.id" :label="building.name_cn || building.name" :value="building.id" />
        </el-select>
        <el-button type="primary" @click="search">搜索</el-button>
        <span class="filter-result">当前显示 {{ displayedItems.length }} 人</span>
      </div>
    </template>

    <el-table :data="displayedItems" v-loading="loading" stripe empty-text="当前筛选条件下暂无租客" table-layout="fixed" class="tenant-table">
      <el-table-column label="姓名" width="110">
        <template #default="{ row }">
          {{ (row.surname_pinyin || '') + (row.given_name_pinyin ? ' ' + row.given_name_pinyin : '') }}
        </template>
      </el-table-column>
      <el-table-column prop="phone" label="电话" width="120" />
      <el-table-column prop="school_name" label="学校" width="110" show-overflow-tooltip />
      <el-table-column label="租期" width="150">
        <template #default="{ row }">
          <span v-if="row.move_in_date || row.move_out_date">
            {{ row.move_in_date || '?' }} ~ {{ row.move_out_date || '?' }}
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="institute_name" label="公寓" width="110" show-overflow-tooltip />
      <el-table-column prop="unit_type_name" label="户型" width="100" show-overflow-tooltip />
      <el-table-column prop="room_number" label="房号" width="70" />
      <el-table-column prop="housing_status" label="状态" width="90">
        <template #default="{ row }">
          <BmStatusTag v-if="row.housing_status" domain="tenant" :status="row.housing_status" size="small" />
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="108" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog(row)">查看 / 编辑</el-button>
          <el-dropdown trigger="click" @command="handleDelete(row)"><el-button text>更多</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="archive">移除租客</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > pageSize"
      v-model:current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="prev, pager, next"
      @current-change="fetchList"
      style="margin-top:20px;justify-content:center"
    />

    <!-- 添加/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑租客' : '添加租客'" width="520px" @close="resetForm">
      <el-form :model="form" label-width="100px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="姓（拼音）" required>
              <el-input v-model="form.surname_pinyin" placeholder="如 WANG" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名（拼音）" required>
              <el-input v-model="form.given_name_pinyin" placeholder="如 Xiaoming" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="中文全名">
          <el-input v-model="form.chinese_name" placeholder="选填" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="学校">
          <el-input v-model="form.school_name" />
        </el-form-item>
        <el-form-item label="选择公寓">
          <el-select v-model="form.institute_id" placeholder="先选公寓" clearable filterable style="width:100%" @change="onBuildingChange">
            <el-option v-for="b in buildings" :key="b.id" :label="b.name_cn || b.name" :value="b.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="分配户型">
          <el-select v-model="form.current_unit_type_id" placeholder="选择户型" clearable filterable style="width:100%" :disabled="!form.institute_id">
            <el-option v-for="ut in filteredUnitTypes" :key="ut.id" :label="ut.name" :value="ut.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="房间号">
          <el-input v-model="form.room_number" placeholder="如 A-301" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="入住日期">
              <el-date-picker v-model="form.move_in_date" type="date" placeholder="选择日期" style="width:100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="退租日期">
              <el-date-picker v-model="form.move_out_date" type="date" placeholder="选择日期" style="width:100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="居住状态">
          <el-select v-model="form.housing_status" style="width:100%">
            <el-option label="在住" value="active" />
            <el-option label="已通知退租" value="notice_given" />
            <el-option label="已搬出" value="moved_out" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </BmPageShell>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { toUserFriendly } from '@/services/api'
import BmPageShell from '@/components/bm/BmPageShell.vue'
import BmSummaryStrip, { type BmSummaryItem } from '@/components/bm/BmSummaryStrip.vue'
import BmStatusTag from '@/components/bm/BmStatusTag.vue'

const items = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const keyword = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const unitTypes = ref<any[]>([])
const buildings = ref<any[]>([])
const statusFilter = ref<'all'|'active'|'notice_given'|'moved_out'>('all')
const buildingFilter = ref<number|null>(null)

const displayedItems = computed(() => items.value.filter((item) => {
  if (statusFilter.value !== 'all' && item.housing_status !== statusFilter.value) return false
  if (buildingFilter.value) {
    const unitType = unitTypes.value.find((candidate) => candidate.id === item.current_unit_type_id)
    if (unitType?.institute_id !== buildingFilter.value) return false
  }
  return true
}))
const summaryItems = computed<BmSummaryItem[]>(() => [
  { key:'active', label:'在住', value:items.value.filter((item) => item.housing_status === 'active').length, note:'本页租客' },
  { key:'notice_given', label:'已通知退租', value:items.value.filter((item) => item.housing_status === 'notice_given').length, note:'本页租客' },
  { key:'moved_out', label:'已搬出', value:items.value.filter((item) => item.housing_status === 'moved_out').length, note:'本页租客' },
  { key:'all', label:'租客总数', value:total.value, note:'当前账号可见' },
])

const filteredUnitTypes = computed(() => {
  if (!form.value.institute_id) return []
  return unitTypes.value.filter(ut => ut.institute_id === form.value.institute_id)
})

const emptyForm = () => ({
  surname_pinyin: '', given_name_pinyin: '', chinese_name: '',
  phone: '', email: '', school_name: '',
  institute_id: null as number | null,
  current_unit_type_id: null as number | null,
  room_number: '',
  move_in_date: null as string | null,
  move_out_date: null as string | null,
  housing_status: 'active',
})

function onBuildingChange() {
  form.value.current_unit_type_id = null
}
const form = ref(emptyForm())

onMounted(() => { fetchList(); fetchBuildings(); fetchUnitTypes() })

function selectStatus(key:string) { statusFilter.value = key as typeof statusFilter.value }
function search() { page.value = 1; fetchList() }

async function fetchList() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize }
    if (keyword.value) params.keyword = keyword.value
    const r = await api.get('/tenants', { params })
    items.value = r.data.items
    total.value = r.data.total
  } catch (error: any) {
    items.value = []
    total.value = 0
    ElMessage.error(toUserFriendly(error) || '租客数据加载失败')
  }
  finally { loading.value = false }
}

async function fetchBuildings() {
  try {
    const r = await api.get('/buildings', { params: { limit: 200 } })
    buildings.value = Array.isArray(r.data) ? r.data : (r.data.items || [])
  } catch { /* */ }
}

async function fetchUnitTypes() {
  try {
    const r = await api.get('/unit-types', { params: { limit: 500 } })
    unitTypes.value = r.data.items || []
  } catch { /* */ }
}

function resetForm() {
  form.value = emptyForm()
  editingId.value = null
}

function openDialog(row?: any) {
  if (row) {
    editingId.value = row.id
    // 从 unitTypes 中找到对应户型，反查 institute_id
    const ut = unitTypes.value.find((u: any) => u.id === row.current_unit_type_id)
    form.value = {
      surname_pinyin: row.surname_pinyin || '',
      given_name_pinyin: row.given_name_pinyin || '',
      chinese_name: row.chinese_name || '',
      phone: row.phone || '',
      email: row.email || '',
      school_name: row.school_name || '',
      institute_id: ut?.institute_id || null,
      current_unit_type_id: row.current_unit_type_id || null,
      room_number: row.room_number || '',
      move_in_date: row.move_in_date || null,
      move_out_date: row.move_out_date || null,
      housing_status: row.housing_status || 'active',
    }
  } else {
    resetForm()
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.surname_pinyin.trim() || !form.value.given_name_pinyin.trim()) {
    ElMessage.warning('请填写姓和名（拼音）')
    return
  }
  try {
    // 去掉仅前端使用的 institute_id，不发给后端
    const { institute_id, ...payload } = form.value
    if (editingId.value) {
      await api.patch('/tenants/' + editingId.value, payload)
    } else {
      await api.post('/tenants', payload)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    fetchList()
    fetchUnitTypes() // 刷新户型列表（可租数量可能变了）
  } catch (e: any) {
    ElMessage.error(toUserFriendly(e))
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm('确定要删除该租客吗？删除后对应户型可租数量将恢复。', '确认删除', { type: 'warning' })
  } catch { return }
  try {
    await api.delete('/tenants/' + row.id)
    ElMessage.success('已删除')
    fetchList()
    fetchUnitTypes()
  } catch (e: any) {
    ElMessage.error(toUserFriendly(e))
  }
}
</script>

<style scoped>
.tenant-toolbar { display: grid; grid-template-columns: minmax(260px, 1fr) 220px auto auto; align-items: center; gap: 12px; }
.tenant-toolbar .el-input { max-width: 420px; }
.filter-result { color: var(--text-muted); font-size: 13px; white-space: nowrap; }
.tenant-table { width: 100%; overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius); }
@media (max-width: 760px) { .tenant-toolbar { grid-template-columns: 1fr; } }
</style>
