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
        <el-row :gutter="16" :class="{ 'spec-row-uk': showStreetScore }">
          <el-col :span="showStreetScore ? 4 : 6">
            <div class="spec-item">
              <span class="spec-icon">📐</span>
              <span class="spec-label">户型</span>
              <span class="spec-value">{{ property.bedrooms }}室{{ property.bathrooms }}卫</span>
            </div>
          </el-col>
          <el-col :span="showStreetScore ? 4 : 6">
            <div class="spec-item">
              <span class="spec-icon">📏</span>
              <span class="spec-label">面积</span>
              <span class="spec-value">{{ property.area_sqm ? property.area_sqm + '㎡' : '暂无' }}</span>
            </div>
          </el-col>
          <el-col :span="showStreetScore ? 4 : 6">
            <div class="spec-item">
              <span class="spec-icon">🏢</span>
              <span class="spec-label">类型</span>
              <span class="spec-value">{{ typeLabel }}</span>
            </div>
          </el-col>
          <el-col :span="showStreetScore ? 4 : 6">
            <div class="spec-item">
              <span class="spec-icon">✅</span>
              <span class="spec-label">状态</span>
              <span class="spec-value">{{ statusLabel }}</span>
            </div>
          </el-col>
          <el-col v-if="showStreetScore" :span="4">
            <div
              class="spec-item spec-item-clickable"
              :class="{ loading: streetScoreLoading }"
              @click="openStreetScoreDialog"
            >
              <span class="spec-icon">🏘️</span>
              <span class="spec-label">
                街区评分
                <el-tooltip
                  content="基于 scoremystreet.com 的英国街区评分"
                  placement="top"
                >
                  <span class="spec-info-icon">ⓘ</span>
                </el-tooltip>
              </span>
              <span v-if="streetScoreLoading" class="spec-value spec-loading">
                加载中…
              </span>
              <span
                v-else-if="streetScore?.overall_score != null"
                class="spec-value street-score"
                :class="streetScoreClass"
              >
                {{ streetScore.overall_score }}/100
              </span>
              <span v-else class="spec-value street-unknown">
                查看评分
              </span>
            </div>
          </el-col>
          <el-col v-if="showCrystalRoof" :span="4">
            <div
              class="spec-item spec-item-clickable"
              :class="{ loading: crystalRoofLoading }"
              @click="openCrystalRoofDialog"
            >
              <span class="spec-icon">⭐</span>
              <span class="spec-label">
                CrystalRoof
                <el-tooltip
                  content="基于 crystalroof.co.uk 的英国地址评分"
                  placement="top"
                >
                  <span class="spec-info-icon">ⓘ</span>
                </el-tooltip>
              </span>
              <span v-if="crystalRoofLoading" class="spec-value spec-loading">
                加载中…
              </span>
              <span
                v-else-if="crystalRoofScore?.overall_score != null"
                class="spec-value crystalroof-score"
                :class="crystalRoofScoreClass"
              >
                {{ crystalRoofScore.overall_score }}/100
              </span>
              <span v-else class="spec-value crystalroof-unknown">
                查看报告
              </span>
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
      <el-button type="primary" size="large" round @click="goToBookingFlow">
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

    <!-- ScoreMyStreet 街区评分详情弹窗 -->
    <el-dialog
      v-model="showStreetScoreDialog"
      title="街区评分详情"
      width="640px"
      :close-on-click-modal="false"
    >
      <div v-if="streetScore" class="street-dialog">
        <div class="street-header">
          <div class="street-score-big" :class="streetScoreClass">
            <span class="score-num">{{ streetScore.overall_score ?? '—' }}</span>
            <span class="score-suffix">/100</span>
          </div>
          <div class="street-meta">
            <div v-if="streetScore.area_name" class="meta-row">
              <span class="meta-label">📍 区域</span>
              <span class="meta-value">{{ streetScore.area_name }}</span>
            </div>
            <div v-if="streetScore.postcode" class="meta-row">
              <span class="meta-label">📮 邮编</span>
              <span class="meta-value">{{ streetScore.postcode }}</span>
            </div>
            <div v-if="streetScore.postcode_district" class="meta-row">
              <span class="meta-label">🗺️ 邮编区</span>
              <span class="meta-value">{{ streetScore.postcode_district }}</span>
            </div>
            <div v-if="streetScore.date_processed" class="meta-row">
              <span class="meta-label">📅 数据日期</span>
              <span class="meta-value">{{ streetScore.date_processed }}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">🔗 数据源</span>
              <span class="meta-value">{{ streetScore.source }}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">📊 数据状态</span>
              <span class="meta-value">
                <el-tag v-if="streetScore.fetched" type="success" size="small">
                  已获取
                </el-tag>
                <el-tag v-else type="warning" size="small">
                  仅提供链接
                </el-tag>
              </span>
            </div>
          </div>
        </div>

        <el-divider />

        <div class="street-subscores">
          <h4>维度评分</h4>
          <div class="subscore-grid">
            <div class="subscore-item">
              <div class="subscore-label">
                🔒 安全
                <span v-if="streetScore.safety_score != null" class="subscore-badge">
                  {{ streetScore.safety_score }}/5
                </span>
              </div>
              <el-progress
                :percentage="safetyScorePercent"
                :color="subscoreColor(safetyScorePercent)"
                :stroke-width="10"
                :show-text="safetyScorePercent > 0"
              />
              <div class="subscore-value">
                <template v-if="streetScore.crime_count != null">
                  近6月 {{ streetScore.crime_count }} 起案件
                </template>
                <template v-else-if="streetScore.safety_score != null">
                  安全评分 {{ streetScore.safety_score }}/5
                </template>
                <template v-else>暂无数据</template>
                <el-tag v-if="streetScore.crime_rate" :type="crimeRateTagType" size="small" style="margin-left: 8px">
                  {{ crimeRateLabel }}
                </el-tag>
              </div>
              <div v-if="streetScore.crime_types" class="crime-types">
                <span v-for="(percent, type) in streetScore.crime_types" :key="type" class="crime-type-tag">
                  {{ type }}: {{ percent }}%
                </span>
              </div>
            </div>

            <div class="subscore-item">
              <div class="subscore-label">
                🏫 学校
                <span v-if="streetScore.schools_score != null" class="subscore-badge">
                  {{ streetScore.schools_score }}/100
                </span>
              </div>
              <el-progress
                :percentage="streetScore.schools_score ?? 0"
                :color="subscoreColor(streetScore.schools_score ?? 0)"
                :stroke-width="10"
                :show-text="(streetScore.schools_score ?? 0) > 0"
              />
              <div class="subscore-value">
                <template v-if="streetScore.schools_count != null">
                  {{ streetScore.schools_count }} 所学校
                </template>
                <template v-else-if="streetScore.schools_score != null">
                  评分 {{ streetScore.schools_score }}/100
                </template>
                <template v-else>暂无数据</template>
                <span v-if="streetScore.schools_info" class="subscore-detail">{{ streetScore.schools_info }}</span>
              </div>
            </div>

            <div class="subscore-item">
              <div class="subscore-label">
                🏪 设施
                <span v-if="streetScore.amenities_score != null" class="subscore-badge">
                  {{ streetScore.amenities_score }}/100
                </span>
              </div>
              <el-progress
                :percentage="streetScore.amenities_score ?? 0"
                :color="subscoreColor(streetScore.amenities_score ?? 0)"
                :stroke-width="10"
                :show-text="(streetScore.amenities_score ?? 0) > 0"
              />
              <div class="subscore-value">
                <template v-if="streetScore.supermarkets_count != null || streetScore.parks_count != null || streetScore.gyms_count != null || streetScore.ev_charging_count != null">
                  <span v-if="streetScore.supermarkets_count">🛒 {{ streetScore.supermarkets_count }}超市</span>
                  <span v-if="streetScore.parks_count"> 🌳 {{ streetScore.parks_count }}公园</span>
                  <span v-if="streetScore.gyms_count"> 💪 {{ streetScore.gyms_count }}健身房</span>
                  <span v-if="streetScore.ev_charging_count"> ⚡ {{ streetScore.ev_charging_count }}充电点</span>
                </template>
                <template v-else-if="streetScore.amenities_score != null">
                  评分 {{ streetScore.amenities_score }}/100
                </template>
                <template v-else>暂无数据</template>
              </div>
            </div>

            <div class="subscore-item">
              <div class="subscore-label">
                🚇 交通
                <span v-if="streetScore.transport_score != null" class="subscore-badge">
                  {{ streetScore.transport_score }}/100
                </span>
              </div>
              <el-progress
                :percentage="streetScore.transport_score ?? 0"
                :color="subscoreColor(streetScore.transport_score ?? 0)"
                :stroke-width="10"
                :show-text="(streetScore.transport_score ?? 0) > 0"
              />
              <div class="subscore-value">
                <template v-if="streetScore.nearest_station">
                  最近: {{ streetScore.nearest_station }}
                  <span v-if="streetScore.nearest_station_distance">({{ streetScore.nearest_station_distance }}英里)</span>
                  <span v-if="streetScore.stations_count">，共{{ streetScore.stations_count }}个车站</span>
                </template>
                <template v-else-if="streetScore.transport_score != null">
                  评分 {{ streetScore.transport_score }}/100
                </template>
                <template v-else>暂无数据</template>
              </div>
            </div>

            <div class="subscore-item">
              <div class="subscore-label">
                🌐 网络
                <span v-if="streetScore.connectivity_score != null" class="subscore-badge">
                  {{ streetScore.connectivity_score }}/100
                </span>
              </div>
              <el-progress
                :percentage="streetScore.connectivity_score ?? 0"
                :color="subscoreColor(streetScore.connectivity_score ?? 0)"
                :stroke-width="10"
                :show-text="(streetScore.connectivity_score ?? 0) > 0"
              />
              <div class="subscore-value">
                <template v-if="streetScore.full_fibre_coverage != null || streetScore.ultrafast_coverage != null || streetScore.superfast_coverage != null">
                  <span v-if="streetScore.full_fibre_coverage">全光纤 {{ streetScore.full_fibre_coverage }}</span>
                  <span v-if="streetScore.ultrafast_coverage">，超高速 {{ streetScore.ultrafast_coverage }}</span>
                  <span v-if="streetScore.superfast_coverage">，高速 {{ streetScore.superfast_coverage }}</span>
                </template>
                <template v-else-if="streetScore.connectivity_score != null">
                  评分 {{ streetScore.connectivity_score }}/100
                </template>
                <template v-else>暂无数据</template>
              </div>
            </div>
          </div>
        </div>

        <div class="street-actions">
          <el-link
            type="primary"
            :href="streetScore.report_url || streetScore.search_url"
            target="_blank"
            class="street-link-btn"
          >
            前往 ScoreMyStreet 查看完整报告 ↗
          </el-link>
          <el-button size="large" @click="showStreetScoreDialog = false">
            关闭
          </el-button>
        </div>
      </div>
      <el-empty v-else description="暂无评分数据" />
    </el-dialog>

    <!-- CrystalRoof 评分详情弹窗 -->
    <el-dialog
      v-model="showCrystalRoofDialog"
      title="CrystalRoof 评分详情"
      width="640px"
      :close-on-click-modal="false"
    >
      <div v-if="crystalRoofScore" class="crystalroof-dialog">
        <div class="crystalroof-header">
          <div class="crystalroof-score-big" :class="crystalRoofScoreClass">
            <span class="score-num">{{ crystalRoofScore.overall_score ?? '—' }}</span>
            <span class="score-suffix">/100</span>
          </div>
          <div class="crystalroof-meta">
            <div class="meta-row">
              <span class="meta-label">📍 地址</span>
              <span class="meta-value">{{ crystalRoofScore.address }}</span>
            </div>
            <div v-if="crystalRoofScore.postcode" class="meta-row">
              <span class="meta-label">📮 邮编</span>
              <span class="meta-value">{{ crystalRoofScore.postcode }}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">🔗 数据源</span>
              <span class="meta-value">{{ crystalRoofScore.source }}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">📊 抓取状态</span>
              <span class="meta-value">
                <el-tag v-if="crystalRoofScore.fetched" type="success" size="small">
                  成功解析
                </el-tag>
                <el-tag v-else type="warning" size="small">
                  仅提供链接
                </el-tag>
              </span>
            </div>
          </div>
        </div>

        <el-divider />

        <div v-if="crystalRoofScore.subscores && Object.keys(crystalRoofScore.subscores).length > 0" class="crystalroof-subscores">
          <h4>子项评分</h4>
          <div class="subscore-grid">
            <div
              v-for="(value, key) in crystalRoofScore.subscores"
              :key="key"
              class="subscore-item"
            >
              <div class="subscore-label">{{ subscoreLabel(key) }}</div>
              <el-progress
                :percentage="value"
                :color="subscoreColor(value)"
                :stroke-width="10"
              />
              <div class="subscore-value">{{ value }}/100</div>
            </div>
          </div>
        </div>

        <el-alert
          v-else-if="!crystalRoofScore.fetched"
          type="info"
          :closable="false"
          show-icon
          class="crystalroof-tip"
        >
          <template #title>
            未能在服务器端自动解析该地址的详细评分（受 Cloudflare 反爬保护限制）。
          </template>
          <p>
            点击下方按钮直接跳转到 CrystalRoof 官网，查看该地址的完整评分报告
            （包括犯罪率、学校、交通、生活设施等多维度数据）。
          </p>
        </el-alert>

        <div class="crystalroof-actions">
          <el-link
            type="primary"
            :href="crystalRoofRedirectUrl"
            target="_blank"
            class="crystalroof-link-btn"
          >
            前往 CrystalRoof 查看完整报告 ↗
          </el-link>
          <el-button size="large" @click="showCrystalRoofDialog = false">
            关闭
          </el-button>
        </div>
      </div>
      <el-empty v-else description="暂无评分数据" />
    </el-dialog>
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
import { crystalRoofService, type CrystalRoofScore } from '@/services/crystalroof'
import { scoreMyStreetService, type ScoreMyStreetScore } from '@/services/scoremystreet'
import { favoriteService } from '@/services/favorite'
import { storeToRefs } from 'pinia'
import PropertyCard from '@/components/PropertyCard.vue'
import BookingDateDialog from '@/components/BookingDateDialog.vue'
import AmapMap from '@/components/AmapMap.vue'
// GoogleMap ? GM Key ?????
// import GoogleMap from '@/components/GoogleMap.vue'
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

