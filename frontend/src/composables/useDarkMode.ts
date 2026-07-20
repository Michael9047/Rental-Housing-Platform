/** 夜间模式切换 —— 持久化到 localStorage，全局 data-theme 属性驱动 */
import { ref } from 'vue'

const STORAGE_KEY = 'rental-theme'
const isDark = ref(false)

/** 初始化：从 localStorage 读取 */
function init(): void {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'dark') {
      isDark.value = true
    } else if (stored === 'light') {
      isDark.value = false
    } else {
      // 首次访问：跟随系统偏好
      isDark.value = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
    }
  } catch {
    // localStorage 不可用时静默忽略
  }
  apply()
}

/** 同步 DOM 属性 */
function apply(): void {
  if (isDark.value) {
    document.documentElement.setAttribute('data-theme', 'dark')
  } else {
    document.documentElement.removeAttribute('data-theme')
  }
}

/** 切换日夜模式 */
function toggle(): void {
  isDark.value = !isDark.value
  try {
    localStorage.setItem(STORAGE_KEY, isDark.value ? 'dark' : 'light')
  } catch { /* ignore */ }
  apply()
}

// 首次加载时初始化
init()

// 监听系统偏好变化（仅当用户未手动设置时）
try {
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored || stored === 'system') {
      isDark.value = e.matches
      apply()
    }
  })
} catch { /* ignore */ }

export function useDarkMode() {
  return { isDark, toggle }
}
