<!-- 统一的新建公寓弹窗，集中处理结构化地址、地图选点、设施和图片。 -->
<template>
  <el-dialog
    v-model="visible"
    title="新建公寓"
    width="780px"
    :close-on-click-modal="false"
    destroy-on-close
    @opened="initializeMap"
    @closed="reset"
  >
    <el-form label-width="105px">
      <el-form-item label="公寓名称" required>
        <el-input v-model="form.name" maxlength="200" />
      </el-form-item>

      <el-divider>地址与地图定位</el-divider>
      <el-alert
        class="address-language-alert"
        title="请填写公寓所在地的官方英文地址"
        description="国家、城市、区域和街道门牌请使用英文。地图选点后也会按英文自动回填，便于海外导航、入住交付和合同识别。"
        type="info"
        :closable="false"
        show-icon
      />
      <div class="address-grid">
        <el-form-item label="国家 / 地区" required>
          <el-autocomplete v-model="form.country" :fetch-suggestions="suggestCountries" placeholder="e.g. United Kingdom" clearable />
        </el-form-item>
        <el-form-item label="城市" required><el-input v-model="form.city" placeholder="e.g. London" /></el-form-item>
        <el-form-item label="区域"><el-input v-model="form.district" placeholder="e.g. Westminster" /></el-form-item>
        <el-form-item label="邮编"><el-input v-model="form.postalCode" placeholder="e.g. SW1A 1AA" /></el-form-item>
        <el-form-item class="address-grid__wide" label="街道 / 门牌" required>
          <el-input v-model="form.street" placeholder="e.g. 10 Downing Street" @keyup.enter="geocodeAddress" />
        </el-form-item>
      </div>

      <el-form-item label="地图坐标" required>
        <div class="map-field">
          <div class="map-toolbar">
            <el-button type="primary" :loading="geocoding" :disabled="!canGeocode" @click="geocodeAddress">
              地址定位
            </el-button>
            <el-button :loading="locating" @click="locate">使用当前位置</el-button>
            <el-button :loading="mapLoading" @click="reloadMap">重新加载地图</el-button>
            <el-button type="danger" plain @click="clearLocation">清空定位</el-button>
            <el-tag v-if="hasCoordinates" type="success" effect="plain">
              {{ form.latitude!.toFixed(6) }}, {{ form.longitude!.toFixed(6) }}
            </el-tag>
            <el-tag v-else type="warning" effect="plain">尚未定位</el-tag>
          </div>
          <div ref="mapElement" class="map-canvas" :class="{ 'is-loading': mapLoading }" />
          <div class="hint">填写英文地址后可定位到地图；点击地图会按英文回填地址，拖动标记可更新精确坐标。</div>
        </div>
      </el-form-item>

      <el-divider>联系方式与介绍</el-divider>
      <el-form-item label="前台电话"><el-input v-model="form.contactPhone" /></el-form-item>
      <el-form-item label="公寓介绍">
        <el-input v-model="form.description" type="textarea" :rows="3" maxlength="2000" show-word-limit />
      </el-form-item>

      <el-divider>公寓设施</el-divider>
      <section v-for="group in amenityGroups" :key="group.label" class="amenity-section">
        <span class="amenity-section__label">{{ group.label }}</span>
        <el-checkbox-group v-model="form.amenities">
          <el-checkbox v-for="item in group.items" :key="item" :value="item" border>{{ item }}</el-checkbox>
        </el-checkbox-group>
      </section>

      <el-divider>公寓公共图集</el-divider>
      <el-form-item label="公寓照片" required>
        <ImageUploader
          v-model="form.images"
          title="公寓外观、大堂与公共设施"
          hint="至少 3 张，首张作为封面"
          :min-files="3"
          :max-files="20"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import ImageUploader from '@/components/ImageUploader.vue'
import { buildingService, type Building } from '@/services/building'
import { loadTiles, type TileHandle } from '@/services/tileDetector'
import { toUserFriendly } from '@/services/api'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; created: [building: Building] }>()
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const submitting = ref(false)
const locating = ref(false)
const geocoding = ref(false)
const mapLoading = ref(false)
const mapElement = ref<HTMLElement | null>(null)

