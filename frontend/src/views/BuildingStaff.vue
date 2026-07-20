<template>
  <div class="page-container">
    <div class="page-header"><h2>公寓人员配置</h2></div>
    <el-button type="primary" @click="openDialog()" style="margin-bottom:16px">添加人员</el-button>
    <el-table :data="staff" v-loading="loading" stripe>
      <el-table-column prop="name" label="姓名" />
      <el-table-column prop="role" label="角色" width="100">
        <template #default="{ row }">{{ {manager:'负责人',sales:'推销员',staff:'员工'}[row.role] || row.role }}</template>
      </el-table-column>
      <el-table-column prop="phone" label="联系电话" width="140" />
      <el-table-column prop="notes" label="备注" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button size="small" text type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑人员' : '添加人员'" width="400px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role">
            <el-option label="负责人" value="manager" />
            <el-option label="员工" value="staff" />
            <el-option label="推销员" value="sales" />
          </el-select>
        </el-form-item>
        <el-form-item label="电话"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/services/api'

const route = useRoute()
const instituteId = Number(route.params.id)
const staff = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const form = ref({ name: '', role: 'staff', phone: '', notes: '' })

onMounted(() => fetchStaff())

async function fetchStaff() {
  loading.value = true
  try {
    const r = await api.get('/buildings/' + instituteId + '/staff', {
      params: { _t: Date.now() },
      headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' },
    })
    staff.value = Array.isArray(r.data) ? r.data : []
  } catch { staff.value = [] }
  finally { loading.value = false }
}

function openDialog(row?: any) {
  if (row) { editingId.value = row.id; form.value = { name: row.name, role: row.role, phone: row.phone || '', notes: row.notes || '' } }
  else { editingId.value = null; form.value = { name: '', role: 'staff', phone: '', notes: '' } }
  dialogVisible.value = true
}

async function handleSave() {
  saving.value = true
  try {
    if (editingId.value) {
      await api.patch('/buildings/' + instituteId + '/staff/' + editingId.value, form.value)
    } else {
      await api.post('/buildings/' + instituteId + '/staff', form.value)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await fetchStaff()
  } catch { /* 拦截器已弹错误 */ }
  finally { saving.value = false }
}

async function handleDelete(row: any) {
  try { await api.delete('/buildings/' + instituteId + '/staff/' + row.id); ElMessage.success('已删除'); await fetchStaff() } catch { /* */ }
}
</script>
