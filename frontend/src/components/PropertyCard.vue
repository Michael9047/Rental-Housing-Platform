<template>
  <el-card
    class="property-card"
    shadow="hover"
    :body-style="{ padding: '0' }"
    @click="$router.push(`/property/${property.id}`)"
  >
    <!-- Property image -->
    <div class="card-image">
      <img
        v-if="primaryImageUrl"
        :src="primaryImageUrl"
        alt="property image"
        class="property-img"
      />
      <template v-else>
        <el-icon :size="48" color="#c0c4cc"><PictureFilled /></el-icon>
        <span class="image-placeholder">????</span>
      </template>
    </div>

    <div class="card-body">
      <h3 class="card-title">{{ property.title }}</h3>

      <div class="card-tags">
        <el-tag size="small" type="info">{{ typeLabels[property.property_type] }}</el-tag>
        <el-tag size="small">{{ property.district }}</el-tag>
        <el-tag size="small" type="info">{{ property.bedrooms }}室{{ property.bathrooms }}卫</el-tag>
      </div>

      <div class="card-meta">
        <span class="card-address">{{ property.address }}</span>
        <span v-if="property.area_sqm" class="card-area">{{ property.area_sqm }} ㎡</span>
      </div>

      <div class="card-footer">
        <span class="card-price">
          <strong>{{ property.price_monthly }}</strong> 元/月
        </span>
        <span v-if="showSimilarity && property.similarity != null" class="card-similarity">
          匹配度 {{ (property.similarity * 100).toFixed(0) }}%
        </span>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { PictureFilled } from '@element-plus/icons-vue'
import type { Property, PropertySearchResult, PropertyType } from '@/types/property'

import { computed } from 'vue'

const props = defineProps<{
  property: Property | PropertySearchResult
  showSimilarity?: boolean
}>()

const primaryImageUrl = computed(() => {
  const images = props.property.images
  if (!images || images.length === 0) return null
  const primary = images.find((img) => img.is_primary) || images[0]
  return `/api/v1/uploads/${primary.filename}`
})

const typeLabels: Record<PropertyType, string> = {
  apartment: '公寓',
  house: '别墅',
  studio: '单间',
  shared: '合租',
}
</script>

<style scoped>
.property-card {
  cursor: pointer;
  transition: transform 0.2s;
}

.property-card:hover {
  transform: translateY(-4px);
}

.card-image {
  height: 180px;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.image-placeholder {
  font-size: 13px;
  color: #c0c4cc;
}

.property-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.card-body {
  padding: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.card-meta {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #909399;
  margin-bottom: 12px;
}

.card-address {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-deposit {
  font-size: 12px;
  color: #909399;
  margin-left: 8px;
}

.card-price {
  font-size: 18px;
  color: #f56c6c;
}

.card-price strong {
  font-size: 22px;
}

.card-similarity {
  font-size: 12px;
  color: #67c23a;
  font-weight: 600;
}
</style>
