<template>
  <div class="detail-page" v-loading="loading">
    <div v-if="property">
      <!-- Back button -->
      <el-button text :icon="ArrowLeft" @click=".back()" class="back-btn">返回</el-button>

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

      <!-- Price -->
      <div class="price-section">
        <span class="price-value">{{ property.price_monthly }}</span>
        <span class="price-unit">元/月</span>
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
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { usePropertyStore } from '@/stores/property'
import { storeToRefs } from 'pinia'
import type { PropertyStatus, PropertyType } from '@/types/property'

const route = useRoute()
const propertyStore = usePropertyStore()
const { currentProperty: property, loading } = storeToRefs(propertyStore)

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

onMounted(() => {
  const id = Number(route.params.id)
  if (id) propertyStore.fetchById(id)
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