// CrystalRoof 评分
const crystalRoofScore = ref<CrystalRoofScore | null>(null)
const crystalRoofLoading = ref(false)
const showCrystalRoofDialog = ref(false)

// ScoreMyStreet 街区评分
const streetScore = ref<ScoreMyStreetScore | null>(null)
const streetScoreLoading = ref(false)
const showStreetScoreDialog = ref(false)

const ukPostcodeRegex = /\b([A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})\b/i

function extractUKPostcode(text: string): string | null {
  const match = ukPostcodeRegex.exec(text)
  return match ? match[1].toUpperCase() : null
}

// 判断是否显示街区评分徽章：仅 UK 房源且有邮编
const showStreetScore = computed(() => {
  if (!property.value) return false
  const country = (property.value.country || '').toUpperCase()
  const address = property.value.address || ''
  const district = property.value.district || ''
  const combined = `${address} ${district}`
  
  if (country === 'GB' || country === 'UK') {
    return extractUKPostcode(combined) !== null
  }
  
  if (extractUKPostcode(combined) !== null) {
    const ukKeywords = [
      'london', 'uk', 'united kingdom', 'england', 'scotland', 'wales',
      'britain', 'manchester', 'birmingham', 'edinburgh', 'liverpool',
      'leeds', 'sheffield', 'newcastle', 'bristol', 'cardiff', 'glasgow',
      '伦敦', '英国', '英格兰', '苏格兰', '威尔士', '曼彻斯特', '伯明翰',
      '爱丁堡', '利物浦', '利兹', '谢菲尔德', '布里斯托尔', '加的夫', '格拉斯哥',
    ]
    const lower = combined.toLowerCase()
    return ukKeywords.some((k) => lower.includes(k))
  }
  
  return false
})

