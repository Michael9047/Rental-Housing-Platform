import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import './styles/booking-form-controls.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'

// 清理损坏的登录状态（旧版 guest token 误存为 access_token 等）
;(() => {
  const accessToken = localStorage.getItem('access_token')
  const userStr = localStorage.getItem('user')
  if (accessToken && !userStr) {
    // 有 token 但无 user → 可能是旧 guest token 残留 → 清除
    localStorage.removeItem('access_token')
  }
})()

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// Register all Element Plus icons globally
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 在任何 JS 执行前拦截 ResizeObserver 良性报错
const eio = window.onerror
window.onerror = (msg, source, line, column, error) => {
  if (typeof msg === 'string' && msg.includes('ResizeObserver')) return true
  if (eio) return eio.call(window, msg, source, line, column, error)
  return false
}

app.config.errorHandler = (err: unknown) => {
  if (err instanceof Error && err.message.includes('ResizeObserver')) return
  console.error(err)
  throw err  // 非 ResizeObserver 错误继续抛出，让 Vue 错误覆盖层显示
}

app.mount('#app')
