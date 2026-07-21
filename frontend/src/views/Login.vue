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

      <!-- 登录方式切换 -->
      <div class="login-tabs">
        <span
          :class="['tab-item', { active: activeTab === 'password' }]"
          @click="switchTab('password')"
        >密码登录</span>
        <span
          :class="['tab-item', { active: activeTab === 'phone' }]"
          @click="switchTab('phone')"
        >手机登录</span>
      </div>

      <!-- ========== 密码登录表单 ========== -->
      <el-form
        v-if="activeTab === 'password'"
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-position="top"
      >
        <el-form-item label="用户名或邮箱" prop="username_or_email">
          <el-input
            v-model="passwordForm.username_or_email"
            placeholder="请输入用户名或邮箱"
            :prefix-icon="User"
            size="large"
            @keyup.enter="handlePasswordLogin"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="passwordForm.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
            size="large"
            @keyup.enter="handlePasswordLogin"
          />
        </el-form-item>

        <el-button
          type="primary"
          :loading="loading"
          size="large"
          class="submit-btn"
          round
          @click="handlePasswordLogin"
        >
          登录
        </el-button>

        <div class="forgot-row">
          <router-link to="/forgot-password">忘记密码？</router-link>
        </div>
      </el-form>

      <!-- ========== 手机登录表单 ========== -->
      <el-form
        v-if="activeTab === 'phone'"
        ref="phoneFormRef"
        :model="phoneForm"
        :rules="phoneRules"
        label-position="top"
      >
        <el-form-item label="手机号" prop="phone">
          <el-input
            v-model="phoneForm.phone"
            placeholder="请输入手机号"
            :prefix-icon="Phone"
            size="large"
            maxlength="11"
          />
        </el-form-item>

        <el-form-item label="验证码" prop="sms_code">
          <div class="sms-row">
            <el-input
              v-model="phoneForm.sms_code"
              placeholder="请输入6位验证码"
              :prefix-icon="Message"
              size="large"
              maxlength="6"
              class="sms-input"
              @keyup.enter="handlePhoneLogin"
            />
            <el-button
              :type="smsBtnDisabled ? 'info' : 'primary'"
              :disabled="smsBtnDisabled"
              :loading="sendingSms"
              size="large"
              class="sms-btn"
              @click="handleSendSms"
            >
              {{ smsBtnText }}
            </el-button>
          </div>
        </el-form-item>

        <!-- 新用户注册字段（手机号验证通过后显示） -->
        <template v-if="isNewUser">
          <el-divider>首次登录，请设置账号信息</el-divider>

          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="phoneForm.username"
              placeholder="请设置用户名"
              :prefix-icon="User"
              size="large"
            />
          </el-form-item>

          <el-form-item label="设置密码" prop="password">
            <el-input
              v-model="phoneForm.password"
              type="password"
              placeholder="至少8位密码"
              :prefix-icon="Lock"
              show-password
              size="large"
            />
          </el-form-item>

          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input
              v-model="phoneForm.confirmPassword"
              type="password"
              placeholder="请再次输入密码"
              :prefix-icon="Lock"
              show-password
              size="large"
              @keyup.enter="handlePhoneRegister"
            />
          </el-form-item>

          <el-button
            type="primary"
            :loading="loading"
            size="large"
            class="submit-btn"
            round
            @click="handlePhoneRegister"
          >
            完成注册并登录
          </el-button>
        </template>

        <!-- 已注册用户：直接登录按钮 -->
        <el-button
          v-else
          type="primary"
          :loading="loading"
          size="large"
          class="submit-btn"
          round
          @click="handlePhoneLogin"
        >
          登录 / 注册
        </el-button>
      </el-form>

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
import { reactive, ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock, Phone, Message } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// ── 状态 ──────────────────────────────────

const activeTab = ref<'password' | 'phone'>('password')
const loading = ref(false)
const wechatLoading = ref(false)

// 密码登录
const passwordFormRef = ref<FormInstance>()
const passwordForm = reactive({
  username_or_email: '',
  password: '',
})

