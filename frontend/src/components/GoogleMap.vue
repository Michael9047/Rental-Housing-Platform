<template>
  <div class="google-map-card">
    <div class="google-map-header">
      <div>
        <p class="google-map-title">位置信息</p>
        <p class="google-map-subtitle">{{ resolvedAddress || '房源地址未填写' }}</p>
      </div>
      <el-tag v-if="hasCoordinates" type="success" effect="plain">已定位</el-tag>
      <el-tag v-else type="info" effect="plain">暂无坐标</el-tag>
    </div>

    <div v-if="!hasCoordinates" class="google-map-empty">
      <el-empty description="当前房源还没有经纬度信息" :image-size="96" />
    </div>

    <div v-else-if="!gmKey" class="google-map-empty">
      <el-empty description="未配置 Google Maps Key，已降级为外链查看" :image-size="96" />
    </div>

    <div v-else ref="mapContainer" class="google-map-container" :style="{ height }" />

    <div v-if="hasCoordinates" class="google-map-actions">
      <el-link :href="gmMarkerUrl" target="_blank" type="primary">在 Google Maps 中查看 &rarr;</el-link>
      <span class="google-map-coords">经纬度：{{ formattedLatitude }}, {{ formattedLongitude }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

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
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mapInstance = ref<any>(null)
const gmKey = import.meta.env.VITE_GM_KEY as string | undefined
const resolvedAddress = computed(() => props.address?.trim() || '')
const hasCoordinates = computed(() => Number.isFinite(props.latitude) && Number.isFinite(props.longitude))
const formattedLatitude = computed(() => (props.latitude ?? 0).toFixed(6))
const formattedLongitude = computed(() => (props.longitude ?? 0).toFixed(6))
const gmMarkerUrl = computed(() => {
  const lat = props.latitude ?? 1.3521
  const lng = props.longitude ?? 103.8198
  return `https://www.google.com/maps?q=${lat},${lng}`
})

async function loadGoogleMapsScript(): Promise<void> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const gWindow = window as any
  if (gWindow.google?.maps) {
    return
  }

  await new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.dataset.googleMap = 'true'
    script.type = 'text/javascript'
    script.async = true
    script.src = `https://maps.googleapis.com/maps/api/js?key=${gmKey}&libraries=places&language=zh-CN`
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Google Maps 脚本加载失败'))
    document.head.appendChild(script)
  })
}

async function initMap() {
  if (!hasCoordinates.value || !gmKey || !mapContainer.value) {
    return
  }

  await loadGoogleMapsScript()
  await nextTick()

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const gWindow = window as any
  const google = gWindow.google
  if (!google?.maps || !mapContainer.value) {
    return
  }

  const lat = Number(props.latitude)
  const lng = Number(props.longitude)
  const position = { lat, lng }

  const map = new google.maps.Map(mapContainer.value, {
    zoom: props.zoom,
    center: position,
    mapTypeControl: true,
    streetViewControl: false,
    fullscreenControl: true,
    zoomControl: true,
  })

  new google.maps.Marker({
    position,
    map,
    title: resolvedAddress.value || '房源位置',
    animation: google.maps.Animation.DROP,
  })

  mapInstance.value = map
}

watch(
  () => [props.latitude, props.longitude, gmKey],
  () => {
    void initMap()
  },
  { immediate: true },
)

onMounted(() => {
  void initMap()
})

onBeforeUnmount(() => {
  mapInstance.value = null
})
</script>

<style scoped>
.google-map-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.google-map-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.google-map-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.google-map-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.google-map-container {
  width: 100%;
  min-height: 280px;
  border-radius: 14px;
  overflow: hidden;
  background: linear-gradient(135deg, #eef4ff 0%, #f8fbff 100%);
}

.google-map-empty {
  border-radius: 14px;
  background: #fafcff;
  border: 1px dashed #dcdfe6;
  padding: 18px 12px;
}

.google-map-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  font-size: 13px;
  color: #909399;
}

.google-map-coords {
  word-break: break-all;
}
</style>