const amenityGroups = [
  { label: '安保', items: ['24小时安保', '监控系统(CCTV)', '智能门禁', '电子门锁', '前台/礼宾', '消防系统', '夜间巡逻'] },
  { label: '服务', items: ['代收包裹', '维修服务', '公共区域保洁', '定期社交活动', '接机服务', '班车接驳', '入住礼包', '管家服务'] },
  { label: '公用设施', items: ['电梯', '洗衣房', '自行车库', '停车场', '公共厨房', '快递柜/信箱', '自习室', '影音室', '公共休闲区', '屋顶露台', '庭院/花园', '会议室'] },
  { label: '运动娱乐', items: ['健身房', '游泳池', '篮球场', '瑜伽室', '游戏室', 'BBQ区', '乒乓球/台球'] },
]
const countries = ['Australia', 'Canada', 'China', 'France', 'Germany', 'Japan', 'Malaysia', 'New Zealand', 'Singapore', 'South Korea', 'Thailand', 'United Kingdom', 'United States']

function suggestCountries(query: string, callback: (items: Array<{ value: string }>) => void) {
  const keyword = query.trim().toLowerCase()
  callback(countries.filter(country => !keyword || country.toLowerCase().includes(keyword)).map(value => ({ value })))
}

const blank = () => ({
  name: '', country: '', city: '', district: '', street: '', postalCode: '',
  latitude: undefined as number | undefined, longitude: undefined as number | undefined,
  contactPhone: '', description: '', amenities: [] as string[], images: [] as string[],
})
const form = reactive(blank())
const hasCoordinates = computed(() => Number.isFinite(form.latitude) && Number.isFinite(form.longitude))
const canGeocode = computed(() => Boolean(form.country.trim() || form.city.trim() || form.street.trim()))

let map: any = null
let marker: any = null
let tileHandle: TileHandle | null = null

delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({ iconRetinaUrl: markerIcon2x, iconUrl: markerIcon, shadowUrl: markerShadow })

function destroyMap() {
  tileHandle?.destroy()
  tileHandle = null
  if (map) map.remove()
  map = null
  marker = null
}

async function initializeMap() {
  mapLoading.value = true
  await nextTick()
  try {
    destroyMap()
    if (!mapElement.value) return
    const center: [number, number] = hasCoordinates.value
      ? [form.latitude!, form.longitude!]
      : [31.27, 120.73]
    map = L.map(mapElement.value, { center, zoom: hasCoordinates.value ? 17 : 12, attributionControl: false })
    tileHandle = await loadTiles(map, form.country)
    map.on('click', async (event: any) => placeMarker(event.latlng.lat, event.latlng.lng, true))
    if (hasCoordinates.value) placeMarker(form.latitude!, form.longitude!, false)
    setTimeout(() => map?.invalidateSize(), 0)
  } catch (error) {
    ElMessage.error(toUserFriendly(error) || '地图加载失败，请点击重新加载')
  } finally {
    mapLoading.value = false
  }
}

async function reloadMap() {
  await initializeMap()
  if (map) ElMessage.success('地图已重新加载')
}

function placeMarker(latitude: number, longitude: number, reverse: boolean) {
  if (!map) return
  if (marker) marker.setLatLng([latitude, longitude])
  else {
    marker = L.marker([latitude, longitude], { draggable: true }).addTo(map)
    marker.on('dragend', () => {
      const position = marker.getLatLng()
      form.latitude = position.lat
      form.longitude = position.lng
    })
  }
  form.latitude = latitude
  form.longitude = longitude
  if (reverse) void reverseGeocode(latitude, longitude)
}

async function geocodeAddress() {
  if (!canGeocode.value) return
  geocoding.value = true
  try {
    const params = new URLSearchParams({ format: 'json', limit: '1', 'accept-language': 'en' })
    if (form.street) params.set('street', form.street)
    if (form.city) params.set('city', form.city)
    if (form.country) params.set('country', form.country)
    if (form.postalCode) params.set('postalcode', form.postalCode)
    const response = await fetch(`https://nominatim.openstreetmap.org/search?${params}`)
    if (!response.ok) throw new Error('地址定位请求失败')
    const result = await response.json()
    if (!result.length) {
      ElMessage.warning('未找到该地址，请检查地址或在地图上手动选点')
      return
    }
    const latitude = Number(result[0].lat)
    const longitude = Number(result[0].lon)
    placeMarker(latitude, longitude, false)
    map?.setView([latitude, longitude], 17)
    ElMessage.success(`已定位到 ${latitude.toFixed(4)}, ${longitude.toFixed(4)}`)
  } catch (error) {
    ElMessage.error(toUserFriendly(error) || '地址定位失败')
  } finally {
    geocoding.value = false
  }
}

