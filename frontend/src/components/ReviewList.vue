<template>
  <div class="review-list" v-loading="loading">
    <!-- 评分概要 -->
    <div class="review-summary" v-if="stats">
      <div class="summary-score">
        <span class="score-num">{{ displayRating }}</span>
        <span class="score-unit">/5</span>
      </div>
      <div class="summary-stars">
        <div class="star-row">
          <span class="star-label">房源</span>
          <el-rate v-model="displayRating" disabled show-score />
        </div>
        <div v-if="stats.avg_landlord_rating" class="star-row">
          <span class="star-label">房东</span>
          <el-rate v-model="stats.avg_landlord_rating" disabled show-score />
        </div>
      </div>
      <span class="summary-count">共 {{ stats.total_reviews }} 条评价</span>
    </div>

    <!-- 评价列表 -->
    <div v-if="reviews.length > 0" class="review-items">
      <ReviewCard v-for="r in reviews" :key="r.id" :review="r" />
    </div>
    <el-empty v-else description="暂无评价" />

    <!-- 写评价按钮 -->
    <div v-if="showWriteButton" class="write-btn-row">
      <el-button type="primary" @click="$emit('write')">写评价</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ReviewCard from './ReviewCard.vue'
import type { ReviewPublic, ReviewAggregation } from '@/types/review'

const props = defineProps<{
  reviews: ReviewPublic[]
  stats: ReviewAggregation | null
  loading: boolean
  showWriteButton: boolean
}>()

defineEmits<{
  write: []
}>()

const displayRating = computed(() => {
  if (!props.stats?.avg_property_rating) return 0
  return Math.round(props.stats.avg_property_rating * 10) / 10
})
</script>

<style scoped>
.review-list {
  margin-top: 24px;
}

.review-summary {
  display: flex;
  align-items: center;
  gap: 20px;
  background: #fff;
  border-radius: 15px;
  border: 1px solid #303133;
  padding: 20px 24px;
  margin-bottom: 16px;
}

.summary-score {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.score-num {
  font-size: 36px;
  font-weight: 800;
  color: #409eff;
  line-height: 1;
}

.score-unit {
  font-size: 16px;
  color: #999;
  font-weight: 600;
}

.summary-stars {
  flex: 1;
}

.star-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.star-label {
  font-size: 12px;
  color: #999;
  min-width: 28px;
}

.summary-count {
  font-size: 14px;
  color: #999;
}

.review-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.write-btn-row {
  text-align: center;
}
</style>
