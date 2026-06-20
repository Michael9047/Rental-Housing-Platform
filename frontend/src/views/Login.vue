<template>
  <div class="auth-page">
    <el-card class="auth-card" shadow="always">
      <template #header>
        <h2 class="auth-title">登录</h2>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item label="用户名或邮箱" prop="username_or_email">
          <el-input
            v-model="form.username_or_email"
            placeholder="请输入用户名或邮箱"
            :prefix-icon="User"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            native-type="submit"
            :loading="authStore.loading"
            class="submit-btn"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="auth-footer">
        还没有账号？<router-link to="/register">立即注册</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const formRef = ref<FormInstance>()

const form = reactive({
  username_or_email: '',
  password: '',
})

const rules: FormRules = {
  username_or_email: [{ required: true, message: '请输入用户名或邮箱', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    await authStore.login({
      username_or_email: form.username_or_email,
      password: form.password,
    })
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch {
    // Error already handled by interceptor
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

.auth-card {
  width: 400px;
}

.auth-title {
  text-align: center;
  font-size: 22px;
  color: #303133;
  margin: 0;
}

.submit-btn {
  width: 100%;
}

.auth-footer {
  text-align: center;
  font-size: 14px;
  color: #909399;
}

.auth-footer a {
  color: #409eff;
  text-decoration: none;
}
</style>