// 判断是否显示 CrystalRoof 徽章：仅含邮编的房源
const showCrystalRoof = computed(() => {
  if (!property.value) return false
  const country = (property.value.country || '').toUpperCase()
  const address = property.value.address || ''
  const district = property.value.district || ''
  const combined = `${address} ${district}`
  
  if (country === 'GB' || country === 'UK') {
    return extractUKPostcode(combined) !== null
  }
  
  if (extractUKPostcode(combined) !== null) {
    const ukKeywords = [
      'london', 'uk', 'united kingdom', 'england', 'scotland', 'wales',
      'britain', 'manchester', 'birmingham', 'edinburgh', 'liverpool',
      'leeds', 'sheffield', 'newcastle', 'bristol', 'cardiff', 'glasgow',
      '伦敦', '英国', '英格兰', '苏格兰', '威尔士', '曼彻斯特', '伯明翰',
      '爱丁堡', '利物浦', '利兹', '谢菲尔德', '布里斯托尔', '加的夫', '格拉斯哥',
    ]
    const lower = combined.toLowerCase()
    return ukKeywords.some((k) => lower.includes(k))
  }
  
  return false
})

// CrystalRoof 跳转 URL（指向中间页面）
const crystalRoofRedirectUrl = computed(() => {
  if (!crystalRoofScore.value) return '#';
  const postcode = crystalRoofScore.value.postcode || '';
  const params = new URLSearchParams();
  if (postcode) params.set('postcode', postcode);
  return `/crystalroof-redirect.html?${params.toString()}`;
})

