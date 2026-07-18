<template>
  <div class="detail-page" v-loading="loading">
    <div v-if="property">
      <!-- Breadcrumb -->
      <div class="detail-topbar">
        <el-button text :icon="ArrowLeft" @click="$router.back()">返回</el-button>
        <div class="topbar-actions">
          <el-button text :icon="ShoppingCart" :type="inCart ? 'success' : 'default'" @click="handleAddToCart">
            {{ inCart ? '已加入候选' : '加入候选' }}
          </el-button>
          <el-button text :icon="Share" @click="shareProperty">分享</el-button>
        </div>
      </div>

      <!-- Image Gallery -->
      <div v-if="sortedImages.length > 0" class="gallery">
        <el-carousel :interval="4000" height="420px" trigger="click" class="gallery-carousel">
          <el-carousel-item v-for="(img, idx) in sortedImages" :key="img.id">
            <el-image
              :src="getImageUrl(img.filename)"
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
            <img :src="getImageUrl(img.filename)" />
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
              <span class="spec-value">{{ roomTypeSummary }}</span>
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

      <!-- Room Types 房型列表 -->
      <el-card v-if="roomTypes.length > 0" shadow="never" class="info-card">
        <template #header>
          <span class="card-header-text">🏠 可选房型（{{ roomTypes.length }} 种）</span>
        </template>
        <div class="room-type-list">
          <div v-for="rt in roomTypes" :key="rt.id" class="room-type-item">
            <!-- 第一行：左侧图片 + 右侧房型概要 -->
            <div class="rt-row1">
              <div class="rt-thumb">
                <img
                  v-if="propertyImageUrl"
                  :src="propertyImageUrl"
                  :alt="rt.name"
                  class="rt-thumb-img"
                />
                <div v-else class="rt-thumb-placeholder">
                  <span>🏠</span>
                </div>
              </div>
              <div class="rt-summary">
                <span class="rt-name">{{ roomTypeLabels[rt.room_type] || rt.name }}</span>
                <div class="rt-meta">
                  <span class="rt-meta-item">{{ rt.bedrooms }} 卧室</span>
                  <span class="rt-meta-divider">·</span>
                  <span class="rt-meta-item">{{ rt.bathrooms }} 卫</span>
                  <span class="rt-meta-divider">·</span>
                  <span class="rt-meta-item">{{ rt.area_sqm }}㎡</span>
                  <el-tag
                    v-if="rt.available_count <= 2"
                    type="warning"
                    size="small"
                    effect="plain"
                    class="rt-stock-warn"
                  >
                    仅剩 {{ rt.available_count }} 间
                  </el-tag>
                </div>
              </div>
            </div>

            <!-- 第二行：设施标签 -->
            <div class="rt-row2">
              <div class="rt-amenity-tags">
                <span
                  v-for="tag in getRoomAmenities(rt)"
                  :key="tag"
                  class="rt-amenity-tag"
                >{{ tag }}</span>
                <span v-if="getRoomAmenities(rt).length === 0" class="rt-no-amenities">
                  暂无设施信息
                </span>
              </div>
            </div>

            <!-- 第三行：价格 + 预订 -->
            <div class="rt-row3">
              <div class="rt-price">
                <span class="rt-price-value">¥{{ rt.price_monthly.toLocaleString() }}</span>
                <span class="rt-price-unit">/月</span>
              </div>
              <el-button type="primary" size="default" round @click="showBookingDialog = true; selectedRoomTypeId = rt.id">
                预订
              </el-button>
            </div>
          </div>
        </div>
      </el-card>

      <!-- Description -->
      <el-card v-if="property.description" shadow="never" class="info-card">
        <template #header><span class="card-header-text">📝 房源描述</span></template>
        <p class="desc-text">{{ property.description }}</p>
      </el-card>

      <!-- Facilities -->
      <el-card shadow="never" class="info-card">
        <template #header><span class="card-header-text">🏪 配套设施</span></template>
        <div v-if="allFacilities.length > 0" class="facility-grid">
          <el-tag
            v-for="f in displayedFacilities"
            :key="f"
            type="info"
            effect="plain"
            size="large"
            round
            class="facility-tag-item"
          >{{ f }}</el-tag>
        </div>
        <span v-else class="no-data">暂无配套设施信息</span>
        <div v-if="allFacilities.length > 10" class="facility-toggle">
          <el-button text type="primary" @click="showAllFacilities = true">
            查看更多 ({{ allFacilities.length - 10 }})
            <el-icon><ArrowDown /></el-icon>
          </el-button>
        </div>
      </el-card>

      <!-- 配套设施全部弹窗 -->
      <el-dialog
        v-model="showAllFacilities"
        title="全部配套设施"
        width="560px"
        :close-on-click-modal="true"
        destroy-on-close
        class="facility-dialog"
      >
        <div class="facility-dialog-grid">
          <el-tag
            v-for="f in allFacilities"
            :key="f"
            type="info"
            effect="plain"
            size="large"
            round
            class="facility-tag-item"
          >{{ f }}</el-tag>
        </div>
      </el-dialog>

      <!-- AI POI Analysis -->
      <el-card v-if="poiData" shadow="never" class="info-card">
        <template #header>
          <div class="card-header-row">
            <span class="card-header-text">📍 周边分析</span>
            <el-button text size="small" type="primary" :loading="poiLoading" @click="refreshPOI">
              刷新数据
            </el-button>
          </div>
        </template>
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

      <!-- POI 加载失败 -->
      <el-card v-else-if="poiFailed" shadow="never" class="info-card poi-error-card">
        <div class="poi-error">
          <el-icon :size="24" color="#f56c6c"><WarningFilled /></el-icon>
          <span>周边数据暂不可用</span>
          <el-button size="small" type="primary" :loading="poiLoading" @click="refreshPOI">
            重试
          </el-button>
        </div>
      </el-card>

      <!-- 🚌 通勤时间（从学校到此房源） -->
      <el-card v-if="schoolInfo" shadow="never" class="info-card">
        <template #header>
          <span class="card-header-text">🚌 通勤时间 — 从 {{ schoolInfo.name }} 出发</span>
        </template>
        <div v-if="commuteInfo" class="commute-grid">
          <div class="commute-item">
            <span class="commute-icon">🚶</span>
            <span class="commute-label">步行</span>
            <span class="commute-value">{{ commuteInfo.walk_min }}<small> 分钟</small></span>
          </div>
          <div class="commute-item">
            <span class="commute-icon">🚲</span>
            <span class="commute-label">骑行</span>
            <span class="commute-value">{{ commuteInfo.bike_min }}<small> 分钟</small></span>
          </div>
          <div class="commute-item">
            <span class="commute-icon">🚗</span>
            <span class="commute-label">驾车</span>
            <span class="commute-value">{{ commuteInfo.drive_min }}<small> 分钟</small></span>
          </div>
          <div class="commute-item">
            <span class="commute-icon">🚌</span>
            <span class="commute-label">公交/地铁</span>
            <span class="commute-value">{{ commuteInfo.transit_min }}<small> 分钟</small></span>
          </div>
        </div>
        <div v-if="commuteInfo" class="commute-dist">📍 直线距离约 <strong>{{ commuteInfo.dist_km }}km</strong></div>
        <div v-else v-loading="commuteLoading" style="text-align:center;padding:20px;color:#909399;">
          正在计算通勤时间…
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
          <div v-for="(r, i) in displayedReviews" :key="i" class="review-item">
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
        <div v-if="sortedReviews.length > 3" class="reviews-toggle">
          <el-button text type="primary" @click="showAllReviews = !showAllReviews">
            {{ showAllReviews ? '收起' : `查看更多评价 (${sortedReviews.length - 3})` }}
            <el-icon><component :is="showAllReviews ? 'ArrowUp' : 'ArrowDown'" /></el-icon>
          </el-button>
        </div>
      </section>

      <!-- 🗺️ 周边地图 -->
      <PropertyMapCard
        v-if="Number(property.latitude) && Number(property.longitude)"
        :property-id="property.id"
        :property-lat="Number(property.latitude)"
        :property-lng="Number(property.longitude)"
        :property-title="property.title"
        :property-address="property.address"
        :country="schoolInfo?.country ?? property.country"
      />

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

      <!-- 最近浏览过 -->
      <section v-if="recentlyViewedProperties.length > 0" class="recent-section">
        <h2 class="section-title">🕐 最近浏览过</h2>
        <div class="property-grid">
          <PropertyCard
            v-for="p in recentlyViewedProperties"
            :key="p.id"
            :property="p"
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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ShoppingCart, Share, ArrowUp, ArrowDown, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePropertyStore } from '@/stores/property'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'
import api from '@/services/api'
import { propertyService, type PropertyPOI } from '@/services/property'
import { commuteService } from '@/services/commute'
import { storeToRefs } from 'pinia'
import PropertyCard from '@/components/PropertyCard.vue'
import type { CommuteInfo } from '@/components/PropertyCard.vue'
import { getImageUrl } from '@/utils/image'
import PropertyMapCard from '@/components/PropertyMapCard.vue'
import BookingDateDialog from '@/components/BookingDateDialog.vue'
import type { Property, PropertyType, PropertyStatus, RoomType, RoomTypeEnum } from '@/types/property'
import { roomTypeLabels } from '@/types/property'

