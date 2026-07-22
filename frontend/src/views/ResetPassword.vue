<template>
  <div class="auth-page">
    <div class="auth-bg-decor" />
    <el-card class="auth-card" shadow="always">
      <div class="auth-logo">
        <span class="logo-icon">🏠</span>
        <span class="logo-text">AI全球公寓租赁</span>
      </div>
      <h2 class="auth-title">重置密码</h2>
      <p class="auth-subtitle">请设置您的新密码</p>

      <!-- 成功 -->
      <el-result
        v-if="done"
        icon="success"
        title="密码已重置"
        sub-title="您的新密码已设置成功，请使用新密码登录。"
      >
        <template #extra>
          <el-button type="primary" @click="$router.push('/login')">前往登录</el-button>
        </template>
      </el-result>

      <!-- Token 无效 -->
      <el-result
        v-else-if="tokenError"
        icon="error"
        title="链接无效或已过期"
        sub-title="重置链接已失效（有效期 30 分钟），请重新申请。"
      >
        <template #extra>
          <el-button type="primary" @click="$router.push('/forgot-password')">重新申请</el-button>
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
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="form.new_password"
            type="password"
            placeholder="至少8位密码"
            :prefix-icon="Lock"
            show-password
            size="large"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>

        <el-form-item label="确认密码" prop="confirm_password">
          <el-input
            v-model="form.confirm_password"
            type="password"
            placeholder="请再次输入新密码"
            :prefix-icon="Lock"
            show-password
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
          重置密码
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { authService } from '@/services/auth'

const route = useRoute()
const formRef = ref<FormInstance>()
const loading = ref(false)
const done = ref(false)
const tokenError = ref(false)
const token = ref('')

const form = reactive({
  new_password: '',
  confirm_password: '',
})

const validateConfirm = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (value !== form.new_password) {
    callback(new Error('两次密码输入不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码至少8位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

onMounted(() => {
  token.value = (route.query.token as string) || ''
  if (!token.value) {
    tokenError.value = true
  }
})

async function handleSubmit() {
  if (!formRef.value || !token.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authService.resetPassword({
      token: token.value,
      new_password: form.new_password,
    })
    done.value = true
  } catch {
    // 400 = token 无效或过期
    tokenError.value = true
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
</style>
