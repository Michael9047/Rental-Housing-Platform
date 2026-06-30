<template>
  <div class="detail-page" v-loading="loading">
    <div v-if="property">
      <!-- Breadcrumb -->
      <div class="detail-topbar">
        <el-button text :icon="ArrowLeft" @click="$router.back()">返回</el-button>
        <div class="topbar-actions">
          <el-button text :icon="Star" :type="isFavorited ? 'warning' : 'default'" @click="toggleFavorite">
            {{ isFavorited ? '已收藏' : '收藏' }}
          </el-button>
          <el-button text :icon="Share" @click="shareProperty">分享</el-button>
        </div>
      </div>

      <!-- Image Gallery -->
      <div v-if="sortedImages.length > 0" class="gallery">
        <el-carousel :interval="4000" height="420px" trigger="click" class="gallery-carousel">
          <el-carousel-item v-for="(img, idx) in sortedImages" :key="img.id">
            <el-image
              :src="`/api/v1/uploads/${img.filename}`"
              fit="cover"
              class="gallery-img"
              :preview-src-list="allImageUrls"
              :initial-index="idx"
              preview-teleported
            />
          </el-carousel-item>
        </el-carousel>
        <div class="gallery-thumbs">
          <div
            v-for="(img, idx) in sortedImages.slice(0, 6)"
            :key="img.id"
            class="thumb"
            :class="{ active: currentSlide === idx }"
            @click="currentSlide = idx"
          >
            <img :src="`/api/v1/uploads/${img.filename}`" />
          </div>
        </div>
      </div>

      <!-- Header Info -->
      <el-card shadow="never" class="info-card">
        <div class="info-header">
          <div>
            <h1 class="property-title">{{ property.title }}</h1>
            <div class="property-meta">
              <el-tag :type="statusTagType">{{ statusLabel }}</el-tag>
              <el-tag type="info">{{ typeLabel }}</el-tag>
              <span class="meta-loc">{{ property.district }} · {{ property.address }}</span>
            </div>
          </div>
        </div>

        <div class="price-row">
          <div class="price-main">
            <span class="price-value">¥{{ property.price_monthly }}</span>
            <span class="price-unit">/月</span>
            <span v-if="property.deposit_amount" class="price-deposit">
              押金 ¥{{ property.deposit_amount }}
            </span>
            <span v-if="property.service_fee_rate" class="price-fee">
              · 服务费 {{ (property.service_fee_rate * 100).toFixed(0) }}%
            </span>
          </div>
          <el-button type="primary" size="large" round @click="showBookingDialog = true">
            预约看房
          </el-button>
        </div>
      </el-card>

      <!-- Key Specs Grid -->
      <el-card shadow="never" class="info-card">
        <el-row :gutter="16">
          <el-col :span="6">
            <div class="spec-item">
              <span class="spec-icon">📐</span>
              <span class="spec-label">户型</span>
              <span class="spec-value">{{ property.bedrooms }}室{{ property.bathrooms }}卫</span>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="spec-item">
              <span class="spec-icon">📏</span>
              <span class="spec-label">面积</span>
              <span class="spec-value">{{ property.area_sqm ? property.area_sqm + '㎡' : '暂无' }}</span>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="spec-item">
              <span class="spec-icon">🏢</span>
              <span class="spec-label">类型</span>
              <span class="spec-value">{{ typeLabel }}</span>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="spec-item">
              <span class="spec-icon">✅</span>
              <span class="spec-label">状态</span>
              <span class="spec-value">{{ statusLabel }}</span>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- Description -->
      <el-card v-if="property.description" shadow="never" class="info-card">
        <template #header><span class="card-header-text">📝 房源描述</span></template>
        <p class="desc-text">{{ property.description }}</p>
      </el-card>

      <!-- Facilities -->
      <el-card shadow="never" class="info-card">
        <template #header><span class="card-header-text">🏪 配套设施</span></template>
        <div class="facility-groups">
          <div class="facility-group">
            <span class="facility-group-label">🏠 基础配套</span>
            <div class="facility-tags">
              <el-tag v-for="f in baseFacilities" :key="f" type="info" effect="plain" size="large" round>
                {{ f }}
              </el-tag>
            </div>
          </div>
          <div v-if="isOverseas && overseasFacilities.length > 0" class="facility-group">
            <span class="facility-group-label">🌍 海外专属配套</span>
            <div class="facility-tags">
              <el-tag v-for="f in overseasFacilities" :key="f" type="warning" effect="plain" size="large" round>
                {{ f }}
              </el-tag>
            </div>
          </div>
        </div>
        <span v-if="baseFacilities.length === 0" class="no-data">暂无配套设施信息</span>
      </el-card>

      <!-- Map Area (OpenStreetMap) -->
      <el-card shadow="never" class="info-card">
        <template #header><span class="card-header-text">🗺️ 位置信息</span></template>
        <p class="map-address">
          <strong>📍 {{ property.address }}</strong>
          <span v-if="property.latitude" class="map-coords">
            ({{ Number(property.latitude).toFixed(4) }}, {{ Number(property.longitude).toFixed(4) }})
          </span>
        </p>
        <div v-if="property.latitude && property.longitude" class="map-container">
          <iframe
            class="map-iframe"
            :src="mapSrc"
            frameborder="0"
            scrolling="no"
            loading="lazy"
          />
          <div class="map-overlay-actions">
            <el-link
              :href="`https://uri.amap.com/marker?position=${property.longitude},${property.latitude}`"
              target="_blank"
              type="primary"
              :underline="false"
              class="map-ext-link"
            >
              在高德地图中查看全景 ↗
            </el-link>
          </div>
          <p class="map-hint">地图中心红色标记：房源位置 · 自动标注周边POI</p>
        </div>
        <div v-else class="map-placeholder">
          <span class="map-icon">📍</span>
          <p>暂无精确坐标</p>
          <p class="map-hint">请联系房东获取详细位置信息</p>
        </div>
      </el-card>

      <!-- AI POI Analysis -->
      <el-card v-if="poiData" shadow="never" class="info-card">
        <template #header><span class="card-header-text">🤖 AI 智能周边分析</span></template>
        <div v-loading="poiLoading">
          <blockquote class="poi-summary">{{ poiData.content }}</blockquote>
          <div v-if="poiData.poi_data" class="poi-grid">
            <div v-for="(items, category) in poiData.poi_data" :key="category" class="poi-group">
              <h4>{{ category }}</h4>
              <ul>
                <li v-for="item in items" :key="item.name">
                  {{ item.name }} <span class="poi-dist">{{ item.distance }}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </el-card>

      <!-- Reviews Section -->
      <section class="reviews-section" v-if="property">
        <h2 class="section-title">💬 用户评价</h2>
        <div class="reviews-summary">
          <div class="reviews-score">
            <span class="score-num">{{ avgRating }}</span>
            <span class="score-unit">/5</span>
          </div>
          <div class="reviews-stars">
            <el-rate v-model="avgRating" disabled show-score-text :texts="[avgRatingText]" />
          </div>
          <span class="reviews-count">共 {{ reviews.length }} 条评价</span>
        </div>
        <div class="reviews-list">
          <div v-for="(r, i) in reviews" :key="i" class="review-item">
            <div class="review-avatar">
              <el-avatar :size="40" :style="{ background: r.avatarColor }">{{ r.avatar }}</el-avatar>
            </div>
            <div class="review-body">
              <div class="review-header">
                <span class="review-user">{{ r.user }}</span>
                <el-rate v-model="r.rating" disabled size="small" />
                <span class="review-date">{{ r.date }}</span>
              </div>
              <p class="review-text">{{ r.text }}</p>
              <div v-if="r.reply" class="review-reply">
                <span class="reply-badge">房东回复</span>
                <p>{{ r.reply }}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Similar Properties -->
      <section class="similar-section">
        <h2 class="section-title">同片区相似房源</h2>
        <div class="property-grid">
          <PropertyCard
            v-for="p in similarProperties"
            :key="p.id"
            :property="p"
            :show-quick-book="true"
            @book="openBookingDialogForCard"
          />
        </div>
      </section>
    </div>

    <el-empty v-else-if="!loading" description="房源未找到" />

    <!-- Bottom Fixed Bar -->
    <div class="bottom-bar" v-if="property">
      <el-button size="large" @click="$router.back()">返回搜索列表</el-button>
      <el-button type="primary" size="large" round @click="showBookingDialog = true">
        立即支付押金预订
      </el-button>
    </div>

    <!-- Booking Date Dialog -->
    <BookingDateDialog
      v-model="showBookingDialog"
      :property-id="property?.id || 0"
      :property-title="property?.title"
      :property-price="property?.price_monthly"
      @confirm="handleBookingConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Star, Share } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { usePropertyStore } from '@/stores/property'
