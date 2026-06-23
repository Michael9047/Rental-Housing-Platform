<template>
  <div class="notifications-page" v-loading="loading">
    <div class="notifications-header">
      <h2>通知</h2>
      <el-button v-if="notifications.length > 0" text type="primary" @click="handleMarkAllRead">
        全部已读
      </el-button>
    </div>

    <el-empty v-if="!loading && notifications.length === 0" description="暂无通知" />

    <div v-for="notification in notifications" :key="notification.id" class="notification-item" :class="{ unread: !notification.is_read }" @click="handleClick(notification)">
      <div class="notification-title">
        <el-badge v-if="!notification.is_read" is-dot class="unread-dot" />
        <span>{{ notification.title }}</span>
      </div>
      <p v-if="notification.content" class="notification-content">{{ notification.content }}</p>
      <span class="notification-time">{{ formatDate(notification.created_at) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { notificationService } from '@/services/notification'
import type { Notification } from '@/types/booking'

const notifications = ref<Notification[]>([])
const loading = ref(false)

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

async function fetchNotifications() {
  loading.value = true
  try {
    notifications.value = await notificationService.list()
  } finally {
    loading.value = false
  }
}

async function handleClick(notification: Notification) {
  if (!notification.is_read) {
    await notificationService.markRead(notification.id)
    notification.is_read = true
  }
}

async function handleMarkAllRead() {
  await notificationService.markAllRead()
  notifications.value.forEach((n) => (n.is_read = true))
}

onMounted(fetchNotifications)
</script>

<style scoped>
.notifications-page {
  max-width: 700px;
  margin: 0 auto;
}

.notifications-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.notifications-header h2 {
  font-size: 22px;
  color: #303133;
  margin: 0;
}

.notification-item {
  padding: 16px;
  background: #fff;
  border-radius: 8px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.notification-item:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.notification-item.unread {
  background: #ecf5ff;
  border-left: 3px solid #409eff;
}

.notification-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}

.unread-dot {
  margin-right: 4px;
}

.notification-content {
  margin: 8px 0 4px;
  font-size: 13px;
  color: #606266;
}

.notification-time {
  font-size: 12px;
  color: #c0c4cc;
}
</style>