// 评分等级样式（颜色编码）
const crystalRoofScoreClass = computed(() => {
  const score = crystalRoofScore.value?.overall_score
  if (score == null) return 'score-unknown'
  if (score >= 80) return 'score-excellent'
  if (score >= 60) return 'score-good'
  if (score >= 40) return 'score-medium'
  return 'score-low'
})

// 街区评分等级样式
const streetScoreClass = computed(() => {
  const score = streetScore.value?.overall_score
  if (score == null) return 'score-unknown'
  if (score >= 80) return 'score-excellent'
  if (score >= 60) return 'score-good'
  if (score >= 40) return 'score-medium'
  return 'score-low'
})

// 安全评分转换为百分比（5分制转100分制）
const safetyScorePercent = computed(() => {
  const score = streetScore.value?.safety_score
  if (score == null) return 0
  return Math.round((score / 5) * 100)
})

// 犯罪率标签类型
const crimeRateTagType = computed(() => {
  const rate = (streetScore.value?.crime_rate || '').toLowerCase()
  if (rate === 'low') return 'success'
  if (rate === 'medium') return 'warning'
  if (rate === 'high') return 'danger'
  return 'info'
})

// 犯罪率中文标签
const crimeRateLabel = computed(() => {
  const rate = (streetScore.value?.crime_rate || '').toLowerCase()
  const labels: Record<string, string> = {
    low: '低',
    medium: '中',
    high: '高',
  }
  return labels[rate] || streetScore.value?.crime_rate || ''
})

