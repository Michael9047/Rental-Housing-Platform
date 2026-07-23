<template>
  <div class="detail-page" v-loading="loading">
    <div v-if="building">
      <!-- ═══════ 第一层：公寓头部 — 全宽大图 ═══════ -->
      <div class="hero-section">
        <div v-if="building.images?.length" class="hero-carousel">
          <el-carousel :interval="5000" height="420px" indicator-position="none" arrow="always">
            <el-carousel-item v-for="img in building.images" :key="img.id">
              <img :src="img.filename?.startsWith('http') ? img.filename : '/api/v1/uploads/'+img.filename" class="hero-img" alt="" />
            </el-carousel-item>
          </el-carousel>
          <div class="hero-overlay">
            <h1 class="hero-title">{{ building.name }}</h1>
            <p class="hero-addr" v-if="building.address">📍 {{ building.address }}</p>
          </div>
        </div>
        <div v-else class="hero-placeholder">
          <span class="hero-icon">🏢</span>
          <h1 class="hero-title">{{ building.name }}</h1>
          <p class="hero-addr" v-if="building.address">📍 {{ building.address }}</p>
        </div>
      </div>

      <!-- ═══════ 快捷操作行 ═══════ -->
      <div class="quick-info-bar">
        <div class="quick-tags">
          <span v-if="building.female_only" class="quick-tag tag-pink">👩 女生独栋</span>
          <span v-if="building.couples_allowed" class="quick-tag tag-purple">💑 支持情侣入住</span>
        </div>
        <div class="quick-actions">
          <el-button type="success" round :icon="inCart ? 'Check' : 'Plus'" :loading="cartLoading" @click.stop="toggleCart">
            {{ inCart ? '已加入候选' : '加入候选' }}
          </el-button>
          <span class="quick-phone" v-if="building.contact_phone">📞 {{ building.contact_phone }}</span>
        </div>
      </div>

      <!-- ═══════ 公寓简介 ═══════ -->
      <div class="intro-section" v-if="building.description">
        <p class="intro-text">{{ building.description }}</p>
      </div>

      <!-- ═══════ 公寓配套 — 卡片式四大板块 ═══════ -->
      <div class="amenities-section" v-if="building.amenities?.length">
        <h2 class="section-heading">🏗️ 公寓配套 & 服务</h2>
        <div class="amenity-cards">
          <div class="amenity-card" v-if="getCategoryAmenities(building.amenities, 'security').length">
            <div class="amenity-card-icon">🛡️</div>
            <div class="amenity-card-title">安保</div>
            <div class="amenity-card-tags">
              <span v-for="a in getCategoryAmenities(building.amenities, 'security')" :key="a" class="amenity-tag">{{ a }}</span>
            </div>
          </div>
          <div class="amenity-card" v-if="getCategoryAmenities(building.amenities, 'service').length">
            <div class="amenity-card-icon">🛎️</div>
            <div class="amenity-card-title">服务</div>
            <div class="amenity-card-tags">
              <span v-for="a in getCategoryAmenities(building.amenities, 'service')" :key="a" class="amenity-tag">{{ a }}</span>
            </div>
          </div>
          <div class="amenity-card" v-if="getCategoryAmenities(building.amenities, 'facility').length">
            <div class="amenity-card-icon">🏠</div>
            <div class="amenity-card-title">公用设施</div>
            <div class="amenity-card-tags">
              <span v-for="a in getCategoryAmenities(building.amenities, 'facility')" :key="a" class="amenity-tag">{{ a }}</span>
            </div>
          </div>
          <div class="amenity-card" v-if="getCategoryAmenities(building.amenities, 'sport').length">
            <div class="amenity-card-icon">⚽</div>
            <div class="amenity-card-title">运动娱乐</div>
            <div class="amenity-card-tags">
              <span v-for="a in getCategoryAmenities(building.amenities, 'sport')" :key="a" class="amenity-tag">{{ a }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══════ 地图 ═══════ -->
      <div class="map-section" v-if="building.latitude && building.longitude">
        <h2 class="section-heading">🗺️ 位置</h2>
        <div id="detail-map" class="map-container"></div>
      </div>

      <!-- ═══════ 第二层：可选户型 ═══════ -->
      <div class="unit-types-section">
        <h2 class="section-heading">📐 可选户型 <span class="heading-badge" v-if="building.unit_types?.length">{{ building.unit_types.length }} 种</span></h2>
        <div class="unit-type-grid" v-if="building.unit_types?.length">
          <div
            v-for="ut in building.unit_types" :key="ut.id"
            :class="['unit-type-card', { active: selectedUnitType?.id === ut.id }]"
            @click="selectUnitType(ut)"
          >
            <!-- 户型图缩略图 -->
            <div class="ut-card-cover">
              <img v-if="ut.image_urls?.[0]" :src="ut.image_urls[0]" alt="" class="ut-cover-img" />
              <div v-else class="ut-cover-placeholder">🏠</div>
              <div class="ut-card-status">
                <span :class="ut.room_count > 0 ? 'status-available' : 'status-full'">
                  {{ ut.room_count > 0 ? ut.room_count+'间可租' : '暂满' }}
                </span>
              </div>
            </div>
            <!-- 户型信息 -->
            <div class="ut-card-body">
              <h3 class="ut-card-name">{{ ut.name }}</h3>
              <div class="ut-card-specs">
                <span class="spec-item">{{ ut.bedrooms }}室{{ ut.hall_count }}厅{{ ut.bathrooms }}卫</span>
                <span class="spec-divider">·</span>
                <span class="spec-item">{{ ut.area_sqm }}㎡</span>
              </div>
              <div class="ut-card-price">
                <span class="price-value">{{ cur(ut.currency) }}{{ Number(ut.base_rent).toLocaleString() }}</span>
                <span class="price-period">/月</span>
              </div>
              <div class="ut-card-tags" v-if="ut.amenities?.length">
                <span v-for="a in ut.amenities.slice(0, 4)" :key="a" class="ut-tag">{{ a }}</span>
                <span v-if="ut.amenities.length > 4" class="ut-tag ut-tag-more">+{{ ut.amenities.length - 4 }}</span>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无户型数据" :image-size="80" />
      </div>

      <!-- ═══════ 第三层：选中户型详情 ═══════ -->
      <div class="ut-detail-section" v-if="selectedUnitType">
        <h2 class="section-heading">{{ selectedUnitType.name }} — 户型详情</h2>

        <!-- 户型图集 -->
        <div class="ut-gallery" v-if="selectedUnitType.image_urls?.length">
          <el-image
            v-for="(url, i) in selectedUnitType.image_urls" :key="i"
            :src="url" fit="cover"
            class="ut-gallery-img"
            preview-teleported :preview-src-list="selectedUnitType.image_urls"
          />
        </div>

        <!-- 户型参数卡 -->
        <div class="ut-specs-grid">
          <div class="spec-card">
            <div class="spec-icon">🛏️</div>
            <div class="spec-label">户型格局</div>
            <div class="spec-value">{{ selectedUnitType.bedrooms }}室{{ selectedUnitType.hall_count }}厅{{ selectedUnitType.bathrooms }}卫</div>
          </div>
          <div class="spec-card">
            <div class="spec-icon">📐</div>
            <div class="spec-label">面积</div>
            <div class="spec-value">{{ selectedUnitType.area_sqm }}㎡</div>
          </div>
          <div class="spec-card">
            <div class="spec-icon">💰</div>
            <div class="spec-label">标准月租</div>
            <div class="spec-value price">{{ cur(selectedUnitType.currency) }}{{ Number(selectedUnitType.base_rent).toLocaleString() }}</div>
          </div>
          <div class="spec-card">
            <div class="spec-icon">🔒</div>
            <div class="spec-label">押金</div>
            <div class="spec-value">{{ selectedUnitType.deposit_amount ? cur(selectedUnitType.currency)+selectedUnitType.deposit_amount : '-' }} / {{ depositLabel(selectedUnitType.deposit_type) }}</div>
          </div>
          <div class="spec-card">
            <div class="spec-icon">📅</div>
            <div class="spec-label">最短租期</div>
            <div class="spec-value">{{ selectedUnitType.min_stay_months }} 个月</div>
          </div>
          <div class="spec-card full-width" v-if="selectedUnitType.amenities?.length">
            <div class="spec-icon">✨</div>
            <div class="spec-label">户型配套</div>
            <div class="spec-value">
              <span v-for="a in selectedUnitType.amenities" :key="a" class="spec-amenity-tag">{{ a }}</span>
            </div>
          </div>
        </div>
        <!-- 预定按钮 -->
        <div class="ut-book-bar">
          <el-button type="primary" size="large" round @click="goBook" style="min-width:200px;font-weight:600">
            🏠 立即预定 · {{ cur(selectedUnitType.currency) }}{{ Number(selectedUnitType.base_rent).toLocaleString() }}/月
          </el-button>
        </div>
      </div>

      <!-- 底部占位 -->
      <div class="page-bottom" />
    </div>

    <el-empty v-else description="公寓不存在或已下架" :image-size="120" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Check } from '@element-plus/icons-vue'
