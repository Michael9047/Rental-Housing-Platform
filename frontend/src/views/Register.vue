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
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" :prefix-icon="Phone" />
        </el-form-item>
        <!-- 短信验证码（填写合法手机号后显示） -->
        <el-form-item v-if="form.phone && /^1[3-9]\d{9}$/.test(form.phone)" label="短信验证码" prop="sms_code">
          <div class="sms-row">
            <el-input
              v-model="form.sms_code"
              placeholder="请输入6位验证码"
              :prefix-icon="Message"
              maxlength="6"
              class="sms-input"
            />
            <el-button
              :type="smsBtnDisabled ? 'info' : 'primary'"
              :disabled="smsBtnDisabled"
              :loading="sendingSms"
              class="sms-btn"
              @click="handleSendSms"
            >
              {{ smsBtnText }}
            </el-button>
          </div>
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
import { reactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, Message, Phone } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { authService } from '@/services/auth'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)
const sendingSms = ref(false)
const smsCountdown = ref(0)
let countdownTimer: ReturnType<typeof setInterval> | null = null

const form = reactive({
  username: '',
  email: '',
  phone: '',
  sms_code: '',
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

const rules = computed<FormRules>(() => {
  const base: FormRules = {
    username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
    phone: [
      { required: true, message: '请输入手机号', trigger: 'blur' },
      { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' },
    ],
    password: [
      { required: true, message: '请输入密码', trigger: 'blur' },
      { min: 8, message: '密码至少8位', trigger: 'blur' },
    ],
    confirmPassword: [
      { required: true, message: '请确认密码', trigger: 'blur' },
      { validator: validateConfirmPassword, trigger: 'blur' },
    ],
  }
  // 填写了合法手机号时，验证码为必填
  if (form.phone && /^1[3-9]\d{9}$/.test(form.phone)) {
    base.sms_code = [
      { required: true, message: '请输入短信验证码', trigger: 'blur' },
      { len: 6, message: '验证码为6位数字', trigger: 'blur' },
    ]
  }
  return base
})

const smsBtnDisabled = computed(() => smsCountdown.value > 0 || sendingSms.value)
const smsBtnText = computed(() => {
  if (sendingSms.value) return '发送中...'
  if (smsCountdown.value > 0) return `${smsCountdown.value}s 后重发`
  return '发送验证码'
})

function startCountdown() {
  smsCountdown.value = 60
  countdownTimer = setInterval(() => {
    smsCountdown.value--
    if (smsCountdown.value <= 0) {
      if (countdownTimer) clearInterval(countdownTimer)
      countdownTimer = null
    }
  }, 1000)
}

async function handleSendSms() {
  const phone = (form.phone || '').trim()
  if (!phone || !/^1[3-9]\d{9}$/.test(phone)) {
    ElMessage.warning('请输入正确的手机号')
    return
  }
  sendingSms.value = true
  try {
    await authService.sendSmsCode({ phone })
    ElMessage.success('验证码已发送')
    startCountdown()
  } catch {
    // error handled by interceptor
  } finally {
    sendingSms.value = false
  }
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
      username: form.username.trim(),
      password: form.password,
      email: form.email?.trim() || undefined,
      phone: form.phone.trim() || undefined,
      sms_code: form.sms_code.trim() || undefined,
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

.sms-row {
  display: flex;
  gap: 12px;
}
.sms-input {
  flex: 1;
}
.sms-btn {
  min-width: 120px;
  flex-shrink: 0;
}
</style>