async function reverseGeocode(latitude: number, longitude: number) {
  try {
    const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&accept-language=en`)
    if (!response.ok) throw new Error('地址识别请求失败')
    const result = await response.json()
    const address = result?.address
    if (!address) return ElMessage.warning('该坐标附近未识别到地址')
    const road = address.road || address.pedestrian || address.path || address.footway || ''
    const houseNumber = address.house_number || ''
    form.country = address.country || form.country
    form.city = address.city || address.town || address.municipality || address.village || address.hamlet || ''
    form.district = address.suburb || address.borough || address.city_district || address.county || address.state_district || ''
    form.street = houseNumber ? `${houseNumber} ${road}`.trim() : road
    form.postalCode = address.postcode || ''
    ElMessage.success('已识别地图位置并回填英文地址')
  } catch (error) {
    ElMessage.warning(toUserFriendly(error) || '坐标已保存，但地址识别失败')
  }
}

function locate() {
  if (!navigator.geolocation) return ElMessage.warning('当前浏览器不支持定位')
  locating.value = true
  navigator.geolocation.getCurrentPosition(
    position => {
      placeMarker(position.coords.latitude, position.coords.longitude, true)
      map?.setView([position.coords.latitude, position.coords.longitude], 17)
      locating.value = false
    },
    () => { locating.value = false; ElMessage.error('定位失败，请在地图上手动选点') },
    { enableHighAccuracy: true, timeout: 10000 },
  )
}

function clearLocation() {
  form.latitude = undefined
  form.longitude = undefined
  if (marker) marker.remove()
  marker = null
}

function reset() {
  destroyMap()
  Object.assign(form, blank())
}

async function submit() {
  if (!form.name.trim() || !form.country.trim() || !form.city.trim() || !form.street.trim()) {
    ElMessage.warning('请完整填写公寓名称和地址')
    return
  }
  if (!hasCoordinates.value) { ElMessage.warning('请完成地图定位'); return }
  if (form.images.length < 3) { ElMessage.warning('请至少上传 3 张公寓照片'); return }
  submitting.value = true
  try {
    const building = await buildingService.create({
      name: form.name.trim(), country: form.country.trim(), city: form.city.trim(),
      district: form.district.trim() || null, street: form.street.trim(),
      postal_code: form.postalCode.trim() || null,
      latitude: String(form.latitude), longitude: String(form.longitude),
      contact_phone: form.contactPhone.trim() || null,
      description: form.description.trim() || null,
      amenities: form.amenities, image_urls: form.images,
    } as any)
    emit('created', building)
    visible.value = false
    ElMessage.success('公寓创建成功')
  } catch (error) {
    ElMessage.error(toUserFriendly(error) || '创建失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.address-grid { display:grid; grid-template-columns:1fr 1fr; column-gap:16px; }
.address-grid__wide { grid-column:1 / -1; }
.address-language-alert { margin-bottom:18px; }
.map-field { width:100%; min-width:0; }
.map-toolbar { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:10px; }
.map-canvas {
  position:relative;
  display:block;
  width:100%;
  height:300px;
  min-height:300px;
  max-height:300px;
  overflow:hidden;
  contain:layout paint;
  isolation:isolate;
  border:1px solid var(--el-border-color);
  border-radius:10px;
  background:#f5f7fa;
}
.map-canvas.is-loading { opacity:.6; }
.hint { color:#909399; font-size:12px; margin-top:7px; }
.amenity-section { display:grid; grid-template-columns:95px 1fr; gap:10px; margin:12px 0; }
.amenity-section__label { color:#606266; font-size:13px; padding-top:7px; }
.amenity-section :deep(.el-checkbox-group) { display:flex; flex-wrap:wrap; gap:8px; }
.amenity-section :deep(.el-checkbox) { margin-right:0; }
@media (max-width:720px) {
  .address-grid { grid-template-columns:1fr; }
  .address-grid__wide { grid-column:auto; }
  .amenity-section { grid-template-columns:1fr; }
}
</style>
