<template>
  <div class="amap-map-card">
    <div class="amap-map-header">
      <div>
        <p class="amap-map-title">位置信息</p>
        <p class="amap-map-subtitle">{{ resolvedAddress || '房源地址未填写' }}</p>
      </div>
      <el-tag v-if="hasCoordinates" type="success" effect="plain">已定位</el-tag>
      <el-tag v-else type="info" effect="plain">暂无坐标</el-tag>
    </div>

    <div v-if="!hasCoordinates" class="amap-map-empty">
      <el-empty description="当前房源还没有经纬度信息" :image-size="96" />
    </div>

    <div v-else-if="!amapKey" class="amap-map-empty">
      <el-empty description="未配置高德地图 Key，已降级为外链查看" :image-size="96" />
    </div>

    <div v-else ref="mapContainer" class="amap-map-container" :style="{ height }" />

    <div v-if="hasCoordinates" class="amap-map-actions">
      <el-link :href="amapMarkerUrl" target="_blank" type="primary">在高德地图中查看 ↗</el-link>
      <span class="amap-map-coords">经纬度：{{ formattedLatitude }}, {{ formattedLongitude }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

type AMapMapInstance = {
  destroy: () => void
  addControl: (control: unknown) => void
}

const props = withDefaults(
  defineProps<{
    latitude: number | null | undefined
    longitude: number | null | undefined
    address?: string | null
    height?: string
    zoom?: number
  }>(),
  {
    address: '',
    height: '360px',
    zoom: 15,
  },
)

const mapContainer = ref<HTMLElement | null>(null)
const mapInstance = ref<AMapMapInstance | null>(null)
const amapKey = import.meta.env.VITE_AMAP_KEY as string | undefined
const resolvedAddress = computed(() => props.address?.trim() || '')
const hasCoordinates = computed(() => Number.isFinite(props.latitude) && Number.isFinite(props.longitude))
const formattedLatitude = computed(() => (props.latitude ?? 0).toFixed(6))
const formattedLongitude = computed(() => (props.longitude ?? 0).toFixed(6))
const amapMarkerUrl = computed(() => {
  const lng = props.longitude ?? 120.585
  const lat = props.latitude ?? 31.299
  const name = resolvedAddress.value || '房源位置'
  return `https://uri.amap.com/marker?position=${lng},${lat}&name=${encodeURIComponent(name)}`
})

async function loadAmapScript(): Promise<void> {
  if ((window as Window & { AMap?: unknown }).AMap) {
    return
  }

  await new Promise<void>((resolve, reject) => {
    if (import.meta.env.VITE_AMAP_SECURITY_JS_CODE) {
      ;(window as Window & { _AMapSecurityConfig?: { securityJsCode: string } })._AMapSecurityConfig = {
        securityJsCode: import.meta.env.VITE_AMAP_SECURITY_JS_CODE,
      }
    }

    const script = document.createElement('script')
    script.dataset.amapMap = 'true'
    script.type = 'text/javascript'
    script.async = true
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${amapKey}&plugin=AMap.Scale,AMap.ToolBar&lang=zh_cn`
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('高德地图脚本加载失败'))
    document.head.appendChild(script)
  })
}

async function initMap() {
  if (!hasCoordinates.value || !amapKey || !mapContainer.value) {
    return
  }

  await loadAmapScript()
  await nextTick()

  mapInstance.value?.destroy()
  mapInstance.value = null

  const AMap = (window as Window & { AMap?: any }).AMap
  if (!AMap || !mapContainer.value) {
    return
  }

  const lng = Number(props.longitude)
  const lat = Number(props.latitude)
  const map = new AMap.Map(mapContainer.value, {
    zoom: props.zoom,
    center: [lng, lat],
    viewMode: '2D',
  }) as AMapMapInstance

  map.addControl(new AMap.Scale())
  map.addControl(new AMap.ToolBar())
  new AMap.Marker({
    position: [lng, lat],
    title: resolvedAddress.value || '房源位置',
    map,
  })

  mapInstance.value = map
}

watch(
  () => [props.latitude, props.longitude, amapKey],
  () => {
    void initMap()
  },
  { immediate: true },
)

onMounted(() => {
  void initMap()
})

onBeforeUnmount(() => {
  mapInstance.value?.destroy()
  mapInstance.value = null
})
</script>

<style scoped>
.amap-map-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.amap-map-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.amap-map-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.amap-map-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.amap-map-container {
  width: 100%;
  min-height: 280px;
  border-radius: 14px;
  overflow: hidden;
  background: linear-gradient(135deg, #eef4ff 0%, #f8fbff 100%);
}

.amap-map-empty {
  border-radius: 14px;
  background: #fafcff;
  border: 1px dashed #dcdfe6;
  padding: 18px 12px;
}

.amap-map-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  font-size: 13px;
  color: #909399;
}

.amap-map-coords {
  word-break: break-all;
}
</style>