<!-- 旧 /room/:id 路由适配器：将 UnitType ID 转为 Building ID 后重定向。 -->
<template><div v-loading="true" style="min-height:200px"></div></template>
<script setup lang="ts">
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'

const route = useRoute()
const router = useRouter()

let redirectEpoch = 0

async function resolveLegacyId(rawId: unknown): Promise<void> {
  const id = Array.isArray(rawId) ? String(rawId[0] || '') : String(rawId || '')
  const numericId = Number(id)
  if (!Number.isInteger(numericId) || numericId <= 0) {
    await router.replace({ path: '/' })
    return
  }
  const epoch = ++redirectEpoch

  // /room 历史上表示具体户型，必须先查 UnitType。
  // 如果 UnitType.id 与 Institute.id 碰号，先查 Building 会跳到错误公寓。
  try {
    const r = await api.get(`/unit-types/${id}`)
    const instId = r.data?.institute_id
    if (epoch !== redirectEpoch) return
    if (Number.isInteger(Number(instId)) && Number(instId) > 0) {
      await router.replace({
        name: 'building-detail',
        params: { id: String(instId) },
        query: { ...route.query, unit_type_id: id },
      })
      return
    }
  } catch { /* 不是 UnitType，继续尝试旧 Building 链接。 */ }

  try {
    await api.get(`/buildings/${id}/tenant-detail`)
    if (epoch !== redirectEpoch) return
    await router.replace({
      name: 'building-detail',
      params: { id },
      query: { ...route.query },
    })
    return
  } catch { /* 两种实体都不存在。 */ }

  if (epoch === redirectEpoch) await router.replace({ path: '/' })
}

watch(() => route.params.id, (id) => {
  void resolveLegacyId(id)
}, { immediate: true })
</script>