function subscoreLabel(key: string): string {
  const labels: Record<string, string> = {
    crime: '治安',
    schools: '学校',
    transport: '交通',
    restaurants: '餐饮',
    shopping: '购物',
  }
  return labels[key] || key
}

function subscoreColor(value: number): string {
  if (value >= 80) return '#67c23a'
  if (value >= 60) return '#409eff'
  if (value >= 40) return '#e6a23c'
  return '#f56c6c'
}

function openStreetScoreDialog() {
  showStreetScoreDialog.value = true
}

async function loadStreetScore() {
  if (!property.value || !showStreetScore.value) {
    streetScore.value = null
    return
  }
  streetScoreLoading.value = true
  try {
    const data = await scoreMyStreetService.getScore(
      property.value.address,
      property.value.country,
    )
    streetScore.value = data
  } catch (err) {
    streetScore.value = null
  } finally {
    streetScoreLoading.value = false
  }
}

function openCrystalRoofDialog() {
  showCrystalRoofDialog.value = true
}

async function loadCrystalRoof() {
  if (!property.value || !showCrystalRoof.value) {
    crystalRoofScore.value = null
    return
  }
  crystalRoofLoading.value = true
  try {
    const data = await crystalRoofService.getScore(
      property.value.address,
      property.value.country,
    )
    crystalRoofScore.value = data
  } catch (err) {
    // 非 UK 地址会被 400 拒绝，忽略
    crystalRoofScore.value = null
  } finally {
    crystalRoofLoading.value = false
  }
}

// Similar properties
const similarProperties = ref<Property[]>([])

// Booking dialog
const showBookingDialog = ref(false)

// Favorites
const isFavorited = ref(false)
const loadingProperty = ref(false)
const togglingFavorite = ref(false)

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

