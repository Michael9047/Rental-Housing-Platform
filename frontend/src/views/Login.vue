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

      <el-divider>其他登录方式</el-divider>
      <div class="sso-buttons">
        <el-button class="wechat-btn" @click="handleWechatLogin" :loading="wechatLoading">
          <el-icon><ChatDotRound /></el-icon> 微信登录
        </el-button>
      </div>
      <div class="auth-footer">
        还没有账号？<router-link to="/register">立即注册</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock, ChatDotRound } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const wechatLoading = ref(false)

async function handleWechatLogin() {
  wechatLoading.value = true
  try {
    // In browser environment, use WeChat OAuth redirect
    // For demo/development, show a message explaining the flow
    ElMessage.info('微信登录需要微信内置浏览器或小程序环境。请使用微信扫码或在微信中打开。')
  } finally {
    wechatLoading.value = false
  }
}
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

.sso-buttons {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
}

.wechat-btn {
  background: #07c160;
  border-color: #07c160;
  color: #fff;
  width: 100%;
}

.wechat-btn:hover {
  background: #06ad56;
  border-color: #06ad56;
  color: #fff;
}

.auth-divider {
  margin: 20px 0;
}

.auth-footer a {
  color: #409eff;
  text-decoration: none;
}
</style>
