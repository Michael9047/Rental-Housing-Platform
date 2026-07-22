<template>
  <div class="page-container">
    <div class="page-header">
      <h2>房客管理</h2>
      <div style="display:flex;gap:8px">
        <el-input v-model="keyword" placeholder="搜索姓名/电话" clearable style="width:220px" @input="fetchList" @clear="fetchList" />
        <el-button type="primary" @click="openDialog()">添加房客</el-button>
      </div>
    </div>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="name" label="姓名" min-width="100" />
      <el-table-column prop="phone" label="电话" width="140" />
      <el-table-column prop="email" label="邮箱" width="180" />
      <el-table-column prop="id_number" label="证件号" width="180" />
      <el-table-column prop="emergency_contact" label="紧急联系人" width="140" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }"><el-button size="small" text type="primary" @click="openDialog(row)">编辑</el-button></template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑房客' : '添加房客'" width="400px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="姓名" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="电话"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="证件号"><el-input v-model="form.id_number" /></el-form-item>
        <el-form-item label="紧急联系人"><el-input v-model="form.emergency_contact" /></el-form-item>
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
const keyword = ref('')
const form = ref({ name: '', phone: '', email: '', id_number: '', emergency_contact: '' })

onMounted(() => fetchList())

async function fetchList() {
  loading.value = true
  try {
    const params: any = {}
    if (keyword.value) params.keyword = keyword.value
    const r = await api.get('/tenants', { params })
    items.value = r.data.items
  } catch { /* */ }
  finally { loading.value = false }
}

function openDialog(row?: any) {
  if (row) { editingId.value = row.id; form.value = { ...row } }
  else { editingId.value = null; form.value = { name: '', phone: '', email: '', id_number: '', emergency_contact: '' } }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.name.trim()) { ElMessage.warning('请输入姓名'); return }
  try {
    if (editingId.value) await api.patch('/tenants/' + editingId.value, form.value)
    else await api.post('/tenants', form.value)
    ElMessage.success('保存成功'); dialogVisible.value = false; fetchList()
  } catch { /* */ }
}
</script>

<style scoped>
h2 { font-size: 22px; color: #303133; margin: 0 }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px }
</style>