function goToBookingFlow() {
  if (!property.value) return
  router.push({
    path: '/booking/flow',
    query: { property_id: String(property.value.id) },
  })
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
    crystalRoofScore.value = null
    streetScore.value = null
    if (property.value) {
      loadPOI(property.value.id)
      loadSimilar()
      loadCrystalRoof()
      loadStreetScore()
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

.spec-item-clickable {
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s;
  position: relative;
}

.spec-item-clickable:hover {
  background: linear-gradient(180deg, #f0f5ff 0%, #fff 100%);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.12);
}

.spec-item-clickable.loading {
  cursor: wait;
}

.spec-info-icon {
  font-size: 10px;
  color: var(--text-muted);
  cursor: help;
  margin-left: 2px;
  vertical-align: super;
}

.spec-loading {
  color: var(--text-muted);
  font-size: 13px;
  font-weight: normal;
}

.crystalroof-score {
  font-size: 16px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.crystalroof-unknown {
  font-size: 13px;
  font-weight: 500;
  color: var(--primary);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.crystalroof-score.score-excellent { color: #67c23a; }
.crystalroof-score.score-good      { color: #409eff; }
.crystalroof-score.score-medium    { color: #e6a23c; }
.crystalroof-score.score-low       { color: #f56c6c; }
.crystalroof-score.score-unknown   { color: var(--text-muted); font-weight: 500; }

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

/* ── CrystalRoof Dialog ────────────── */

.crystalroof-dialog {
  padding: 4px 0;
}

.crystalroof-header {
  display: flex;
  align-items: center;
  gap: 24px;
}

.crystalroof-score-big {
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding: 18px 24px;
  background: var(--primary-light);
  border-radius: 12px;
  border-left: 4px solid var(--primary);
}

.crystalroof-score-big .score-num {
  font-size: 48px;
  font-weight: 800;
  line-height: 1;
  color: var(--primary);
}

.crystalroof-score-big.score-excellent .score-num { color: #67c23a; }
.crystalroof-score-big.score-good      .score-num { color: #409eff; }
.crystalroof-score-big.score-medium    .score-num { color: #e6a23c; }
.crystalroof-score-big.score-low       .score-num { color: #f56c6c; }
.crystalroof-score-big.score-unknown   .score-num { color: var(--text-muted); }

.crystalroof-score-big .score-suffix {
  font-size: 16px;
  color: var(--text-muted);
  font-weight: 600;
}

.crystalroof-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.meta-label {
  color: var(--text-muted);
  min-width: 80px;
  font-weight: 500;
}

.meta-value {
  color: var(--text-primary);
  word-break: break-word;
}

.crystalroof-subscores h4 {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--text-primary);
}

.subscore-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.subscore-item {
  background: #fafbfc;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 12px 14px;
}

.subscore-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.subscore-value {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.subscore-detail {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}

.crime-types {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.crime-type-tag {
  font-size: 10px;
  padding: 2px 6px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 4px;
  color: var(--text-muted);
}

.crystalroof-tip {
  margin: 8px 0 16px;
}

.crystalroof-tip p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.crystalroof-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
  justify-content: flex-end;
}

.crystalroof-link-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  padding: 0 24px;
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  text-decoration: none;
  transition: all 0.2s;
}

.crystalroof-link-btn:hover {
  background: var(--primary-light);
  color: #fff;
  text-decoration: none;
  opacity: 0.9;
}

.crystalroof-link-btn:active {
  transform: translateY(1px);
}

/* ── ScoreMyStreet Dialog ──────────── */

.street-dialog {
  padding: 4px 0;
}

.street-header {
  display: flex;
  align-items: center;
  gap: 24px;
}

.street-score-big {
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding: 18px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  min-width: 140px;
  justify-content: center;
}

.street-score-big .score-num {
  font-size: 48px;
  font-weight: 800;
  line-height: 1;
  color: #fff;
}

.street-score-big.score-excellent .score-num { color: #fff; }
.street-score-big.score-good      .score-num { color: #fff; }
.street-score-big.score-medium    .score-num { color: #fff; }
.street-score-big.score-low       .score-num { color: #fff; }
.street-score-big.score-unknown   .score-num { color: rgba(255,255,255,0.7); }

.street-score-big .score-suffix {
  font-size: 16px;
  color: rgba(255,255,255,0.8);
  font-weight: 600;
}

.street-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.street-subscores h4 {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--text-primary);
}

.subscore-badge {
  float: right;
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  background: var(--primary-light);
  padding: 2px 8px;
  border-radius: 12px;
}

.street-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
  justify-content: flex-end;
}

.street-link-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  padding: 0 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  text-decoration: none;
  transition: all 0.2s;
}

.street-link-btn:hover {
  color: #fff;
  text-decoration: none;
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.street-link-btn:active {
  transform: translateY(1px);
}

.street-score {
  font-size: 16px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.street-unknown {
  font-size: 13px;
  font-weight: 500;
  color: #667eea;
  text-decoration: underline;
  text-underline-offset: 2px;
}
</style>



