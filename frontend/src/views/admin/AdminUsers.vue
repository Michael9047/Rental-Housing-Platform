<template>
  <div class="admin-users" v-loading="loading">
    <div class="page-head">
      <h2>用户管理</h2>
      <div class="page-actions">
        <el-button @click="fetchUsers">刷新</el-button>
        <el-button type="primary" @click="openCreateDialog">创建账户</el-button>
      </div>
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
      <el-tab-pane label="BM/公寓经理" name="landlord" />
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
              <el-option label="BM/公寓经理" value="landlord" />
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

    <el-dialog v-model="createDialogVisible" title="创建内部账户" width="min(92vw, 520px)" destroy-on-close>
      <el-alert
        title="BM/公寓经理在当前数据库中继续使用 landlord 角色。"
        type="info"
        :closable="false"
        show-icon
        class="role-note"
      />
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="用户名" required>
          <el-input v-model.trim="createForm.username" maxlength="100" autocomplete="off" />
        </el-form-item>
        <el-form-item label="初始密码" required>
          <el-input
            v-model="createForm.password"
            type="password"
            show-password
            maxlength="128"
            autocomplete="new-password"
            placeholder="至少 8 位"
          />
        </el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="createForm.role" class="full-width">
            <el-option label="BM/公寓经理" value="landlord" />
            <el-option label="维修工" value="maintenance_worker" />
            <el-option label="租客" value="tenant" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model.trim="createForm.email" maxlength="255" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model.trim="createForm.phone" maxlength="32" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createAccount">创建账户</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminService } from '@/services/admin'
import { userService } from '@/services/user'
import { useAuthStore } from '@/stores/auth'
import type { AdminUserCreateInput, User } from '@/types/user'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const users = ref<User[]>([])
const loading = ref(false)
const creating = ref(false)
const createDialogVisible = ref(false)
const createForm = reactive<AdminUserCreateInput>({
  username: '',
  password: '',
  email: '',
  phone: '',
  role: 'landlord',
})
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
    const target = users.value.find((user) => user.id === userId)
    const roleLabel = ({
      admin: '管理员',
      tenant: '租客',
      landlord: 'BM/公寓经理',
      maintenance_worker: '维修工',
    } as Record<string, string>)[role] || role
    const selfWarning = userId === authStore.user?.id
      ? '这是你当前登录的账户，修改后可能立即失去管理员权限。'
      : ''
    await ElMessageBox.confirm(
      `确认将“${target?.username || userId}”修改为${roleLabel}？${selfWarning}`,
      '确认修改角色',
      { type: selfWarning ? 'error' : 'warning', confirmButtonText: '确认修改' },
    )
    await adminService.updateUserRole(userId, role)
    ElMessage.success('角色已更新')
    await fetchUsers()
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error?.response?.data?.detail || '更新失败')
  }
}

function resetCreateForm() {
  Object.assign(createForm, { username: '', password: '', email: '', phone: '', role: 'landlord' })
}

function openCreateDialog() {
  resetCreateForm()
  createDialogVisible.value = true
}

async function createAccount() {
  if (!createForm.username || createForm.password.length < 8) {
    ElMessage.warning('请填写用户名和至少 8 位的初始密码')
    return
  }
  if (createForm.role === 'admin') {
    try {
      await ElMessageBox.confirm('新账户将拥有完整管理员权限，确认继续？', '高权限账户确认', {
        type: 'warning',
        confirmButtonText: '确认创建',
      })
    } catch {
      return
    }
  }

  creating.value = true
  try {
    await adminService.createUser({
      username: createForm.username,
      password: createForm.password,
      role: createForm.role,
      ...(createForm.email ? { email: createForm.email } : {}),
      ...(createForm.phone ? { phone: createForm.phone } : {}),
    })
    ElMessage.success('账户已创建，请安全告知员工初始密码')
    createDialogVisible.value = false
    await fetchUsers()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '创建账户失败')
  } finally {
    creating.value = false
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

.page-actions {
  display: flex;
  gap: 8px;
}

.role-note {
  margin-bottom: 16px;
}

.full-width {
  width: 100%;
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
