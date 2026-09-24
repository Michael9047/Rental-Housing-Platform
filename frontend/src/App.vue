<template>
  <!-- 错误横幅：悬浮在页面顶部，不阻挡用户操作 -->
  <div v-if="errorInfo" class="error-banner" :class="{ 'error-banner--dev': isDev }">
    <span class="error-banner__icon">⚠️</span>
    <span class="error-banner__msg">{{ isDev ? errorInfo.message : '应用遇到了问题，请刷新页面重试' }}</span>
    <span v-if="isDev" class="error-banner__meta">{{ errorInfo.category }} · {{ errorInfo.source }}</span>
    <button class="error-banner__close" @click="errorInfo = null">✕</button>
  </div>
  <router-view />
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'
import { useRouter } from 'vue-router'
import { createLogger } from '@/utils/logger'

const log = createLogger('App')
const router = useRouter()
const isDev = import.meta.env.DEV

/** 错误分类 */
type ErrorCategory = 'network' | 'auth' | 'not_found' | 'server' | 'unknown'

interface ErrorInfo {
  id: string
  timestamp: string
  category: ErrorCategory
  message: string
  source?: string
}

const errorInfo = ref<ErrorInfo | null>(null)

/** 生成简短的 UUID v4 */
function generateId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

/** 从错误消息推断分类 */
function categorizeError(msg: string): ErrorCategory {
  if (/network|fetch|ECONN|\bnet\b|timeout|NetworkError/i.test(msg)) return 'network'
  if (/401|unauthorized|token|login|expired|auth/i.test(msg)) return 'auth'
  if (/404|not.?found|不存在/i.test(msg)) return 'not_found'
  if (/500|internal.?server|server.?error/i.test(msg)) return 'server'
  return 'unknown'
}

function _isNoise(msg: string | undefined): boolean {
  if (!msg) return false
  return msg.includes('ResizeObserver') || msg.includes('Script error')
}

let _dismissTimer: ReturnType<typeof setTimeout> | null = null

function setError(message: string, source?: string) {
  if (_isNoise(message)) return
  errorInfo.value = {
    id: generateId(),
    timestamp: new Date().toISOString(),
    category: categorizeError(message),
    message,
    source,
  }
  log.error('Error boundary 捕获', {
    errorId: errorInfo.value.id,
    category: errorInfo.value.category,
    source,
  }, message)

  // 8 秒后自动消失
  if (_dismissTimer) clearTimeout(_dismissTimer)
  _dismissTimer = setTimeout(() => { errorInfo.value = null }, 8000)
}

function handleRetry() {
  // 生产环境直接刷新页面；开发环境清空错误让 Vite HMR 恢复
  if (isDev) {
    errorInfo.value = null
  } else {
    window.location.reload()
  }
}

function handleGoHome() {
  errorInfo.value = null
  router.push('/')
}

onErrorCaptured((err: any) => {
  const msg = err?.message || err?.toString() || ''
  if (_isNoise(msg)) return false
  setError(msg || 'Unknown error', 'Vue component')
  return false
})

// Global error handler
window.addEventListener('error', (e) => {
  if (_isNoise(e.message)) return
  setError(e.message || 'Unknown error', `${e.filename?.split('/').pop()}:${e.lineno}`)
})

window.addEventListener('unhandledrejection', (e) => {
  const msg = e.reason?.message || e.reason?.toString() || ''
  if (_isNoise(msg)) return
  setError(msg || 'Unknown error', 'Promise')
})
</script>

<style>
/* ===== 全局橙白主题 — 租房品牌色 ===== */
:root {
  --primary: #FF6B35;
  --primary-light: #FFF4ED;
  --primary-dark: #E85D2C;
  --success: #67c23a;
  --warning: #e6a23c;
  --danger: #f56c6c;
  --info: #909399;
  --bg: #f5f6f8;
  --bg-white: #ffffff;
  --text-primary: #303133;
  --text-secondary: #606266;
  --text-muted: #909399;
  --border: #e4e7ed;
  --border-light: #ebeef5;
  --radius-sm: 8px;
  --radius: 12px;
  --radius-lg: 16px;
  --radius-xl: 20px;
  --shadow-sm: 0 1px 4px rgba(0, 0, 0, 0.04);
  --shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 4px 24px rgba(0, 0, 0, 0.08);

  /* ── 覆盖 Element Plus 原生主题变量 ── */
  --el-color-primary: #FF6B35;
  --el-color-primary-light-3: #FF8F64;
  --el-color-primary-light-5: #FFA982;
  --el-color-primary-light-7: #FFC7AD;
  --el-color-primary-light-8: #FFDDCD;
  --el-color-primary-light-9: #FFF4ED;
  --el-color-primary-dark-2: #E85D2C;
  --el-color-primary-dark-4: #D14E20;
  --el-color-primary-dark-6: #B33F16;

  /* ── Element Plus 圆角统一 ── */
  --el-border-radius-base: 8px;
  --el-border-radius-round: 20px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: var(--bg);
  color: var(--text-primary);
}

/* ===== 错误横幅（不阻挡页面） ===== */
.error-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  background: #fff3cd;
  border-bottom: 2px solid #ffc107;
  font-size: 14px;
  line-height: 1.4;
}
.error-banner--dev {
  background: #f8d7da;
  border-color: #f5c2c7;
}
.error-banner__icon { flex-shrink: 0; font-size: 18px; }
.error-banner__msg { flex: 1; min-width: 0; font-weight: 500; }
.error-banner__meta { flex-shrink: 0; font-size: 12px; color: var(--text-muted); font-family: monospace; }
.error-banner__close {
  flex-shrink: 0;
  border: none;
  background: none;
  font-size: 16px;
  cursor: pointer;
  padding: 2px 6px;
  opacity: 0.6;
}
.error-banner__close:hover { opacity: 1; }

/* ===== 全局圆角覆盖 ===== */
.el-card {
  border-radius: var(--radius) !important;
  border: 1px solid var(--border) !important;
  box-shadow: var(--shadow-sm) !important;
  transition: box-shadow 0.3s;
}
.el-card:hover {
  box-shadow: var(--shadow) !important;
}

.el-button {
  border-radius: var(--radius-sm) !important;
  font-weight: 500;
}
.el-button--primary {
  background: var(--primary);
  border-color: var(--primary);
}
.el-button--primary:hover {
  background: var(--primary-dark);
  border-color: var(--primary-dark);
}

.el-input .el-input__wrapper,
.el-select .el-select__wrapper,
.el-date-picker .el-input__wrapper {
  border-radius: var(--radius-sm) !important;
}

.el-tag {
  border-radius: 6px !important;
}

.el-dialog {
  border-radius: var(--radius-lg) !important;
}

.el-menu {
  border-radius: 0 !important;
}

.el-pagination .el-pager li {
  border-radius: 6px !important;
}

/* ===== 通用辅助类 ===== */
.page-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.section-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title::before {
  content: '';
  width: 4px;
  height: 20px;
  background: var(--primary);
  border-radius: 2px;
}

/* fade transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
