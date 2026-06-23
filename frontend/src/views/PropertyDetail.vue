<template>
  <div class="detail-page" v-loading="loading">
    <div v-if="property">
      <!-- Back button -->
      <el-button text :icon="ArrowLeft" @click="$router.back()" class="back-btn">返回</el-button>

      <!-- Image Gallery -->
      <div v-if="property.images && property.images.length > 0" class="image-gallery">
        <el-carousel :interval="4000" type="card" height="400px" trigger="click">
          <el-carousel-item v-for="img in sortedImages" :key="img.id">
            <el-image
              :src="`/api/v1/uploads/${img.filename}`"
              fit="cover"
              class="gallery-image"
              :preview-src-list="allImageUrls"
              :initial-index="sortedImages.indexOf(img)"
              preview-teleported
            />
          </el-carousel-item>
        </el-carousel>
      </div>

      <!-- Title & Basic Info -->
      <div class="detail-header">
        <h1>{{ property.title }}</h1>
        <div class="header-meta">
          <el-tag :type="statusTagType">{{ statusLabel }}</el-tag>
          <el-tag type="info">{{ typeLabel }}</el-tag>
          <span class="meta-item">{{ property.district }}</span>
          <span class="meta-item">{{ property.address }}</span>
        </div>
      </div>

      <!-- Price & Book Button -->
      <div class="price-section">
        <div class="price-info">
          <span class="price-value">{{ property.price_monthly }}</span>
          <span class="price-unit">元/月</span>
        <div v-if="property.deposit_amount" class="fee-info">
          <span>押金: ¥{{ property.deposit_amount }}</span>
          <span v-if="property.service_fee_rate"> | 服务费: {{ (property.service_fee_rate * 100).toFixed(0) }}%</span>
        </div>
        </div>
        <el-button
          v-if="authStore.isLoggedIn && !authStore.isLandlord"
          type="primary"
          size="large"
          @click="showBookingDialog = true"
        >
          预约看房
        </el-button>
      </div>

      <!-- Key Details -->
      <el-card shadow="never" class="detail-card">
        <el-row :gutter="24">
          <el-col :span="6">
            <div class="detail-item">
              <span class="detail-label">户型</span>
              <span class="detail-value">{{ property.bedrooms }}室{{ property.bathrooms }}卫</span>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="detail-item">
              <span class="detail-label">面积</span>
              <span class="detail-value">{{ property.area_sqm ? property.area_sqm + ' ㎡' : '暂无' }}</span>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="detail-item">
              <span class="detail-label">类型</span>
              <span class="detail-value">{{ typeLabel }}</span>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="detail-item">
              <span class="detail-label">状态</span>
              <span class="detail-value">{{ statusLabel }}</span>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- Description -->
      <el-card v-if="property.description" shadow="never" class="detail-card">
        <template #header><span>房源描述</span></template>
        <p class="description-text">{{ property.description }}</p>
      </el-card>

      <!-- Meta -->
      <el-card shadow="never" class="detail-card">
        <template #header><span>其他信息</span></template>
        <p class="meta-text">发布于 {{ formatDate(property.created_at) }}</p>
        <p class="meta-text">更新于 {{ formatDate(property.updated_at) }}</p>
      </el-card>
    </div>

    <el-empty v-else-if="!loading" description="房源未找到" />

    <!-- 位置信息 -->
    <el-card class="info-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>位置信息</span>
        </div>
      </template>
      <div class="map-section">
        <p class="map-address"><strong>{{ property.address }}</strong></p>
        <p v-if="property.latitude" class="map-coords">
          经纬度: {{ property.latitude.toFixed(4) }}, {{ property.longitude.toFixed(4) }}
        </p>
        <el-link
          :href="'https://uri.amap.com/marker?position=' + (property.longitude || 120.585) + ',' + (property.latitude || 31.299)"
          target="_blank"
          type="primary">
          在高德地图中查看 ↗
        </el-link>
      </div>
    </el-card>

    <!-- 周边设施 -->
    <el-card v-if="poiData" class="info-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>周边设施</span>
        </div>
      </template>
      <div v-loading="poiLoading">
        <p class="poi-summary">{{ poiData.content }}</p>
        <div v-if="poiData.poi_data" class="poi-grid">
          <div v-for="(items, cat) in poiData.poi_data" :key="cat" class="poi-cat">
            <h4>{{ cat }}</h4>
            <div v-for="item in items" :key="item.name" class="poi-row">
              <span>{{ item.name }}</span>
              <span class="poi-dist">{{ item.distance }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- Booking Dialog -->
    <el-dialog v-model="showBookingDialog" title="预约看房" width="480px">
      <el-form :model="bookingForm" label-width="100px">
        <el-form-item label="预约日期">
          <el-date-picker
            v-model="bookingForm.scheduled_date"
            type="date"
            placeholder="选择看房日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="留言">
          <el-input
            v-model="bookingForm.message"
            type="textarea"
            :rows="3"
            placeholder="给房东留言（如：联系方式、看房时间偏好等）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBookingDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleBook">
          提交预约
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { usePropertyStore } from '@/stores/property'
import { useAuthStore } from '@/stores/auth'
import { bookingService } from '@/services/booking'
import { propertyService } from '@/services/property'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import type { PropertyStatus, PropertyType } from '@/types/property'

const route = useRoute()
const propertyStore = usePropertyStore()
const authStore = useAuthStore()
const { currentProperty: property, loading } = storeToRefs(propertyStore)

const poiData = ref(null)
const poiLoading = ref(false)
async function loadPOI(pid) {
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

const showBookingDialog = ref(false)
const submitting = ref(false)
const bookingForm = reactive({
  scheduled_date: '',
  message: '',
})

const statusLabels: Record<PropertyStatus, string> = {
  available: '可租',
  rented: '已租',
  maintenance: '维护中',
  offline: '已下架',
}

const typeLabels: Record<PropertyType, string> = {
  apartment: '公寓',
  house: '别墅',
  studio: '单间',
  shared: '合租',
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
  sortedImages.value.map((img) => `/api/v1/uploads/${img.filename}`)
)

const statusLabel = computed(() => property.value ? statusLabels[property.value.status] : '')
const typeLabel = computed(() => property.value ? typeLabels[property.value.property_type] : '')

const statusTagType = computed(() => {
  if (!property.value) return 'info'
  const map: Record<PropertyStatus, string> = {
    available: 'success',
    rented: 'warning',
    maintenance: 'info',
    offline: 'danger',
  }
  return map[property.value.status]
})

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

async function handleBook() {
  if (!bookingForm.scheduled_date && !bookingForm.message) {
    ElMessage.warning('请至少填写预约日期或留言')
    return
  }
  submitting.value = true
  try {
    await bookingService.create({
      property_id: property.value!.id,
      scheduled_date: bookingForm.scheduled_date || undefined,
      message: bookingForm.message || undefined,
    })
    ElMessage.success('预约提交成功')
    showBookingDialog.value = false
    bookingForm.scheduled_date = ''
    bookingForm.message = ''
  } catch (err: any) {
    if (err?.response?.status === 409) {
      ElMessage.warning('您已对该房源发起过预约')
    }
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  const id = Number(route.params.id)
  if (id) {
    propertyStore.fetchById(id).then(() => {
      if (property.value) loadPOI(property.value.id)
    })
  }
})
</script>

<style scoped>
.detail-page {
  max-width: 900px;
  margin: 0 auto;
}

.back-btn {
  margin-bottom: 16px;
}

.image-gallery {
  margin-bottom: 24px;
}

.gallery-image {
  width: 100%;
  height: 400px;
}

.detail-header h1 {
  font-size: 26px;
  color: #303133;
  margin-bottom: 12px;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}

.meta-item {
  font-size: 14px;
  color: #606266;
}

.price-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.price-value {
  font-size: 32px;
  font-weight: 700;
  color: #f56c6c;
}

.price-unit {
  font-size: 16px;
  color: #909399;
  margin-left: 4px;
}

.detail-card {
  margin-bottom: 16px;
}

.detail-item {
  text-align: center;
}

.detail-label {
  display: block;
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}

.detail-value {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.description-text {
  font-size: 14px;
  color: #606266;
  line-height: 1.8;
  white-space: pre-wrap;
}

.meta-text {
  font-size: 13px;
  color: #909399;
  margin-bottom: 4px;
}
</style>