const passwordRules: FormRules = {
  username_or_email: [{ required: true, message: '请输入用户名或邮箱', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

// 手机登录
const phoneFormRef = ref<FormInstance>()
const isNewUser = ref(false) // 是否为新用户（需展示注册字段）
const sendingSms = ref(false)
const smsCountdown = ref(0)
let countdownTimer: ReturnType<typeof setInterval> | null = null

const phoneForm = reactive({
  phone: '',
  sms_code: '',
  username: '',
  password: '',
  confirmPassword: '',
})

const phoneRules = computed<FormRules>(() => {
  const base: FormRules = {
    phone: [
      { required: true, message: '请输入手机号', trigger: 'blur' },
      { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' },
    ],
    sms_code: [
      { required: true, message: '请输入验证码', trigger: 'blur' },
      { len: 6, message: '验证码为6位数字', trigger: 'blur' },
    ],
  }
  if (isNewUser.value) {
    base.username = [
      { required: true, message: '请设置用户名', trigger: 'blur' },
      { min: 2, max: 50, message: '用户名长度 2-50 个字符', trigger: 'blur' },
    ]
    base.password = [
      { required: true, message: '请设置密码', trigger: 'blur' },
      { min: 8, message: '密码至少8位', trigger: 'blur' },
    ]
    base.confirmPassword = [
      { required: true, message: '请确认密码', trigger: 'blur' },
      {
        validator: (_rule: unknown, value: string, callback: (err?: Error) => void) => {
          if (value !== phoneForm.password) {
            callback(new Error('两次密码输入不一致'))
          } else {
            callback()
          }
        },
        trigger: 'blur',
      },
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

// ── 倒计时 ────────────────────────────────

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

// ── 切换 Tab ──────────────────────────────

function switchTab(tab: 'password' | 'phone') {
  activeTab.value = tab
  isNewUser.value = false
  phoneForm.sms_code = ''
  phoneForm.username = ''
  phoneForm.password = ''
  phoneForm.confirmPassword = ''
}

// ── 密码登录 ──────────────────────────────

async function handlePasswordLogin() {
  if (!passwordFormRef.value) return
  const valid = await passwordFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.login({
      username_or_email: passwordForm.username_or_email,
      password: passwordForm.password,
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

// ── 发送短信验证码 ─────────────────────────

async function handleSendSms() {
  // 先校验手机号
  const phone = (phoneForm.phone || '').trim()
  if (!phone || !/^1[3-9]\d{9}$/.test(phone)) {
    ElMessage.warning('请输入正确的手机号')
    return
  }

  sendingSms.value = true
  try {
    const { authService } = await import('@/services/auth')
    await authService.sendSmsCode({ phone })
    ElMessage.success('验证码已发送')
    startCountdown()
  } catch {
    // error handled by interceptor
  } finally {
    sendingSms.value = false
  }
}

// ── 手机号登录 ────────────────────────────

async function handlePhoneLogin() {
  if (!phoneFormRef.value) return

  // 动态校验规则（根据是否为新用户）
  const valid = await phoneFormRef.value.validate().catch(() => false)
  if (!valid) return

  const phone = (phoneForm.phone || '').trim()
  const sms_code = (phoneForm.sms_code || '').trim()

  loading.value = true
  try {
    const resp = await authStore.phoneLogin({ phone, sms_code })

    if (resp.is_new_user) {
      // 新用户：展开注册字段
      isNewUser.value = true
      ElMessage.info('手机号验证通过，请设置账号信息')
    } else {
      ElMessage.success('登录成功')
      const redirect = (route.query.redirect as string) || '/'
      router.push(redirect)
    }
  } catch {
    // error handled by interceptor
  } finally {
    loading.value = false
  }
}

// ── 新用户手机注册 ────────────────────────

async function handlePhoneRegister() {
  if (!phoneFormRef.value) return

  const valid = await phoneFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    // 短信验证已通过 phone-login 完成，直接注册
    await authStore.phoneRegister({
      phone: (phoneForm.phone || '').trim(),
      username: (phoneForm.username || '').trim(),
      password: phoneForm.password,
    })
    ElMessage.success('注册成功')
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch {
    // error handled by interceptor
  } finally {
    loading.value = false
  }
}

// ── 微信登录 ──────────────────────────────

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
  margin-bottom: 20px;
}

/* ── Tab 切换 ─────────────────────────── */
.login-tabs {
  display: flex;
  justify-content: center;
  gap: 32px;
  margin-bottom: 20px;
  border-bottom: 2px solid var(--border-light, #ebeef5);
  padding-bottom: 12px;
}

.tab-item {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-regular, #606266);
  cursor: pointer;
  padding-bottom: 12px;
  margin-bottom: -14px;
  border-bottom: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s;
}

.tab-item:hover {
  color: var(--primary);
}

.tab-item.active {
  color: var(--primary);
  font-weight: 600;
  border-bottom-color: var(--primary);
}

/* ── 短信验证码行 ─────────────────────── */
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

.submit-btn {
  width: 100%;
  font-weight: 600;
}

.forgot-row {
  text-align: right;
  margin-top: 10px;
}

.forgot-row a {
  font-size: 13px;
  color: var(--text-muted);
  text-decoration: none;
}

.forgot-row a:hover {
  color: var(--primary);
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
