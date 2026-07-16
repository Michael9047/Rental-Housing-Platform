<template>
  <div class="home-page">
    <!-- ===== Hero: AI Search ===== -->
    <section class="hero">
      <div class="hero-badge">🤖 AI 驱动</div>
      <h1 class="hero-title">AI 智能找公寓</h1>
      <p class="hero-subtitle">自然语言描述需求，一键匹配全球房源</p>

      <div class="hero-search-wrapper">
        <div class="hero-search-bar">
          <el-input
            v-model="query"
            size="large"
            placeholder="输入租房需求，例如：预算8000、市中心两居、近地铁、可短租、海外公寓"
            :prefix-icon="Search"
            class="hero-search-input"
            @keyup.enter="aiSearch"
          />
          <button
            class="voice-btn"
            :class="{ listening: listening }"
            @click="toggleVoice"
            title="语音输入"
          >
            <el-icon :size="20"><Microphone /></el-icon>
          </button>
          <el-button type="primary" @click="aiSearch" class="hero-search-btn">
            搜索
          </el-button>
        </div>

        <div class="hero-hints">
          <el-tag
            v-for="hint in searchHints"
            :key="hint"
            class="hint-tag"
            effect="plain"
            @click="quickSearch(hint)"
          >
            {{ hint }}
          </el-tag>
        </div>
      </div>
    </section>

    <!-- ===== Region Cards ===== -->
    <section class="region-section">
      <h2 class="section-title">按地区找房</h2>
      <div class="region-scroll-wrapper">
        <el-button
          class="scroll-arrow scroll-left"
          :icon="ArrowLeft"
          circle
          @click="scrollRegion('left')"
          :disabled="scrollAtStart"
        />
        <div class="region-scroll" ref="regionScrollRef" @scroll="onRegionScroll">
          <div
            v-for="region in regions"
            :key="region.value"
            class="region-card"
            @click="searchByRegion(region.value)"
          >
            <span class="region-icon">{{ region.icon }}</span>
            <span class="region-label">{{ region.label }}</span>
          </div>
          <div class="region-card region-more-card" @click="$router.push('/search')">
            <span class="region-icon" style="font-size:24px">＋</span>
            <span class="region-label">更多</span>
          </div>
        </div>
        <el-button
          class="scroll-arrow scroll-right"
          :icon="ArrowRight"
          circle
          @click="scrollRegion('right')"
          :disabled="scrollAtEnd"
        />
      </div>
    </section>

    <!-- ===== AI精选高匹配房源 ===== -->
    <section class="featured-section">
      <div class="section-header">
        <h2 class="section-title">AI 精选高匹配房源</h2>
        <el-button text type="primary" @click="$router.push('/search')">
          查看更多 <el-icon><ArrowRight /></el-icon>
        </el-button>
      </div>

      <div v-loading="loading" class="featured-list">
        <div v-if="!loading && properties.length === 0" class="empty-featured">
          <el-empty description="暂无房源数据" />
        </div>

        <div
          v-for="p in properties.slice(0, 6)"
          :key="p.id"
          class="featured-item"
        >
          <div class="featured-image" @click="goDetail(p.id)">
            <img
              v-if="getPrimaryImage(p)"
              :src="getPrimaryImage(p)"
              :alt="p.title"
              class="featured-img"
            />
            <div v-else class="featured-placeholder">
              <el-icon :size="36" color="#c0c4cc"><PictureFilled /></el-icon>
            </div>
            <span v-if="p.district" class="featured-district">{{ p.district }}</span>
          </div>

          <div class="featured-info">
            <div class="featured-header">
              <h3 class="featured-title" @click="goDetail(p.id)">{{ p.title }}</h3>
              <span v-if="p.similarity != null" class="featured-match">
                AI匹配 {{ (p.similarity * 100).toFixed(0) }}%
              </span>
            </div>

            <div class="featured-tags">
              <el-tag size="small">{{ p.bedrooms }}室{{ p.bathrooms }}卫</el-tag>
              <el-tag size="small" type="info">{{ typeLabels[p.property_type] }}</el-tag>
              <el-tag size="small" v-if="p.area_sqm">{{ p.area_sqm }}㎡</el-tag>
            </div>

            <p class="featured-address">{{ p.address }}</p>

            <div class="featured-footer">
              <div class="featured-price">
                <span class="price-num">¥{{ p.price_monthly }}</span>
                <span class="price-unit">/月</span>
              </div>
              <div class="featured-actions">
                <el-button size="small" text type="primary" @click="goDetail(p.id)">
                  查看详情
                </el-button>
                <el-button size="small" type="primary" @click.stop="openBookingDialog(p)">
                  预约看房
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="load-more" v-if="properties.length > 0">
        <span>下滑加载更多房源...</span>
      </div>
    </section>

    <!-- Booking Date Dialog -->
    <BookingDateDialog
      v-model="showBookingDialog"
      :property-id="selectedProperty?.id || 0"
      :property-title="selectedProperty?.title"
      :property-price="selectedProperty?.price_monthly"
      @confirm="handleBookingConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Search, ArrowRight, ArrowLeft, PictureFilled, Microphone } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { usePropertyStore } from '@/stores/property'
