<template>
  <div class="callback-container">
    <el-icon class="is-loading" :size="32"><Loading /></el-icon>
    <p>{{ statusText }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const statusText = ref('正在完成微信登录...')

onMounted(async () => {
  const code = route.query.code as string
  const state = route.query.state as string

  if (!code || !state) {
    statusText.value = '登录参数不完整，即将返回登录页...'
    setTimeout(() => router.replace('/login'), 2000)
    return
  }

  try {
    await authStore.wechatQrLogin({ code, state })
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/'
    router.replace(redirect)
  } catch {
    statusText.value = '登录失败，即将返回登录页...'
    setTimeout(() => router.replace('/login'), 2000)
  }
})
</script>

<style scoped>
.callback-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  gap: 16px;
  color: #606266;
  font-size: 15px;
}
</style>