const route = useRoute()
const router = useRouter()
const propertyStore = usePropertyStore()
const authStore = useAuthStore()
const cartStore = useCartStore()
const { currentProperty: property, loading } = storeToRefs(propertyStore)

const inCart = computed(() => cartStore.has(property.value?.id ?? 0))

const currentSlide = ref(0)

// ── 学校通勤上下文（从 Search 页学校模式跳转时携带）──
const schoolInfo = computed(() => {
  const q = route.query
  if (!q.school_lat || !q.school_lng) return null
  return {
    lat: Number(q.school_lat),
    lng: Number(q.school_lng),
    name: (q.school_name as string) || '学校',
    country: (q.school_country as string) || undefined,
    city: (q.school_city as string) || undefined,
  }
})

// Facilities — 合并基础配套 + 海外配套，去重
const allFacilities = computed(() => {
  if (!property.value) return []
  const p = property.value
  const f = ['电梯', '空调', '洗衣机', '冰箱', 'WiFi', '暖气']
  if (p.property_type === 'house') f.push('车位', '全屋家电')
  if (p.property_type === 'studio') f.push('独立卫浴', '储物间')
  if (p.area_sqm && p.area_sqm > 60) f.push('阳台')
  if (p.description && /宠物|猫|狗/.test(p.description)) f.push('可养宠物')

  // 海外配套
  const d = p.district || ''
  const isOverseas = !/苏州|北京|上海|广州|深圳|杭州|南京|成都|武汉|重庆/.test(d)
  if (isOverseas) f.push('健身房', '自习室', '签证咨询', '24小时前台', '校车接驳')

  return Array.from(new Set(f))
})

