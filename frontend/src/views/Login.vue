<template>
  <div class="auth-page">
    <div class="auth-bg-decor" />
    <el-card class="auth-card" shadow="always">
      <div class="auth-logo">
        <span class="logo-icon">🏠</span>
        <span class="logo-text">AI全球公寓租赁</span>
      </div>
      <h2 class="auth-title">欢迎回来</h2>
      <p class="auth-subtitle">登录您的账号，开始智能找房</p>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
      >
        <el-form-item label="用户名或邮箱" prop="username_or_email">
          <el-input
            v-model="form.username_or_email"
            placeholder="请输入用户名或邮箱"
            :prefix-icon="User"
            size="large"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
            size="large"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
      </el-form>

      <el-button
        type="primary"
        :loading="loading"
        size="large"
        class="submit-btn"
        round
        @click="handleLogin"
      >
        登录
      </el-button>

      <el-divider>其他登录方式</el-divider>
      <el-button class="wechat-btn" @click="handleWechatLogin" :loading="wechatLoading" size="large" round>
        💚 微信登录
      </el-button>
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
const loading = ref(false)
const wechatLoading = ref(false)

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

  loading.value = true
  try {
    await authStore.login({
      username_or_email: form.username_or_email,
      password: form.password,
    })
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch {
    // error message handled by axios interceptor
  } finally {
    loading.value = false
  }
}

async function handleWechatLogin() {
  wechatLoading.value = true
  try {
    ElMessage.info('微信登录需要微信内置浏览器或小程序环境。请使用微信扫码或在微信中打开。')
  } finally {
    wechatLoading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #e8f4fd 0%, #d0e8fb 30%, #f0f2f5 60%, #e8f4fd 100%);
  position: relative;
}

.auth-bg-decor {
  position: absolute;
  top: -200px;
  right: -200px;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(64,158,255,0.08) 0%, transparent 70%);
  border-radius: 50%;
}

.auth-card {
  width: 420px;
  border-radius: var(--radius-lg) !important;
  position: relative;
}

.auth-logo {
  text-align: center;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.logo-icon { font-size: 28px; }

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--primary);
}

.auth-title {
  text-align: center;
  font-size: 22px;
  color: var(--text-primary);
  margin: 0 0 4px;
}

.auth-subtitle {
  text-align: center;
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 24px;
}

.submit-btn {
  width: 100%;
  font-weight: 600;
}

.wechat-btn {
  width: 100%;
  background: #07c160;
  border-color: #07c160;
  color: #fff;
}

.wechat-btn:hover {
  background: #06ad56;
  border-color: #06ad56;
  color: #fff;
}

.auth-footer {
  text-align: center;
  margin-top: 16px;
  font-size: 14px;
  color: var(--text-muted);
}

.auth-footer a {
  color: var(--primary);
  text-decoration: none;
  font-weight: 600;
}
</style>
