<template>
  <div class="admin-detail-page" v-loading="loading">
    <div class="page-head">
      <div>
        <h2>信息通知</h2>
        <span>{{ total }} 条未读业务通知</span>
      </div>
      <el-button :icon="Refresh" @click="loadData">刷新</el-button>
    </div>

    <div v-if="items.length" class="notice-list">
      <button
        v-for="item in items"
        :key="item.id"
        class="notice-card"
        @click="markNoticeRead(item)"
      >
        <span class="notice-main">
          <strong>{{ item.title }}</strong>
          <span>{{ item.content || item.body || '-' }}</span>
        </span>
        <span class="notice-meta">
          <el-tag size="small" effect="plain">{{ item.entity_type || item.type }}</el-tag>
          <time>{{ formatDateTime(item.created_at) }}</time>
        </span>
      </button>
    </div>
    <el-empty v-else description="暂无未读业务通知" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { notificationService } from '@/services/notification'
import type { Notification } from '@/types/booking'

const loading = ref(false)
const items = ref<Notification[]>([])
const total = ref(0)

function formatDateTime(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

async function markNoticeRead(item: Notification) {
  await notificationService.markRead(item.id)
  await loadData()
}

async function loadData() {
  loading.value = true
  try {
    const result = await notificationService.list({
      page: 1,
      page_size: 100,
      unread_only: true,
      business_only: true,
    })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.admin-detail-page {
  box-sizing: border-box;
  width: 100%;
}

.page-head {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

h2 {
  color: #303133;
  margin: 0;
}

.page-head span {
  color: #909399;
  font-size: 13px;
}

.notice-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 360px), 1fr));
  align-items: start;
  gap: 10px;
}

.notice-card {
  align-items: center;
  background: #fff7f2;
  border: 1px solid #f3c3aa;
  border-radius: 8px;
  box-sizing: border-box;
  cursor: pointer;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  padding: 14px;
  text-align: left;
  width: 100%;
  min-width: 0;
}

.notice-card:hover {
  border-color: #f06f3d;
}

.notice-main {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.notice-main strong {
  color: #303133;
}

.notice-main span {
  color: #606266;
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.notice-meta {
  align-items: flex-end;
  color: #909399;
  display: flex;
  flex-direction: column;
  flex: 0 0 auto;
  font-size: 12px;
  gap: 8px;
}

@media (max-width: 760px) {
  .notice-card {
    align-items: flex-start;
    flex-direction: column;
  }

  .notice-meta {
    align-items: flex-start;
  }
}
</style>
