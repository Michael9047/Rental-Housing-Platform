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
        // 本机 8000、8001 被其他工作区的遗留服务占用时，PR41 本地后端使用 8007。
        target: 'http://127.0.0.1:8007',
        changeOrigin: true,
      },
    },
  },
})