import { useAuthStore } from '@/stores/auth'
import { propertyService, type PropertyPOI } from '@/services/property'
import { favoriteService } from '@/services/favorite'
import { storeToRefs } from 'pinia'
import PropertyCard from '@/components/PropertyCard.vue'
import BookingDateDialog from '@/components/BookingDateDialog.vue'
import type { Property, PropertyType, PropertyStatus } from '@/types/property'

const route = useRoute()
const router = useRouter()
const propertyStore = usePropertyStore()
const authStore = useAuthStore()
const { currentProperty: property, loading } = storeToRefs(propertyStore)

const currentSlide = ref(0)

// Map
const mapSrc = computed(() => {
  if (!property.value?.latitude || !property.value?.longitude) return ''
  const lat = Number(property.value.latitude)
  const lng = Number(property.value.longitude)
  const bbox = `${lng - 0.008},${lat - 0.005},${lng + 0.008},${lat + 0.005}`
  return `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lng}`
})

// Facilities — smart dynamic based on property
const isOverseas = computed(() => {
  if (!property.value) return false
  const d = property.value.district || ''
  return !/苏州|北京|上海|广州|深圳|杭州|南京|成都|武汉|重庆/.test(d)
})

const baseFacilities = computed(() => {
  if (!property.value) return []
  const p = property.value
  const f = ['电梯', '空调', '洗衣机', '冰箱', 'WiFi', '暖气']
  if (p.property_type === 'house') f.push('车位', '全屋家电')
  if (p.property_type === 'studio') f.push('独立卫浴', '储物间')
  if (p.area_sqm && p.area_sqm > 60) f.push('阳台')
  if (p.description && /宠物|猫|狗/.test(p.description)) f.push('可养宠物')
  return f.filter((v, i, a) => a.indexOf(v) === i)
})