import api from '@/services/api'
import { useCartStore } from '@/stores/cart'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const cartStore = useCartStore()
const authStore = useAuthStore()
const building = ref<any>(null)
const selectedUnitType = ref<any>(null)
const loading = ref(false)
const cartLoading = ref(false)
const inCart = computed(() => building.value ? cartStore.has(building.value.id) : false)

async function toggleCart() {
  if (cartLoading.value || !building.value) return
  if (!authStore.isLoggedIn) {
    ElMessage.warning('请先登录后再使用候选清单')
    router.push('/login')
    return
  }
  cartLoading.value = true
  try {
    if (inCart.value) {
      await cartStore.remove(building.value.id)
      ElMessage.info('已移出候选清单')
    } else {
      await cartStore.add(building.value.id)
      ElMessage.success('已加入候选清单')
    }
  } catch {
    ElMessage.error('操作失败，请稍后重试')
  } finally { cartLoading.value = false }
}

function goBook() {
  if (!building.value || !selectedUnitType.value) return
  router.push({
    path: '/booking/confirm',
    query: {
      property_id: String(building.value.id),
      unit_type_id: String(selectedUnitType.value.id),
    }
  })
}

function depositLabel(t: string) {
  const m: any = { one_month: '押一付一', one_three: '押一付三', two_month: '押二付一', three_month: '押三付一', half_month: '押半付一', free: '免押金', custom: '自定义' }
  return m[t] || t || '-'
}

