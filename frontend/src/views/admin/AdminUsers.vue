<template>
  <div class="admin-users" v-loading="loading">
    <div class="page-head">
      <h2>用户管理</h2>
      <el-button @click="fetchUsers">刷新</el-button>
    </div>

    <div class="query-bar">
      <el-input
        v-model="queryText"
        clearable
        placeholder="查询用户名、邮箱、手机号"
        @keyup.enter="searchUsers"
        @clear="searchUsers"
      />
      <el-button type="primary" @click="searchUsers">查询</el-button>
    </div>

    <el-tabs v-model="roleFilter" @tab-change="syncRoleQuery">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane label="管理员" name="admin" />
      <el-tab-pane label="租客" name="tenant" />
      <el-tab-pane label="房东" name="landlord" />
      <el-tab-pane label="维修工" name="maintenance_worker" />
    </el-tabs>

    <div class="table-wrap">
      <el-table :data="users" stripe class="data-table">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" min-width="120" show-overflow-tooltip />
        <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip />
        <el-table-column prop="phone" label="手机号" min-width="130" show-overflow-tooltip />
        <el-table-column label="角色" width="130">
          <template #default="{ row }">
            <el-select
              :model-value="row.role"
              size="small"
              @change="(val: string) => handleRoleChange(row.id, val)"
            >
              <el-option label="管理员" value="admin" />
              <el-option label="租客" value="tenant" />
              <el-option label="房东" value="landlord" />
              <el-option label="维修工" value="maintenance_worker" />
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
        <el-table-column label="注册时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { adminService } from '@/services/admin'
import { userService } from '@/services/user'
import type { User } from '@/types/user'

const route = useRoute()
const router = useRouter()
const users = ref<User[]>([])
const loading = ref(false)
const allowedRoles = new Set(['admin', 'tenant', 'landlord', 'maintenance_worker'])
const roleFilter = ref(typeof route.query.role === 'string' && allowedRoles.has(route.query.role) ? route.query.role : 'all')
const queryText = ref(typeof route.query.q === 'string' ? route.query.q : '')

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('zh-CN')
}

async function fetchUsers() {
  loading.value = true
  try {
    users.value = await userService.list({
      limit: 100,
      q: queryText.value.trim() || undefined,
      role: roleFilter.value === 'all' ? undefined : roleFilter.value,
    })
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

function syncRoleQuery() {
  router.replace({
    path: '/admin/users',
    query: {
      ...(roleFilter.value === 'all' ? {} : { role: roleFilter.value }),
      ...(queryText.value.trim() ? { q: queryText.value.trim() } : {}),
    },
  })
  fetchUsers()
}

function searchUsers() {
  router.replace({
    path: '/admin/users',
    query: {
      ...(roleFilter.value === 'all' ? {} : { role: roleFilter.value }),
      ...(queryText.value.trim() ? { q: queryText.value.trim() } : {}),
    },
  })
  fetchUsers()
}

watch(
  () => [route.query.role, route.query.q],
  ([role, q]) => {
    roleFilter.value = typeof role === 'string' && allowedRoles.has(role) ? role : 'all'
    queryText.value = typeof q === 'string' ? q : ''
  },
)

onMounted(fetchUsers)
</script>

<style scoped>
.admin-users {
  box-sizing: border-box;
  width: 100%;
}

.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.query-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  width: min(100%, 680px);
  margin-bottom: 12px;
}

.query-bar .el-input {
  min-width: 180px;
}

.table-wrap {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  box-sizing: border-box;
  overflow-x: auto;
  width: 100%;
}

.data-table {
  min-width: 900px;
  width: 100%;
}

.admin-users h2 {
  font-size: 22px;
  color: #303133;
  margin: 0;
}

@media (max-width: 640px) {
  .page-head,
  .query-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .query-bar {
    width: 100%;
  }
}
</style>