const overseasFacilities = computed(() => {
  if (!property.value || !isOverseas.value) return []
  return ['健身房', '自习室', '签证咨询', '24小时前台', '校车接驳', '独立卫浴']
})

// Reviews (static mock — backend doesn't have reviews yet)
const reviews = [
  { user: '李明', avatar: '李', avatarColor: '#FF6B35', rating: 5, date: '2026-06-20', text: '房间很干净，采光好，房东人很nice。地铁就在楼下非常方便！', reply: '感谢李先生的认可，欢迎随时联系。' },
  { user: 'Emily', avatar: 'E', avatarColor: '#67c23a', rating: 4.5, date: '2026-06-15', text: 'Great location and friendly landlord. The apartment has everything I need for my study abroad year.', reply: 'Thanks Emily! Happy to help with your stay.' },
  { user: '王芳', avatar: '王', avatarColor: '#409eff', rating: 4, date: '2026-06-08', text: '配套齐全，周边买菜方便。唯一建议是洗衣机可以换个新的。', reply: '' },
  { user: '张伟', avatar: '张', avatarColor: '#e6a23c', rating: 5, date: '2026-05-28', text: '第三次租了，每次体验都很好。平台服务也很到位，推荐！', reply: '感谢老客户的支持！' },
]

const avgRating = computed(() => {
  if (reviews.length === 0) return 0
  const sum = reviews.reduce((a, r) => a + r.rating, 0)
  return Math.round(sum / reviews.length * 10) / 10
})

const avgRatingText = computed(() => {
  const r = avgRating.value
  if (r >= 4.5) return '超赞'
  if (r >= 4) return '好评'
  if (r >= 3) return '不错'
  return '一般'
})

// POI
const poiData = ref<PropertyPOI | null>(null)
const poiLoading = ref(false)

// Similar properties
const similarProperties = ref<Property[]>([])

// Booking dialog
const showBookingDialog = ref(false)

// Favorites
const isFavorited = ref(false)
const loadingProperty = ref(false)
const togglingFavorite = ref(false)

