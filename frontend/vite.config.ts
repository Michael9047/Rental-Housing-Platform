import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // 本机 8000 被旧工作区遗留进程占用时，PR41 本地后端使用 8001。
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
})
