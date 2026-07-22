<template>
  <div class="page-container">
    <div class="page-header">
      <h2>订单记录</h2>
      <div style="display:flex;gap:8px">
        <el-select v-model="filterStatus" placeholder="筛选状态" clearable style="width:120px" @change="fetchList">
          <el-option label="进行中" value="active" />
          <el-option label="已完成" value="completed" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
        <el-button type="primary" @click="openDialog()">添加订单</el-button>
      </div>
    </div>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="tenant_name" label="房客" width="100" />
      <el-table-column label="房间ID" width="80" show-overflow-tooltip>
        <template #default="{ row }">{{ row.room_id || '-' }}</template>
      </el-table-column>
      <el-table-column prop="start_date" label="开始日期" width="120" />
      <el-table-column prop="end_date" label="结束日期" width="120" />
      <el-table-column label="总额" width="100">
        <template #default="{ row }">¥{{ Number(row.total_amount).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column prop="deposit_status" label="押金状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="row.deposit_status==='paid'?'success':(row.deposit_status==='refunded'?'info':'warning')">
            {{ row.deposit_status==='paid'?'已付':(row.deposit_status==='refunded'?'已退':(row.deposit_status||'未付')) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag size="small">{{ row.status==='active'?'进行中':(row.status==='completed'?'已完成':'已取消') }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }"><el-button size="small" text type="primary" @click="openDialog(row)">编辑</el-button></template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑订单' : '添加订单'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="房间">
          <el-select v-model="form.room_id" filterable style="width:100%" placeholder="选择房间">
            <el-option v-for="r in rooms" :key="r.id" :label="`${r.institute_name || '—'} / ${r.unit_type_name || '—'} (ID:${r.id})`" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="房客">
          <el-select v-model="form.tenant_id" filterable style="width:100%" placeholder="选择房客">
            <el-option v-for="t in tenants" :key="t.id" :label="`${t.name} ${t.phone || ''}`" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="form.start_date" type="date" style="width:100%" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="form.end_date" type="date" style="width:100%" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="总额"><el-input-number v-model="form.total_amount" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="押金状态">
          <el-select v-model="form.deposit_status" style="width:100%">
            <el-option label="未付" value="unpaid" />
            <el-option label="已付" value="paid" />
            <el-option label="已退" value="refunded" />
          </el-select>
        </el-form-item>
        <el-form-item label="订单状态">
          <el-select v-model="form.status" style="width:100%">
            <el-option label="进行中" value="active" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="handleSave">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/services/api'

const items = ref<any[]>([]); const loading = ref(false)
const dialogVisible = ref(false); const editingId = ref<number | null>(null)
const filterStatus = ref('')
const rooms = ref<any[]>([]); const tenants = ref<any[]>([])
const form = ref({ room_id: 0, tenant_id: 0, start_date: '', end_date: '', total_amount: 0, deposit_status: 'unpaid', status: 'active' })

onMounted(() => { fetchList(); loadRooms(); loadTenants() })

async function fetchList() {
  loading.value = true
  try {
    const params: any = {}
    if (filterStatus.value) params.status = filterStatus.value
    const r = await api.get('/orders', { params }); items.value = r.data.items
  } catch { /* */ }
  finally { loading.value = false }
}

async function loadRooms() {
  try { const r = await api.get('/rooms', { params: { page_size: 200 } }); rooms.value = r.data.items || [] } catch { /* */ }
}

async function loadTenants() {
  try { const r = await api.get('/tenants', { params: { page_size: 200 } }); tenants.value = r.data.items || [] } catch { /* */ }
}

function openDialog(row?: any) {
  if (row) {
    editingId.value = row.id
    form.value = { ...row, start_date: row.start_date || '', end_date: row.end_date || '' }
  }
  else { editingId.value = null; form.value = { room_id: 0, tenant_id: 0, start_date: '', end_date: '', total_amount: 0, deposit_status: 'unpaid', status: 'active' } }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.room_id || !form.value.tenant_id) { ElMessage.warning('请选择房间和房客'); return }
  try {
    if (editingId.value) await api.patch('/orders/' + editingId.value, form.value)
    else await api.post('/orders', form.value)
    ElMessage.success('保存成功'); dialogVisible.value = false; fetchList()
  } catch { /* */ }
}
</script>

<style scoped>
h2 { font-size: 22px; color: #303133; margin: 0 }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px }
</style>
