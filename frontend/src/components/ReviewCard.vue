<template>
  <div class="review-card">
    <div class="review-avatar">
      <el-avatar :size="40" :style="{ background: avatarColor }">{{ avatarText }}</el-avatar>
    </div>
    <div class="review-body">
      <div class="review-header">
        <span class="review-user">{{ review.tenant_name || '匿名用户' }}</span>
        <span class="review-date">{{ formatDate(review.created_at) }}</span>
      </div>

      <!-- 房源评分 -->
      <div class="review-rating-row">
        <span class="rating-label">房源</span>
        <el-rate v-model="review.property_rating" disabled size="small" />
      </div>

      <!-- 房东评分（仅个人房东时显示） -->
      <div v-if="review.landlord_rating" class="review-rating-row">
        <span class="rating-label">房东</span>
        <el-rate v-model="review.landlord_rating" disabled size="small" />
      </div>

      <!-- 房源评价 -->
      <p v-if="review.property_comment" class="review-text">{{ review.property_comment }}</p>

      <!-- 房东评价 -->
      <p v-if="review.landlord_comment" class="review-text landlord-comment">
        <span class="tag landlord-tag">对房东</span>
        {{ review.landlord_comment }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ReviewPublic } from '@/types/review'

const props = defineProps<{
  review: ReviewPublic
}>()

const avatarText = computed(() => {
  const name = props.review.tenant_name || '匿'
  return name.charAt(0).toUpperCase()
})

const avatarColor = computed(() => {
  const colors = ['#FF6B35', '#67c23a', '#409eff', '#e6a23c', '#f56c6c', '#909399']
  const idx = props.review.id % colors.length
  return colors[idx]
})

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
</script>

<style scoped>
.review-card {
  display: flex;
  gap: 14px;
  background: #fff;
  border-radius: 15px;
  border: 1px solid #303133;
  padding: 18px 20px;
}

.review-avatar {
  flex-shrink: 0;
}

.review-body {
  flex: 1;
  min-width: 0;
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
  color: #222;
}

.review-date {
  font-size: 12px;
  color: #999;
  margin-left: auto;
}

.review-rating-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.rating-label {
  font-size: 12px;
  color: #999;
  min-width: 28px;
}

.review-text {
  font-size: 14px;
  color: #555;
  line-height: 1.7;
  margin-top: 6px;
}

.landlord-comment {
  padding-left: 12px;
  border-left: 3px solid #e6a23c;
}

.tag {
  display: inline-block;
  font-size: 11px;
  font-weight: 500;
  border-radius: 4px;
  padding: 1px 6px;
  margin-right: 6px;
}

.landlord-tag {
  background: #faecd8;
  color: #e6a23c;
}
</style>