const statusLabels: Record<PropertyStatus, string> = {
  available: '可租', rented: '已租', maintenance: '维护中', offline: '已下架',
}
const typeLabels: Record<PropertyType, string> = {
  apartment: '公寓', house: '别墅', studio: '单间', shared: '合租',
}

const statusTagType = computed(() => {
  if (!property.value) return 'info'
  const map: Record<PropertyStatus, string> = {
    available: 'success', rented: 'warning', maintenance: 'info', offline: 'danger',
  }
  return map[property.value.status]
})

const statusLabel = computed(() => property.value ? statusLabels[property.value.status] : '')
const typeLabel = computed(() => property.value ? typeLabels[property.value.property_type] : '')

const sortedImages = computed(() => {
  const imgs = property.value?.images
  if (!imgs) return []
  return [...imgs].sort((a, b) => {
    if (a.is_primary) return -1
    if (b.is_primary) return 1
    return a.sort_order - b.sort_order
  })
})

const allImageUrls = computed(() =>
  sortedImages.value.map((img) => `/api/v1/uploads/${img.filename}`)
)

function openBookingDialogForCard(p: Property) {
  // Switch property first, then open dialog
  property.value = p
  showBookingDialog.value = true
}

function handleBookingConfirm(data: { propertyId: number; date: string; slot: string }) {
  showBookingDialog.value = false
  router.push({
    path: '/booking/confirm',
    query: { property_id: String(data.propertyId), date: data.date, slot: data.slot },
  })
}

async function checkFavoriteStatus() {
  if (!property.value || !authStore.isLoggedIn) {
    isFavorited.value = false
    return
  }
  try {
    isFavorited.value = await favoriteService.isFavorited(property.value.id)
  } catch {
    isFavorited.value = false
  }
}

async function toggleFavorite() {
  if (!property.value) return
  if (!authStore.isLoggedIn) {
    ElMessage.warning('请先登录后再收藏')
    return
  }
  if (togglingFavorite.value) return  // 防止连击
  togglingFavorite.value = true
  try {
    if (isFavorited.value) {
      await favoriteService.remove(property.value.id)
      isFavorited.value = false
      ElMessage.success('已取消收藏')
    } else {
      await favoriteService.add(property.value.id)
      isFavorited.value = true
      ElMessage.success('已添加收藏')
    }
  } catch {
    ElMessage.error('操作失败，请稍后重试')
  } finally {
    togglingFavorite.value = false
  }
}

function shareProperty() {
  if (!property.value) return
  const url = window.location.href
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(() => {
      ElMessage.success('链接已复制到剪贴板，可分享给好友')
    }).catch(() => {
      ElMessage.info(`分享链接：${url}`)
    })
  } else {
    ElMessage.info(`分享链接：${url}`)
  }
}

async function loadProperty(id: number) {
  if (isNaN(id) || id <= 0) return
  if (loadingProperty.value) return
  loadingProperty.value = true
  isFavorited.value = false
  try {
    await propertyStore.fetchById(id)
    if (property.value) {
      loadPOI(property.value.id)
      loadSimilar()
      await checkFavoriteStatus()
    }
  } catch { /* handled */ }
  finally { loadingProperty.value = false }
}

async function loadPOI(pid: number) {
  poiLoading.value = true
  try {
    const d = await propertyService.getPropertyPOI(pid)
    poiData.value = d
  } catch {
    poiData.value = null
  } finally {
    poiLoading.value = false
  }
}

async function loadSimilar() {
  try {
    const list = await propertyService.list({ limit: 3 })
    similarProperties.value = list.filter(p => p.id !== property.value?.id).slice(0, 3)
  } catch { similarProperties.value = [] }
}

// Watch route param changes (with immediate to cover onMounted)
const stopWatch = watch(() => route.params.id, (newId) => {
  poiData.value = null
  loadProperty(Number(newId))
}, { immediate: true })

onUnmounted(() => stopWatch())
</script>

<style scoped>
.detail-page {
  max-width: 960px;
  margin: 0 auto;
  padding-bottom: 80px;
}

/* ── Top Bar ──────────────────────── */

.detail-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

/* ── Gallery ──────────────────────── */

.gallery {
  margin-bottom: 20px;
  border-radius: var(--radius);
  overflow: hidden;
}

.gallery-carousel :deep(.el-carousel__container) {
  border-radius: var(--radius);
}

.gallery-img {
  width: 100%;
  height: 420px;
}

