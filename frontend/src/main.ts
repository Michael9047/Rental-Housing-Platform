import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'

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
window.onerror = (msg, source, lineno, colno, error) => {
  if (typeof msg === 'string' && msg.includes('ResizeObserver')) return true
  if (eio) return eio.call(window, msg, source, lineno, colno, error)
}

app.config.errorHandler = (err: unknown) => {
  if (err instanceof Error && err.message.includes('ResizeObserver')) return
  console.error(err)
}

app.mount('#app')
