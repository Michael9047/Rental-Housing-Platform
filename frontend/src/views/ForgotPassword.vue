<template>
  <div class="auth-page">
    <div class="auth-bg-decor" />
    <el-card class="auth-card" shadow="always">
      <div class="auth-logo">
        <span class="logo-icon">🏠</span>
        <span class="logo-text">AI全球公寓租赁</span>
      </div>
      <h2 class="auth-title">忘记密码</h2>
      <p class="auth-subtitle">输入注册邮箱，我们将发送重置链接</p>

      <!-- 发送成功提示 -->
      <el-result
        v-if="sent"
        icon="success"
        title="重置链接已发送"
        sub-title="请检查您的邮箱，点击邮件中的链接重置密码。链接有效期 30 分钟。"
      >
        <template #extra>
          <el-button type="primary" @click="$router.push('/login')">返回登录</el-button>
        </template>
      </el-result>

      <!-- 表单 -->
      <el-form
        v-else
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
      >
        <el-form-item label="邮箱地址" prop="email">
          <el-input
            v-model="form.email"
            placeholder="请输入注册时使用的邮箱"
            :prefix-icon="Message"
            size="large"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>

        <el-button
          type="primary"
          :loading="loading"
          size="large"
          class="submit-btn"
          round
          @click="handleSubmit"
        >
          发送重置链接
        </el-button>
      </el-form>

      <div class="auth-footer">
        <router-link to="/login">← 返回登录</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { Message } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { authService } from '@/services/auth'

const formRef = ref<FormInstance>()
const loading = ref(false)
const sent = ref(false)

const form = reactive({
  email: '',
})

const rules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
}

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authService.forgotPassword({ email: form.email })
    sent.value = true
  } catch {
    // error handled by interceptor — 但仍展示成功页面防止邮箱枚举
    sent.value = true
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
.logo-text { font-size: 16px; font-weight: 700; color: var(--primary); }

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
  margin-top: 4px;
}

.auth-footer {
  text-align: center;
  margin-top: 16px;
  font-size: 14px;
}

.auth-footer a {
  color: var(--primary);
  text-decoration: none;
  font-weight: 600;
}
</style>