import { storeToRefs } from 'pinia'
import BookingDateDialog from '@/components/BookingDateDialog.vue'
import type { Property, PropertyType } from '@/types/property'

const router = useRouter()
const propertyStore = usePropertyStore()
const { properties, loading } = storeToRefs(propertyStore)

const query = ref('')
const listening = ref(false)

const searchHints = [
  '单间公寓', '一居室', '两居室', '海外留学生公寓',
  '地铁好房', '短租', '宠物友好',
]

const regions = [
  { value: 'china', label: '国内城区', icon: '🏙️' },
  { value: 'singapore', label: '新加坡', icon: '🇸🇬' },
  { value: 'hongkong', label: '香港公寓', icon: '🇭🇰' },
  { value: 'australia', label: '澳洲房源', icon: '🇦🇺' },
  { value: 'uk', label: '英国留学', icon: '🇬🇧' },
  { value: 'usa', label: '美国房源', icon: '🇺🇸' },
  { value: 'japan_korea', label: '日韩房源', icon: '🌸' },
  { value: 'europe', label: '欧洲公寓', icon: '🇪🇺' },
]

// Region scroll
const regionScrollRef = ref<HTMLElement | null>(null)
const scrollAtStart = ref(true)
const scrollAtEnd = ref(false)

function scrollRegion(dir: 'left' | 'right') {
  const el = regionScrollRef.value
  if (!el) return
  const amount = 300
  el.scrollBy({ left: dir === 'left' ? -amount : amount, behavior: 'smooth' })
  setTimeout(() => onRegionScroll(), 350)
}

function onRegionScroll() {
  const el = regionScrollRef.value
  if (!el) return
  scrollAtStart.value = el.scrollLeft <= 4
  scrollAtEnd.value = el.scrollLeft + el.clientWidth >= el.scrollWidth - 4
}

// Voice input
let recognition: any = null
function toggleVoice() {
  const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  if (!SpeechRecognition) {
    ElMessage.warning('您的浏览器不支持语音输入')
    return
  }
  if (listening.value) {
    recognition?.stop()
    listening.value = false
    return
  }
  recognition = new SpeechRecognition()
  recognition.lang = 'zh-CN'
  recognition.interimResults = false
  recognition.maxAlternatives = 1
  listening.value = true
  recognition.start()
  recognition.onresult = (event: any) => {
    const transcript = event.results[0][0].transcript
    query.value = transcript
    listening.value = false
    recognition = null
  }
  recognition.onerror = () => {
    listening.value = false
    recognition = null
    ElMessage.info('语音识别未成功，请手动输入')
  }
  recognition.onend = () => {
    listening.value = false
    recognition = null
  }
}

const typeLabels: Record<PropertyType, string> = {
  apartment: '公寓',
  house: '别墅',
  studio: '单间',
  shared: '合租',
}

// Booking dialog
const showBookingDialog = ref(false)
const selectedProperty = ref<Property | null>(null)

function openBookingDialog(p: Property) {
  selectedProperty.value = p
  showBookingDialog.value = true
}

function handleBookingConfirm(data: { propertyId: number; date: string; slot: string }) {
  showBookingDialog.value = false
  router.push({
    path: '/booking/confirm',
    query: {
      property_id: String(data.propertyId),
      date: data.date,
      slot: data.slot,
    },
  })
}

// Navigation
function aiSearch() {
  const q = query.value.trim()
  if (q) router.push({ name: 'search', query: { q } })
}

function quickSearch(hint: string) {
  router.push({ name: 'search', query: { q: hint } })
}

function searchByRegion(region: string) {
  if (region === 'more') {
    router.push({ name: 'search' })
  } else {
    router.push({ name: 'search', query: { country: region } })
  }
}

function goDetail(id: number) {
  router.push(`/property/${id}`)
}

function getPrimaryImage(p: Property): string | undefined {
  const images = p.images
  if (!images || images.length === 0) return undefined
  const primary = images.find((img) => img.is_primary) || images[0]
  return `/api/v1/uploads/${primary.filename}`
}

onMounted(() => {
  propertyStore.fetchList({ limit: 6 })
})
</script>

<style scoped>
/* ===== Hero ===== */
.hero {
  text-align: center;
  padding: 60px 20px 40px;
}

.hero-badge {
  display: inline-block;
  background: var(--primary-light);
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
  padding: 4px 16px;
  border-radius: 20px;
  margin-bottom: 16px;
}

.hero-title {
  font-size: 38px;
  font-weight: 800;
  color: var(--text-primary);
  margin-bottom: 8px;
  letter-spacing: 1px;
}

