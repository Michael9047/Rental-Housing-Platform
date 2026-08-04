<template>
  <div class="page-container">
    <div class="page-header">
      <h2>租客管理</h2>
      <div style="display:flex;gap:8px">
        <el-input v-model="keyword" placeholder="搜索姓名/电话/学校" clearable style="width:240px" @input="fetchList" @clear="fetchList" />
        <el-button type="primary" @click="openDialog()">添加租客</el-button>
      </div>
    </div>

    <el-table :data="items" v-loading="loading" stripe empty-text="暂无租客">
      <el-table-column label="姓名" min-width="120">
        <template #default="{ row }">
          {{ (row.surname_pinyin || '') + (row.given_name_pinyin ? ' ' + row.given_name_pinyin : '') }}
        </template>
      </el-table-column>
      <el-table-column prop="phone" label="电话" width="140" />
      <el-table-column prop="school_name" label="学校" min-width="140" />
      <el-table-column label="租期" width="200">
        <template #default="{ row }">
          <span v-if="row.move_in_date || row.move_out_date">
            {{ row.move_in_date || '?' }} ~ {{ row.move_out_date || '?' }}
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="institute_name" label="所租公寓" min-width="140" />
      <el-table-column prop="unit_type_name" label="所租户型" min-width="140" />
      <el-table-column prop="room_number" label="房间号" width="100" />
      <el-table-column prop="housing_status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.housing_status === 'active'" type="success" size="small">在住</el-tag>
          <el-tag v-else-if="row.housing_status === 'notice_given'" type="warning" size="small">已通知退租</el-tag>
          <el-tag v-else-if="row.housing_status === 'moved_out'" type="info" size="small">已搬出</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button size="small" text type="danger" @click="handleDelete(row)">删除</el-button>
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/services/api'

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

async function fetchList() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize }
    if (keyword.value) params.keyword = keyword.value
    const r = await api.get('/tenants', { params })
    items.value = r.data.items
    total.value = r.data.total
  } catch { /* */ }
  finally { loading.value = false }
}

async function fetchBuildings() {
  try {
    const r = await api.get('/buildings', { params: { limit: 200 } })
    buildings.value = r.data.items || []
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
    ElMessage.error(e?.response?.data?.detail || '保存失败')
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
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}
</script>

<style scoped>
.page-container { max-width: 1200px; margin: 0 auto; padding: 24px }
h2 { font-size: 22px; color: #303133; margin: 0 }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px }
</style>