.gallery-thumbs {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.thumb {
  width: 60px;
  height: 44px;
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  opacity: 0.5;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.thumb.active {
  opacity: 1;
  border-color: var(--primary);
}

.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* ── Info Card ─────────────────────── */

.info-card {
  margin-bottom: 16px;
}

.card-header-text {
  font-size: 15px;
  font-weight: 600;
}

.property-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.property-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.meta-loc {
  font-size: 14px;
  color: var(--text-secondary);
}

.price-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-light);
}

.price-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--danger);
}

.price-unit {
  font-size: 15px;
  color: var(--text-muted);
  margin-left: 4px;
}

.price-deposit, .price-fee {
  font-size: 13px;
  color: var(--text-muted);
  margin-left: 8px;
}

/* ── Specs Grid ────────────────────── */

.spec-item {
  text-align: center;
  padding: 12px 0;
}

.spec-icon {
  font-size: 24px;
  display: block;
  margin-bottom: 4px;
}

.spec-label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.spec-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ── Description ───────────────────── */

.desc-text {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.8;
  white-space: pre-wrap;
}

/* ── Facilities ────────────────────── */

.facility-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.facility-group-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.facility-tags {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.no-data {
  color: var(--text-muted);
  font-size: 14px;
}

/* ── Map ───────────────────────────── */

.map-address {
  font-size: 14px;
  color: var(--text-primary);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.map-coords {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: normal;
}

.map-container {
  border-radius: var(--radius);
  overflow: hidden;
  border: 1px solid var(--border);
  position: relative;
}

.map-iframe {
  width: 100%;
  height: 360px;
  border: none;
}

.map-overlay-actions {
  position: absolute;
  top: 12px;
  right: 12px;
  background: var(--bg-white);
  border-radius: var(--radius-sm);
  padding: 6px 14px;
  box-shadow: var(--shadow);
}

.map-ext-link {
  font-size: 13px;
  font-weight: 500;
}

.map-hint {
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
  padding: 8px 0 4px;
  margin: 0;
}

.map-placeholder {
  margin-top: 16px;
  height: 240px;
  background: #f5f7fa;
  border: 2px dashed var(--border);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 14px;
}

.map-icon {
  font-size: 40px;
}

/* ── Reviews ────────────────────────── */

.reviews-section {
  margin-top: 32px;
}

.reviews-summary {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--bg-white);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  padding: 20px 24px;
  margin-bottom: 16px;
}

.reviews-score {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.score-num {
  font-size: 36px;
  font-weight: 800;
  color: var(--primary);
  line-height: 1;
}

.score-unit {
  font-size: 16px;
  color: var(--text-muted);
  font-weight: 600;
}

.reviews-stars {
  flex: 1;
}

.reviews-count {
  font-size: 14px;
  color: var(--text-muted);
}

.reviews-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.review-item {
  display: flex;
  gap: 14px;
  background: var(--bg-white);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  padding: 18px 20px;
}

.review-avatar {
  flex-shrink: 0;
}

.review-body {
  flex: 1;
}

.review-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.review-user {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.review-date {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: auto;
}

.review-text {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.review-reply {
  margin-top: 10px;
  background: var(--primary-light);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
}

.reply-badge {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 4px;
  background: var(--bg-white);
  border-radius: 4px;
  padding: 2px 8px;
}

.review-reply p {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 6px 0 0;
}

/* ── POI ───────────────────────────── */

.poi-summary {
  background: var(--primary-light);
  border-left: 4px solid var(--primary);
  padding: 12px 16px;
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.7;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.poi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.poi-group h4 {
  font-size: 14px;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.poi-group ul {
  list-style: none;
  padding: 0;
}

.poi-group li {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.8;
}

.poi-dist {
  color: var(--primary);
  font-weight: 500;
}

/* ── Similar ───────────────────────── */

.similar-section {
  margin-top: 32px;
}

.section-title {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title::before {
  content: '';
  width: 4px;
  height: 20px;
  background: var(--primary);
  border-radius: 2px;
}

.property-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

/* ── Bottom Bar ────────────────────── */

.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 200px;
  right: 0;
  background: var(--bg-white);
  border-top: 1px solid var(--border);
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 50;
  box-shadow: 0 -2px 12px rgba(0,0,0,0.04);
}
</style>