function selectUnitType(ut: any) {
  selectedUnitType.value = ut
  // 滚动到详情区
  nextTick(() => {
    const el = document.querySelector('.ut-detail-section')
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

const curMap: Record<string,string> = { CNY:'¥', USD:'$', GBP:'£', EUR:'€', AUD:'A$', SGD:'S$', CAD:'C$', HKD:'HK$', JPY:'¥', KRW:'₩' }
function cur(c?: string) { return curMap[c||'CNY'] || '¥' }

// 四大板块 amenity 分类
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
    // 用 properties API 取房源（兼容 room/:id 路由）
    const r = await api.get(`/public/rooms/${id}`)
    const room = r.data
    building.value = {
      id: room.id, name: room.title || room.address,
      address: room.address, description: room.description,
      latitude: room.latitude, longitude: room.longitude,
      amenities: room.amenities || [], images: room.images || [],
      contact_phone: null, female_only: false, couples_allowed: false,
      unit_types: [],
    }
    if (room.latitude && room.longitude) {
      await nextTick(); initMap(room.latitude, room.longitude)
    }
    // 取户型信息
    if (room.unit_type_id) {
      try {
        const utRes = await api.get(`/unit-types/${room.unit_type_id}`)
        building.value.unit_types = [{ ...utRes.data, room_count: 1,
          rooms: [{ id: room.id, room_number: room.room_number, floor: room.floor,
            special_discount: room.special_discount, available_from: room.available_from,
            status: room.status }]
        }]
        selectedUnitType.value = building.value.unit_types[0]
      } catch { /* */ }
    }
    if (!building.value.unit_types?.length && room.institute_id) {
      try {
        const utsRes = await api.get('/unit-types', { params: { institute_id: room.institute_id, page_size: 20 } })
        building.value.unit_types = (utsRes.data.items || []).map((ut: any) => ({ ...ut, room_count: 0, rooms: [] }))
      } catch { /* */ }
    }
  } catch (e: any) { console.error('PropertyDetail load failed:', e?.message || e) }
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
/* ═══════════════════════════════════════════════
   全局
   ═══════════════════════════════════════════════ */
.detail-page {
  max-width: 1060px;
  margin: 0 auto;
  padding: 0 24px 60px;
}

.page-bottom { height: 1px }

/* ═══════════════════════════════════════════════
   章节标题
   ═══════════════════════════════════════════════ */
.section-heading {
  font-size: 22px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 20px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.heading-badge {
  font-size: 14px;
  font-weight: 600;
  color: #909399;
  background: #f0f2f5;
  padding: 4px 12px;
  border-radius: 20px;
}

/* ═══════════════════════════════════════════════
   Hero 图片轮播
   ═══════════════════════════════════════════════ */
.hero-section {
  margin: 0 -24px 28px;
  position: relative;
}

.hero-carousel {
  position: relative;
}

.hero-carousel :deep(.el-carousel__container) {
  border-radius: 0;
}

.hero-img {
  width: 100%;
  height: 420px;
  object-fit: cover;
}

.hero-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 40px 60px 32px;
  background: linear-gradient(transparent, rgba(0,0,0,0.65));
  color: #fff;
  border-radius: 0 0 16px 16px;
}

.hero-overlay .hero-title {
  font-size: 30px;
  font-weight: 700;
  margin: 0 0 6px;
  text-shadow: 0 2px 8px rgba(0,0,0,0.3);
  color: #fff;
}

.hero-overlay .hero-addr {
  font-size: 15px;
  opacity: 0.9;
  margin: 0;
  color: #fff;
}

/* 无图 placeholder */
.hero-placeholder {
  height: 340px;
  background: linear-gradient(135deg, #2c3e50 0%, #34495e 40%, #4a6fa5 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff;
  border-radius: 0;
}

.hero-placeholder .hero-icon {
  font-size: 72px;
  margin-bottom: 16px;
  opacity: 0.6;
}

.hero-placeholder .hero-title {
  font-size: 30px;
  font-weight: 700;
  margin: 0 0 8px;
  color: #fff;
}

.hero-placeholder .hero-addr {
  font-size: 15px;
  opacity: 0.8;
  margin: 0;
  color: #fff;
}

/* ═══════════════════════════════════════════════
   快捷标签行
   ═══════════════════════════════════════════════ */
.quick-info-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 28px;
  padding: 16px 20px;
  background: #fafbfc;
  border-radius: 14px;
  border: 1px solid #ebeef5;
}

.quick-tags {
  display: flex;
  gap: 10px;
}

.quick-tag {
  font-size: 14px;
  font-weight: 600;
  padding: 6px 16px;
  border-radius: 8px;
}

.quick-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ut-book-bar {
  margin-top: 24px;
  text-align: center;
}

.tag-pink {
  background: #fef0f0;
  color: #e0485c;
  border: 1px solid #fcd4da;
}

.tag-purple {
  background: #f4f0fe;
  color: #7c3aed;
  border: 1px solid #e0d4fc;
}

.quick-phone {
  font-size: 15px;
  color: #606266;
  font-weight: 500;
}

/* ═══════════════════════════════════════════════
   公寓简介
   ═══════════════════════════════════════════════ */
.intro-section {
  margin-bottom: 32px;
}

.intro-text {
  font-size: 16px;
  line-height: 1.8;
  color: #4a5568;
  margin: 0;
}

/* ═══════════════════════════════════════════════
   公寓配套 — 卡片式
   ═══════════════════════════════════════════════ */
.amenities-section {
  margin-bottom: 36px;
}

.amenity-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 16px;
}

.amenity-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 14px;
  padding: 20px;
  transition: box-shadow 0.2s, transform 0.2s;
}