const showAllFacilities = ref(false)
const displayedFacilities = computed(() => allFacilities.value.slice(0, 10))

// Reviews (static mock — backend doesn't have reviews yet)
const reviews = [
  { user: '李明', avatar: '李', avatarColor: '#FF6B35', rating: 5, date: '2026-06-20', text: '房间很干净，采光好，房东人很nice。地铁就在楼下非常方便！', reply: '感谢李先生的认可，欢迎随时联系。' },
  { user: 'Emily', avatar: 'E', avatarColor: '#67c23a', rating: 4.5, date: '2026-06-15', text: 'Great location and friendly landlord. The apartment has everything I need for my study abroad year.', reply: 'Thanks Emily! Happy to help with your stay.' },
  { user: '王芳', avatar: '王', avatarColor: '#409eff', rating: 4, date: '2026-06-08', text: '配套齐全，周边买菜方便。唯一建议是洗衣机可以换个新的。', reply: '' },
  { user: '张伟', avatar: '张', avatarColor: '#e6a23c', rating: 5, date: '2026-05-28', text: '第三次租了，每次体验都很好。平台服务也很到位，推荐！', reply: '感谢老客户的支持！' },
]

const showAllReviews = ref(false)

// 按评分降序排列
const sortedReviews = computed(() => [...reviews].sort((a, b) => b.rating - a.rating))

// 默认展示评分最高的3条
const displayedReviews = computed(() =>
  showAllReviews.value ? sortedReviews.value : sortedReviews.value.slice(0, 3)
)

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
const poiFailed = ref(false)

// Commute
const commuteInfo = ref<CommuteInfo | null>(null)
const commuteLoading = ref(false)

// Similar properties
const similarProperties = ref<Property[]>([])

// Room types
const roomTypes = ref<RoomType[]>([])
const selectedRoomTypeId = ref<number | null>(null)

// Booking dialog
const showBookingDialog = ref(false)

const loadingProperty = ref(false)

const statusLabels: Record<PropertyStatus, string> = {
  available: '可租', pending_review: '审核中', rented: '已租', maintenance: '维护中', offline: '已下架',
}
const typeLabels: Record<PropertyType, string> = {
  apartment: '公寓', house: '别墅', studio: '单间', shared: '合租',
}

const statusTagType = computed(() => {
  if (!property.value) return 'info'
  const map: Record<PropertyStatus, string> = {
    available: 'success', pending_review: 'warning', rented: 'warning', maintenance: 'info', offline: 'danger',
  }
  return map[property.value.status]
})

const statusLabel = computed(() => property.value ? statusLabels[property.value.status] : '')
const typeLabel = computed(() => property.value ? typeLabels[property.value.property_type] : '')

