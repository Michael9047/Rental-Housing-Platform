<template>
  <div class="detail-page" v-loading="loading">
    <div v-if="building">
      <!-- ═══ 第一层：公寓头部 ═══ -->
      <!-- 图片轮播 -->
      <div class="image-carousel" v-if="building.images?.length">
        <el-carousel :interval="4000" height="360px" indicator-position="outside">
          <el-carousel-item v-for="img in building.images" :key="img.id">
            <img :src="img.filename?.startsWith('http') ? img.filename : '/api/v1/uploads/'+img.filename" style="width:100%;height:360px;object-fit:cover;border-radius:12px" />
          </el-carousel-item>
        </el-carousel>
      </div>
      <div v-else class="no-image">🏢</div>

      <!-- 公寓基础信息 -->
      <div class="building-header">
        <h1>{{ building.name }}</h1>
        <p class="addr" v-if="building.address">📍 {{ building.address }}</p>
        <p class="desc" v-if="building.description">{{ building.description }}</p>
        <p class="phone" v-if="building.contact_phone">📞 前台：{{ building.contact_phone }}</p>
      </div>

      <!-- 公寓特殊标记 -->
      <div class="special-tags" v-if="building.female_only || building.couples_allowed">
        <el-tag v-if="building.female_only" size="large" effect="dark" type="danger">👩 女生独栋</el-tag>
        <el-tag v-if="building.couples_allowed" size="large" effect="dark" type="warning">💑 支持情侣入住</el-tag>
      </div>

      <!-- 公寓配套 — 四大板块 -->
      <div class="amenities-section" v-if="building.amenities?.length">
        <h3>🏗️ 公寓配套 & 服务</h3>
        <div v-if="getCategoryAmenities(building.amenities, 'security').length" class="amenity-cat">
          <span class="cat-label">🛡️ 安保</span>
          <div class="amenity-tags">
            <el-tag v-for="a in getCategoryAmenities(building.amenities, 'security')" :key="a" size="small" effect="plain" type="primary">{{ a }}</el-tag>
          </div>
        </div>
        <div v-if="getCategoryAmenities(building.amenities, 'service').length" class="amenity-cat">
          <span class="cat-label">🛎️ 服务</span>
          <div class="amenity-tags">
            <el-tag v-for="a in getCategoryAmenities(building.amenities, 'service')" :key="a" size="small" effect="plain" type="success">{{ a }}</el-tag>
          </div>
        </div>
        <div v-if="getCategoryAmenities(building.amenities, 'facility').length" class="amenity-cat">
          <span class="cat-label">🏠 公用设施</span>
          <div class="amenity-tags">
            <el-tag v-for="a in getCategoryAmenities(building.amenities, 'facility')" :key="a" size="small" effect="plain" type="info">{{ a }}</el-tag>
          </div>
        </div>
        <div v-if="getCategoryAmenities(building.amenities, 'sport').length" class="amenity-cat">
          <span class="cat-label">⚽ 运动娱乐</span>
          <div class="amenity-tags">
            <el-tag v-for="a in getCategoryAmenities(building.amenities, 'sport')" :key="a" size="small" effect="plain" type="warning">{{ a }}</el-tag>
          </div>
        </div>
      </div>

      <!-- 地图 -->
      <div class="map-section" v-if="building.latitude && building.longitude">
        <h3>🗺️ 位置</h3>
        <div id="detail-map" style="width:100%;height:240px;border-radius:8px;border:1px solid #dcdfe6"></div>
      </div>

      <el-divider />

      <!-- ═══ 第二层：户型切换 ═══ -->
      <div class="unit-types-section">
        <h3>📐 可选户型</h3>
        <div class="unit-tabs">
          <div v-for="ut in building.unit_types" :key="ut.id"
            :class="['unit-tab', { active: selectedUnitType?.id === ut.id }]"
            @click="selectUnitType(ut)">
            <div class="ut-name">{{ ut.name }}</div>
            <div class="ut-info">{{ ut.bedrooms }}室{{ ut.hall_count }}厅{{ ut.bathrooms }}卫 · {{ ut.area_sqm }}㎡</div>
            <div class="ut-rent">{{ cur(ut.currency) }}{{ Number(ut.base_rent).toLocaleString() }}/月</div>
            <el-tag size="small" :type="ut.room_count > 0 ? 'success' : 'warning'">
              {{ ut.room_count > 0 ? ut.room_count+'间可租' : '暂无可租' }}
            </el-tag>
          </div>
        </div>
      </div>

      <!-- ═══ 第三层：选中户型详情 ═══ -->
      <div class="ut-detail" v-if="selectedUnitType">
        <el-divider />
        <h3>{{ selectedUnitType.name }} — 户型详情</h3>

        <!-- 户型图 -->
        <div class="ut-images" v-if="selectedUnitType.image_urls?.length">
          <el-image v-for="(url, i) in selectedUnitType.image_urls" :key="i"
            :src="url" fit="cover"
            style="width:200px;height:140px;border-radius:8px;margin-right:8px"
            preview-teleported :preview-src-list="selectedUnitType.image_urls" />
        </div>

        <!-- 户型参数 -->
        <el-descriptions :column="4" border size="small" style="margin:16px 0">
          <el-descriptions-item label="室/厅/卫">{{ selectedUnitType.bedrooms }}室{{ selectedUnitType.hall_count }}厅{{ selectedUnitType.bathrooms }}卫</el-descriptions-item>
          <el-descriptions-item label="面积">{{ selectedUnitType.area_sqm }}㎡</el-descriptions-item>
          <el-descriptions-item label="标准月租">{{ cur(selectedUnitType.currency) }}{{ Number(selectedUnitType.base_rent).toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item label="押金">{{ selectedUnitType.deposit_amount ? cur(selectedUnitType.currency)+selectedUnitType.deposit_amount : '-' }} / {{ depositLabel(selectedUnitType.deposit_type) }}</el-descriptions-item>
          <el-descriptions-item label="最短租期">{{ selectedUnitType.min_stay_months }}个月</el-descriptions-item>
          <el-descriptions-item label="户型配套" :span="3">
            <el-tag v-for="a in (selectedUnitType.amenities||[])" :key="a" size="small" style="margin-right:4px">{{ a }}</el-tag>
            <span v-if="!selectedUnitType.amenities?.length">-</span>
          </el-descriptions-item>
        </el-descriptions>

        <!-- ═══ 第四层：可租房间 ═══ -->
        <h4 style="margin-top:20px">🛏️ {{ selectedUnitType.room_count > 0 ? '可租房间 ('+selectedUnitType.room_count+'间)' : '暂无房间' }}</h4>
        <el-table v-if="selectedUnitType.rooms?.length" :data="selectedUnitType.rooms" stripe size="small">
          <el-table-column prop="room_number" label="房号" width="100" />
          <el-table-column prop="floor" label="楼层" width="80"><template #default="{row}">{{ row.floor ?? '-' }}</template></el-table-column>
          <el-table-column label="专属优惠" width="100"><template #default="{row}">{{ row.special_discount || '-' }}</template></el-table-column>
          <el-table-column prop="available_from" label="可入住" width="120" />
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{row}"><el-tag size="small" :type="row.status==='available'?'success':'warning'">{{ row.status==='available'?'可租':'已租' }}</el-tag></template>
          </el-table-column>
        </el-table>
        <div v-else style="color:#c0c4cc;padding:16px 0">该户型暂无在售房间</div>
      </div>
    </div>

    <el-empty v-else description="公寓不存在或已下架" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'

const route = useRoute()
const building = ref<any>(null)
const selectedUnitType = ref<any>(null)
const loading = ref(false)

function depositLabel(t: string) {
  const m: any = { one_month: '押一付一', one_three: '押一付三', two_month: '押二付一', three_month: '押三付一', half_month: '押半付一', free: '免押金', custom: '自定义' }
  return m[t] || t || '-'
}

function selectUnitType(ut: any) { selectedUnitType.value = ut }
const curMap: Record<string,string> = { CNY:'¥', USD:'$', GBP:'£', EUR:'€', AUD:'A$', SGD:'S$', CAD:'C$', HKD:'HK$', JPY:'¥', KRW:'₩' }
function cur(c?: string) { return curMap[c||'CNY'] || '¥' }

// 四大板块 amenity 分类定义
const secAmenities = ['24小时安保','监控系统(CCTV)','智能门禁','电子门锁','前台/礼宾','消防系统','夜间巡逻']
const svcAmenities = ['代收包裹','维修服务','公共区域保洁','定期社交活动','接机服务','班车接驳','入住礼包','管家服务']
const facAmenities = ['电梯','洗衣房','自行车库','停车场','公共厨房','快递柜/信箱','自习室','影音室','公共休闲区','屋顶露台','庭院/花园','会议室']
const spAmenities  = ['健身房','游泳池','篮球场','瑜伽室','游戏室','BBQ区','乒乓球/台球']
function getCategoryAmenities(all: string[], cat: string): string[] {
  const map: Record<string, string[]> = { security: secAmenities, service: svcAmenities, facility: facAmenities, sport: spAmenities }
  return (all || []).filter(a => (map[cat] || []).includes(a))
}

async function loadBuilding() {
  loading.value = true
  try {
    const id = route.params.id
    const r = await api.get(`/properties/${id}`)
    const room = r.data
    // 用 room 数据拼装为 building 格式（兼容模板）
    building.value = {
      id: room.id,
      name: room.title || room.address,
      address: room.address,
      description: room.description,
      latitude: room.latitude,
      longitude: room.longitude,
      amenities: room.amenities || [],
      images: room.images || [],
      unit_types: [],
      female_only: false,
      couples_allowed: false,
    }
    // 地图
    if (room.latitude && room.longitude) {
      await nextTick()
      initMap(room.latitude, room.longitude)
    }
    // 如果有 unit_type_id，尝试取户型
    if (room.unit_type_id) {
      try {
        const utRes = await api.get(`/unit-types/${room.unit_type_id}`)
        const ut = utRes.data
        ut.room_count = 1
        ut.rooms = [{
          id: room.id, room_number: room.room_number,
          floor: room.floor, special_discount: room.special_discount,
          available_from: room.available_from, status: room.status,
        }]
        building.value.unit_types = [ut]
        selectedUnitType.value = ut
      } catch { /* unit_type not available */ }
    }
    // 如果没取到户型，尝试取同 institute 的 unit_types
    if (!building.value.unit_types?.length && room.institute_id) {
      try {
        const utsRes = await api.get('/unit-types', { params: { institute_id: room.institute_id, page_size: 10 } })
        const uts = (utsRes.data.items || utsRes.data || []).map((ut: any) => ({
          ...ut, room_count: 0, rooms: []
        }))
        if (uts.length) building.value.unit_types = uts
      } catch { /* */ }
    }
  } catch { /* */ }
  finally { loading.value = false }
}

function initMap(lat: number, lng: number) {
  const el = document.getElementById('detail-map')
  if (!el) return
  const L = (window as any).L
  if (!L) {
    const s = document.createElement('script')
    s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
    s.onload = () => {
      const lib = (window as any).L
      const m = lib.map('detail-map').setView([lat, lng], 15)
      lib.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(m)
      lib.marker([lat, lng]).addTo(m)
      setTimeout(() => m.invalidateSize(), 300)
    }
    document.head.appendChild(s)
  } else {
    const m = L.map('detail-map').setView([lat, lng], 15)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(m)
    L.marker([lat, lng]).addTo(m)
    setTimeout(() => m.invalidateSize(), 300)
  }
}

onMounted(() => {
  if (!document.getElementById('leaflet-css')) {
    const c = document.createElement('link'); c.id = 'leaflet-css'; c.rel = 'stylesheet'
    c.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
    document.head.appendChild(c)
  }
  loadBuilding()
})
</script>

<style scoped>
.detail-page { max-width: 960px; margin: 0 auto; padding-bottom: 40px }
.no-image { height: 200px; background: #f5f6f8; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 64px }
.building-header { margin: 20px 0 }
.building-header h1 { font-size: 24px; color: #303133; margin: 0 0 8px }
.addr { color: #909399; margin: 0 0 4px }
.desc { color: #606266; margin: 8px 0 }
.phone { color: #909399; font-size: 14px }

.special-tags { display: flex; gap: 10px; margin: 12px 0 }
.amenities-section { margin: 16px 0 }
.amenities-section h3 { font-size: 16px; color: #303133; margin: 0 0 10px }
.amenity-cat { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 8px }
.cat-label { font-size: 13px; color: #606266; font-weight: 600; white-space: nowrap; min-width: 80px; padding-top: 2px }
.amenity-tags { display: flex; flex-wrap: wrap; gap: 6px }

.map-section { margin: 20px 0 }
.map-section h3 { font-size: 16px; color: #303133; margin: 0 0 10px }

.unit-tabs { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 12px }
.unit-tab { border: 2px solid #e4e7ed; border-radius: 12px; padding: 12px 16px; cursor: pointer; min-width: 160px; transition: all 0.2s }
.unit-tab:hover { border-color: #FF6B35 }
.unit-tab.active { border-color: #FF6B35; background: #fff4ed }
.ut-name { font-weight: 600; font-size: 15px; color: #303133 }
.ut-info { font-size: 13px; color: #909399; margin: 2px 0 }
.ut-rent { font-size: 16px; font-weight: 700; color: #f56c6c; margin: 4px 0 }

.ut-detail h3, .ut-detail h4 { font-size: 16px; color: #303133; margin: 0 0 10px }
.ut-images { margin: 10px 0; display: flex; flex-wrap: wrap }
</style>