.amenity-card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  transform: translateY(-1px);
}

.amenity-card-icon {
  font-size: 28px;
  margin-bottom: 8px;
}

.amenity-card-title {
  font-size: 16px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 12px;
}

.amenity-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.amenity-tag {
  display: inline-block;
  font-size: 13px;
  padding: 4px 10px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  color: #606266;
}

/* ═══════════════════════════════════════════════
   地图
   ═══════════════════════════════════════════════ */
.map-section {
  margin-bottom: 40px;
}

.map-container {
  width: 100%;
  height: 280px;
  border-radius: 14px;
  border: 1px solid #e4e7ed;
  overflow: hidden;
}

/* ═══════════════════════════════════════════════
   户型卡片网格
   ═══════════════════════════════════════════════ */
.unit-types-section {
  margin-bottom: 40px;
}

.unit-type-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 18px;
}

.unit-type-card {
  background: #fff;
  border: 2px solid #ebeef5;
  border-radius: 16px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.25s ease;
}

.unit-type-card:hover {
  border-color: #FF6B35;
  box-shadow: 0 6px 24px rgba(255,107,53,0.1);
  transform: translateY(-3px);
}

.unit-type-card.active {
  border-color: #FF6B35;
  background: #fff9f6;
  box-shadow: 0 6px 24px rgba(255,107,53,0.18);
}

