<template>
  <div class="admin-users" v-loading="loading">
    <h2>用户管理</h2>

    <el-table :data="users" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="email" label="邮箱" />
      <el-table-column prop="phone" label="手机号" />
      <el-table-column label="角色" width="110">
        <template #default="{ row }">
          <el-select
            :model-value="row.role"
            size="small"
            @change="(val: string) => handleRoleChange(row.id, val)"
          >
            <el-option label="租客" value="tenant" />
            <el-option label="房东" value="landlord" />
            <el-option label="BD经理" value="bd_manager" />
            <el-option label="维修师傅" value="maintenance_worker" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
            {{ row.status === 'active' ? '正常' : row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="注册时间" width="140">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { adminService } from '@/services/admin'
import { userService } from '@/services/user'
import type { User } from '@/types/user'

const users = ref<User[]>([])
const loading = ref(false)

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

async function fetchUsers() {
  loading.value = true
  try {
    users.value = await userService.list()
  } finally {
    loading.value = false
  }
}

async function handleRoleChange(userId: number, role: string) {
  try {
    await adminService.updateUserRole(userId, role)
    ElMessage.success('角色已更新')
    await fetchUsers()
  } catch {
    ElMessage.error('更新失败')
  }
}

onMounted(fetchUsers)
</script>

<style scoped>
.admin-users {
  max-width: 1100px;
  margin: 0 auto;
}

.admin-users h2 {
  font-size: 22px;
  color: #303133;
  margin-bottom: 20px;
}
</style>