// 从房型列表汇总"户型"展示（如 "Studio~三室"）
const roomTypeSummary = computed(() => {
  if (!property.value) return ''
  if (roomTypes.value.length === 0) {
    return `${property.value.bedrooms}室${property.value.bathrooms}卫`
  }
  const types = [...new Set(roomTypes.value.map(rt => rt.room_type))]
  const labels = types.map(t => roomTypeLabels[t] || t)
  if (labels.length === 1) return labels[0]
  if (labels.length <= 3) return labels.join(' / ')
  return `${labels[0]} ~ ${labels[labels.length - 1]}`
})

// 房型卡片用：属性图作为缩略图
const propertyImageUrl = computed(() => {
  const imgs = property.value?.images
  if (!imgs || imgs.length === 0) return null
  const primary = imgs.find(img => img.is_primary) || imgs[0]
  return primary.filename.startsWith('http')
    ? primary.filename
    : `/api/v1/uploads/${primary.filename}`
})

// 房型设施标签（由公寓管理方填写，直接展示）
function getRoomAmenities(rt: RoomType): string[] {
  return rt.amenities || []
}

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
  sortedImages.value.map((img) => getImageUrl(img.filename))
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

async function handleAddToCart() {
  if (!property.value) return
  // 未登录 → 弹出确认框，引导登录
  if (!authStore.isLoggedIn) {
    try {
      await ElMessageBox.confirm(
        '加入候选清单需要登录账号，是否前往登录？',
        '提示',
        { confirmButtonText: '去登录', cancelButtonText: '取消', type: 'info' }
      )
      router.push({ name: 'login', query: { redirect: route.fullPath } })
    } catch {
      // 用户取消
    }
    return
  }
  try {
    if (inCart.value) {
      await cartStore.remove(property.value.id)
      ElMessage.success('已移出候选清单')
    } else {
      await cartStore.add(property.value.id)
      ElMessage.success('已加入候选清单')
    }
  } catch {
    ElMessage.error('操作失败，请稍后重试')
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
  try {
    await propertyStore.fetchById(id)
    if (property.value) {
      saveRecentId(property.value.id)
      loadPOI(property.value.id)
      loadSimilar()
      loadRoomTypes(property.value.id)
      loadRecentlyViewed()
      fetchCommute()
    }
  } catch { /* handled */ }
  finally { loadingProperty.value = false }
}

async function loadPOI(pid: number) {
  poiLoading.value = true
  poiFailed.value = false
  try {
    const d = await propertyService.getPropertyPOI(pid)
    poiData.value = d
  } catch {
    poiData.value = null
    poiFailed.value = true
  } finally {
    poiLoading.value = false
  }
}

async function refreshPOI() {
  if (!property.value) return
  poiLoading.value = true
  poiFailed.value = false
  try {
    // 调用 generate 端点强制刷新
    const resp = await api.post(`/pois/${property.value.id}/generate`)
    poiData.value = resp.data
  } catch {
    // generate 端点不可用或失败，重新走 get 端点
    await loadPOI(property.value.id)
  } finally {
    poiLoading.value = false
  }
}

/** 学校模式下计算通勤时间 */
async function fetchCommute() {
  const p = property.value
  const school = schoolInfo.value
  if (!p || !school) {
    commuteInfo.value = null
    return
  }
  if (!p.latitude || !p.longitude) return

  commuteLoading.value = true
  try {
    const resp = await commuteService.calculate({
      origin_lat: school.lat,
      origin_lng: school.lng,
      destinations: [{ id: p.id, lat: Number(p.latitude), lng: Number(p.longitude) }],
      country: school.country,
      city: school.city,
    })
    if (resp.results && resp.results.length > 0) {
      const r = resp.results[0]
      commuteInfo.value = {
        dist_km: r.dist_km,
        walk_min: r.walk_min,
        bike_min: r.bike_min,
        drive_min: r.drive_min,
        transit_min: r.transit_min,
      }
    }
  } catch {
    commuteInfo.value = null
  } finally {
    commuteLoading.value = false
  }
}

async function loadSimilar() {
  try {
    const res = await propertyService.list({ page_size: 4 })
    similarProperties.value = res.items.filter(p => p.id !== property.value?.id).slice(0, 3)
  } catch { similarProperties.value = [] }
}

async function loadRoomTypes(pid: number) {
  try {
    roomTypes.value = await propertyService.listRoomTypes(pid)
  } catch {
    roomTypes.value = []
  }
}

// ── 最近浏览过的房源 ──
const RECENT_VIEWED_KEY = 'recently_viewed_properties'
const MAX_RECENT = 4
const recentlyViewedProperties = ref<Property[]>([])

function getRecentIds(): number[] {
  try {
    const raw = localStorage.getItem(RECENT_VIEWED_KEY)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

function saveRecentId(id: number) {
  const ids = getRecentIds().filter(i => i !== id)
  ids.unshift(id)
  localStorage.setItem(RECENT_VIEWED_KEY, JSON.stringify(ids.slice(0, MAX_RECENT)))
}

async function loadRecentlyViewed() {
  const ids = getRecentIds().filter(i => i !== property.value?.id)
  if (ids.length === 0) { recentlyViewedProperties.value = []; return }
  const results: Property[] = []
  for (const id of ids.slice(0, MAX_RECENT)) {
    try {
      const p = await propertyService.getById(id)
      results.push(p)
    } catch { /* 房源可能已下架 */ }
  }
  recentlyViewedProperties.value = results
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

.facility-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
}

.facility-tag-item {
  justify-content: center;
  text-align: center;
  height: 36px;
  font-size: 13px;
}

.facility-toggle {
  text-align: center;
  margin-top: 12px;
}

.facility-toggle .el-button {
  font-size: 14px;
  font-weight: 500;
}

/* 配套设施弹窗 */
.facility-dialog-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 8px 0;
}

.no-data {
  color: var(--text-muted);
  font-size: 14px;
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

/* ── Reviews Toggle ── */
.reviews-toggle {
  text-align: center;
  margin-top: 12px;
}

.reviews-toggle .el-button {
  font-size: 14px;
  font-weight: 500;
}

/* ── Card Header Row ───────────────── */

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

/* ── Commute Grid ──────────────────── */

.commute-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}

.commute-item {
  text-align: center;
  padding: 12px 8px;
  background: #f5f7fa;
  border-radius: 8px;
}

.commute-icon {
  font-size: 24px;
  display: block;
  margin-bottom: 4px;
}

.commute-label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.commute-value {
  font-size: 22px;
  font-weight: 700;
  color: #303133;
}

.commute-value small {
  font-size: 12px;
  font-weight: 400;
  color: #909399;
}

.commute-dist {
  text-align: center;
  font-size: 13px;
  color: #909399;
  padding: 8px;
  background: #f0f9eb;
  border-radius: 6px;
}

/* ── POI ───────────────────────────── */

.poi-error-card {
  --el-card-border-color: #fde2e2;
}

.poi-error {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  color: #f56c6c;
  font-size: 14px;
}

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

/* ── Recently Viewed ────────────────── */

.recent-section {
  margin-top: 32px;
}

/* ── Room Type List ─────────────────── */

.room-type-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.room-type-item {
  padding: 20px 0;
  border-bottom: 1px solid var(--border-light);
}

.room-type-item:first-child {
  padding-top: 0;
}

.room-type-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

/* ── 第一行：缩略图 + 房型概要 ────────── */

.rt-row1 {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.rt-thumb {
  flex: 0 0 200px;
  width: 200px;
  height: 130px;
  border-radius: 8px;
  overflow: hidden;
  background: #f5f7fa;
}

.rt-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.rt-thumb-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 36px;
  color: #c0c4cc;
}

.rt-summary {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rt-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.rt-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.rt-meta-item {
  font-size: 14px;
  color: var(--text-secondary);
}

.rt-meta-item.shared {
  color: var(--text-muted);
}

.rt-meta-divider {
  font-size: 13px;
  color: var(--border);
}

.rt-stock-warn {
  margin-left: 4px;
}

/* ── 第二行：设施标签 ────────────────── */

.rt-row2 {
  margin-top: 14px;
  padding-left: 216px; /* 对齐右侧摘要区域 */
}

.rt-amenity-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.rt-amenity-tag {
  display: inline-block;
  font-size: 13px;
  padding: 4px 14px;
  border-radius: 6px;
  background: #f5f7fa;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  white-space: nowrap;
  line-height: 1.5;
}

.rt-no-amenities {
  font-size: 13px;
  color: var(--text-muted);
}

[data-theme="dark"] .rt-amenity-tag {
  background: #262727;
  border-color: #3a3a3c;
  color: #c8c8cc;
}

/* ── 第三行：价格 + 预订 ──────────────── */

.rt-row3 {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed var(--border-light);
}

.rt-price {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.rt-price-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--danger);
  white-space: nowrap;
}

.rt-price-unit {
  font-size: 13px;
  color: var(--text-muted);
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



