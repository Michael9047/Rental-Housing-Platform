<template>
  <div class="auth-page">
    <el-card class="auth-card" shadow="always">
      <template #header>
        <h2 class="auth-title">注册</h2>
      </template>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" :prefix-icon="User" />
        </el-form-item>
        <el-form-item label="邮箱（选填）" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" :prefix-icon="Message" />
        </el-form-item>
        <el-form-item label="手机号（选填）" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" :prefix-icon="Phone" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="至少8位密码" :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" placeholder="请再次输入密码" :prefix-icon="Lock" show-password @keyup.enter="handleRegister" />
        </el-form-item>
        <el-form-item label="身份" prop="role">
          <el-radio-group v-model="form.role">
            <el-radio value="tenant">租客</el-radio>
            <el-radio value="landlord">房东</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <el-button type="primary" :loading="loading" class="submit-btn" @click="handleRegister">
        注册
      </el-button>

      <div class="auth-footer">
        已有账号？<router-link to="/login">立即登录</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, Message, Phone } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  email: '',
  phone: '',
  password: '',
  confirmPassword: '',
  role: 'tenant' as 'tenant' | 'landlord',
})

const validateConfirmPassword = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (value !== form.password) {
    callback(new Error('两次密码输入不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少8位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

async function handleRegister() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  loading.value = true
  try {
    await authStore.register({
      username: form.username,
      password: form.password,
      email: form.email || undefined,
      phone: form.phone || undefined,
      role: form.role,
    })
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (err: any) {
    const detail = err?.response?.data?.detail
    if (detail && typeof detail === 'string') {
      ElMessage.error(detail)
    } else {
      ElMessage.error('注册失败，请重试')
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.auth-card { width: 420px; }
.auth-title { text-align: center; font-size: 22px; color: #303133; margin: 0; }
.submit-btn { width: 100%; margin-bottom: 8px; }
.auth-footer { text-align: center; font-size: 14px; color: #909399; }
.auth-footer a { color: #409eff; text-decoration: none; }
</style>