/* 户型卡片封面 */
.ut-card-cover {
  position: relative;
  height: 180px;
  background: #f5f6f8;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.ut-cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ut-cover-placeholder {
  font-size: 56px;
  opacity: 0.25;
}

.ut-card-status {
  position: absolute;
  top: 12px;
  right: 12px;
}

.status-available {
  font-size: 13px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 20px;
  background: rgba(103, 194, 58, 0.15);
  color: #529b2e;
}

.status-full {
  font-size: 13px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 20px;
  background: rgba(144, 147, 153, 0.15);
  color: #909399;
}

/* 户型卡片内容 */
.ut-card-body {
  padding: 18px 20px 20px;
}

.ut-card-name {
  font-size: 18px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 8px;
}

.ut-card-specs {
  font-size: 15px;
  color: #606266;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 0;
}

.spec-divider {
  margin: 0 8px;
  color: #c0c4cc;
}

.ut-card-price {
  margin-bottom: 12px;
}

.price-value {
  font-size: 22px;
  font-weight: 700;
  color: #f56c6c;
}

.price-period {
  font-size: 14px;
  color: #909399;
  margin-left: 2px;
}

.ut-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ut-tag {
  font-size: 12px;
  padding: 3px 10px;
  background: #f5f7fa;
  border-radius: 6px;
  color: #909399;
}

.ut-tag-more {
  background: #fffaeb;
  color: #e6a23c;
}

/* ═══════════════════════════════════════════════
   选中户型详情
   ═══════════════════════════════════════════════ */
.ut-detail-section {
  background: #fafbfc;
  border: 1px solid #ebeef5;
  border-radius: 18px;
  padding: 32px;
  margin-bottom: 40px;
}

.ut-detail-section .section-heading {
  font-size: 20px;
  margin-bottom: 24px;
}

/* 户型图集 */
.ut-gallery {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 28px;
}

.ut-gallery-img {
  width: 220px;
  height: 150px;
  border-radius: 12px;
  object-fit: cover;
  cursor: pointer;
  transition: transform 0.2s;
}

.ut-gallery-img:hover {
  transform: scale(1.03);
}

/* 户型参数卡片网格 */
.ut-specs-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.spec-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 14px;
  padding: 20px;
  transition: box-shadow 0.2s;
}

.spec-card:hover {
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}

.spec-card.full-width {
  grid-column: 1 / -1;
}

.spec-icon {
  font-size: 24px;
  margin-bottom: 8px;
}

.spec-label {
  font-size: 13px;
  color: #909399;
  font-weight: 500;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.spec-value {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.spec-value.price {
  color: #f56c6c;
  font-size: 18px;
}

.spec-amenity-tag {
  display: inline-block;
  font-size: 13px;
  padding: 5px 12px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  color: #606266;
  margin: 3px 4px 3px 0;
  font-weight: 500;
}

@media (max-width: 768px) {
  .detail-page { padding: 0 12px 40px }
  .hero-section { margin: 0 -12px 20px }
  .hero-img, .hero-carousel :deep(.el-carousel__container) { height: 260px !important }
  .hero-overlay { padding: 24px 28px 20px }
  .hero-overlay .hero-title, .hero-placeholder .hero-title { font-size: 24px }
  .hero-placeholder { height: 240px }
  .unit-type-grid { grid-template-columns: 1fr }
  .ut-specs-grid { grid-template-columns: repeat(2, 1fr) }
  .amenity-cards { grid-template-columns: 1fr }
  .ut-detail-section { padding: 20px }
  .ut-gallery-img { width: 100%; height: auto; aspect-ratio: 4/3 }
}
</style>
