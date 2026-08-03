<!-- 旧 /room/:id 路由适配器：将 unit_type ID 转为 building ID 后重定向 -->
<template><div v-loading="true" style="min-height:200px"></div></template>
<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'

const route = useRoute()
const router = useRouter()

onMounted(async () => {
  const id = route.params.id as string
  // 先尝试 building API
  try {
    await api.get(`/buildings/${id}/tenant-detail`)
    // 是合法的 building ID，直接替换到 building 路由
    router.replace({ path: `/building/${id}` })
    return
  } catch { /* 404 — 可能是 unit_type ID，继续查找 */ }

  // 尝试 unit_type 查找
  try {
    const r = await api.get(`/unit-types/${id}`)
    const instId = r.data?.institute_id
    if (instId) {
      router.replace({ path: `/building/${instId}` })
      return
    }
  } catch { /* 也找不到 */ }

  // 都找不到，重定向到首页
  router.replace({ path: '/' })
})
</script>
