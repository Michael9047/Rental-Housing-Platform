<template>
  <div v-if="error" style="padding:40px;color:red;background:#fff;max-width:800px;margin:40px auto;border-radius:12px;font-family:monospace">
    <h2>⚠️ Vue App Error</h2>
    <pre style="white-space:pre-wrap;word-break:break-all">{{ error }}</pre>
    <button @click="error=null" style="margin-top:20px;padding:10px 20px;background:#e94560;color:#fff;border:none;border-radius:8px;cursor:pointer">🔄 Retry</button>
  </div>
  <router-view v-else />
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'
const error = ref<string | null>(null)

function _isNoise(msg: string | undefined): boolean {
  if (!msg) return false
  return msg.includes('ResizeObserver') || msg.includes('Script error')
}

onErrorCaptured((err: any) => {
  const msg = err?.message || err?.toString() || ''
  if (_isNoise(msg)) return false
  error.value = msg || 'Unknown error'
  console.error('Caught:', err)
  return false
})
// Global error handler
window.addEventListener('error', (e) => {
  if (_isNoise(e.message)) return
  error.value = `[${e.filename?.split('/').pop()}:${e.lineno}] ${e.message}`
})
window.addEventListener('unhandledrejection', (e) => {
  const msg = e.reason?.message || e.reason?.toString() || ''
  if (_isNoise(msg)) return
  error.value = `[Promise] ${msg}`
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
