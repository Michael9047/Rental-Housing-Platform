<template>
  <div class="profile-page">
    <h2>个人中心</h2>

    <el-card shadow="never" class="profile-card">
      <template #header><span>基本信息</span></template>
      <el-form
        v-if="!editing"
        label-width="100px"
      >
        <el-form-item label="用户名">
          <span>{{ user?.username }}</span>
        </el-form-item>
        <el-form-item label="邮箱">
          <span>{{ user?.email || '未设置' }}</span>
        </el-form-item>
        <el-form-item label="手机号">
          <span>{{ user?.phone || '未设置' }}</span>
        </el-form-item>
        <el-form-item label="身份">
          <el-tag :type="user?.role === 'admin' ? 'danger' : user?.role === 'landlord' ? 'warning' : 'info'">
            {{ roleLabels[user?.role || 'tenant'] }}
          </el-tag>
        </el-form-item>
        <el-form-item label="注册时间">
          <span>{{ user?.created_at ? formatDate(user.created_at) : '' }}</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="startEdit">编辑资料</el-button>
        </el-form-item>
      </el-form>

      <el-form
        v-else
        ref="formRef"
        :model="editForm"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="editForm.username" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="editForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="editForm.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="saveProfile">保存</el-button>
          <el-button @click="cancelEdit">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { userService } from '@/services/user'
import { storeToRefs } from 'pinia'
import type { UserRole } from '@/types/user'

const authStore = useAuthStore()
const { user } = storeToRefs(authStore)

const editing = ref(false)
const saving = ref(false)
const formRef = ref<FormInstance>()

const roleLabels: Record<UserRole, string> = {
  tenant: '租客',
  landlord: '房东',
  admin: '管理员',
}

const editForm = reactive({
  username: '',
  email: '',
  phone: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
}

function startEdit() {
  if (!user.value) return
  editForm.username = user.value.username
  editForm.email = user.value.email || ''
  editForm.phone = user.value.phone || ''
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function saveProfile() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const updated = await userService.updateMyProfile({
      username: editForm.username,
      email: editForm.email || undefined,
      phone: editForm.phone || undefined,
    })
    authStore.user = updated
    localStorage.setItem('user', JSON.stringify(updated))
    editing.value = false
    ElMessage.success('资料更新成功')
  } catch {
    // handled by interceptor
  } finally {
    saving.value = false
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

onMounted(async () => {
  await authStore.fetchCurrentUser()
})
</script>

<style scoped>
.profile-page {
  max-width: 700px;
  margin: 0 auto;
}

.profile-page h2 {
  font-size: 22px;
  color: #303133;
  margin-bottom: 20px;
}

.profile-card {
  margin-bottom: 20px;
}
</style>