.hero-subtitle {
  font-size: 16px;
  color: var(--text-muted);
  margin-bottom: 32px;
}

.hero-search-wrapper {
  max-width: 750px;
  margin: 0 auto;
}

/* ── unified search bar: input + voice + button ── */
.hero-search-bar {
  display: flex;
  align-items: stretch;
  border-radius: 28px;
  border: 2px solid var(--primary);
  background: var(--bg-white);
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(255, 107, 53, 0.14);
  transition: box-shadow 0.25s;
}

.hero-search-bar:focus-within {
  box-shadow: 0 4px 24px rgba(255, 107, 53, 0.22);
}

/* ── input ── */
.hero-search-input {
  flex: 1;
}

.hero-search-input :deep(.el-input__wrapper) {
  border-radius: 0 !important;
  height: 52px;
  font-size: 15px;
  box-shadow: none !important;
  border: none !important;
  background: transparent !important;
}

/* ── voice button ── */
.voice-btn {
  flex-shrink: 0;
  width: 48px;
  background: transparent;
  border: none;
  color: #b0b3bb;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  padding: 0;
  outline: none;
}

.voice-btn:hover {
  color: var(--primary);
  background: transparent;
}

.voice-btn.listening {
  color: var(--primary);
  background: var(--primary-light);
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* ── search submit button ── */

.hero-search-btn {
  flex-shrink: 0;
  height: auto;
  font-size: 16px;
  font-weight: 600;
  padding: 0 28px !important;
  border-radius: 0 !important;
  background: var(--primary) !important;
  border-color: var(--primary) !important;
  color: #fff !important;
}

.hero-search-btn:hover {
  background: var(--primary-dark) !important;
  border-color: var(--primary-dark) !important;
}

.hero-hints {
  display: flex;
  gap: 10px;
  margin-top: 16px;
  justify-content: center;
  flex-wrap: wrap;
}

.hint-tag {
  cursor: pointer;
  transition: all 0.2s;
  border-radius: 20px !important;
  padding: 4px 16px;
  font-size: 13px;
}

.hint-tag:hover {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
  transform: translateY(-2px);
}

/* ===== Regions ===== */
.region-section {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px 0 20px;
}

.section-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 20px;
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

.region-scroll-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
}

.region-scroll {
  display: flex;
  gap: 16px;
  overflow-x: auto;
  scroll-behavior: smooth;
  padding: 4px 4px 8px;
  flex: 1;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.region-scroll::-webkit-scrollbar {
  display: none;
}

.scroll-arrow {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  z-index: 2;
  box-shadow: var(--shadow);
}

.region-card {
  flex-shrink: 0;
  width: 150px;
  height: 110px;
  background: var(--bg-white);
  border-radius: var(--radius);
  border: 2px solid transparent;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  transition: all 0.25s;
  box-sizing: border-box;
}

.region-card:hover {
  border-color: var(--primary);
  box-shadow: 0 4px 16px rgba(255, 107, 53, 0.12);
  transform: translateY(-3px);
}

.region-more-card {
  border-style: dashed;
  border-color: var(--border);
  color: var(--text-muted);
}

.region-more-card:hover {
  border-style: dashed;
  border-color: var(--primary);
  color: var(--primary);
}

.region-icon {
  font-size: 32px;
}

.region-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ===== Featured List ===== */
.featured-section {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px 0 40px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.featured-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.featured-item {
  display: flex;
  background: var(--bg-white);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  overflow: hidden;
  transition: all 0.25s;
  cursor: default;
}

.featured-item:hover {
  box-shadow: var(--shadow-lg);
  border-color: var(--primary);
}

.featured-image {
  width: 280px;
  min-height: 180px;
  flex-shrink: 0;
  background: #f5f7fa;
  position: relative;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.featured-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.featured-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.featured-district {
  position: absolute;
  bottom: 10px;
  left: 10px;
  background: rgba(0,0,0,0.55);
  color: #fff;
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 4px;
}

.featured-info {
  flex: 1;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
}

.featured-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.featured-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  cursor: pointer;
  transition: color 0.2s;
}

.featured-title:hover {
  color: var(--primary);
}

.featured-match {
  background: linear-gradient(135deg, #67c23a, #85ce61);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 20px;
  white-space: nowrap;
}

.featured-tags {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}

.featured-address {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.featured-footer {
  margin-top: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.featured-price {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.price-num {
  font-size: 24px;
  font-weight: 700;
  color: var(--danger);
}

.price-unit {
  font-size: 13px;
  color: var(--text-muted);
}

.featured-actions {
  display: flex;
  gap: 4px;
}

.load-more {
  text-align: center;
  padding: 24px;
  color: var(--text-muted);
  font-size: 14px;
}

.empty-featured {
  padding: 40px 0;
}
</style>
