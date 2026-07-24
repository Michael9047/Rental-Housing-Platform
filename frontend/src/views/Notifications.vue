<template>
  <div class="notifications-page" v-loading="loading">
    <div class="notifications-header">
      <h2>消息中心</h2>
      <div class="header-actions">
        <el-radio-group v-model="filter" size="small" @change="fetchNotifications">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="unread">未读</el-radio-button>
        </el-radio-group>
        <el-button v-if="unreadCount > 0" text type="primary" @click="handleMarkAllRead">
          全部标为已读 ({{ unreadCount > 99 ? '99+' : unreadCount }})
        </el-button>
      </div>
    </div>

    <el-empty v-if="!loading && notifications.length === 0" description="暂无通知" />

    <div class="notification-list">
      <div
        v-for="notification in notifications"
        :key="notification.id"
        class="notification-card"
        :class="{ unread: !notification.is_read }"
        @click="handleClick(notification)"
      >
        <div class="card-left">
          <span v-if="!notification.is_read" class="unread-dot" />
          <el-icon v-else class="read-icon" :size="10"><Check /></el-icon>
        </div>
        <div class="card-body">
          <div class="card-title">
            <span class="event-badge">{{ getEventLabel(notification.type) }}</span>
            {{ notification.title }}
          </div>
          <p v-if="notification.content" class="card-content">{{ notification.content }}</p>
          <div class="card-footer">
            <span class="card-time">{{ formatTime(notification.created_at) }}</span>
            <span v-if="notification.order_id" class="card-link">
              <el-icon :size="12"><Link /></el-icon>
              订单 #{{ notification.order_id }}
            </span>
          </div>
        </div>
        <div class="card-right">
          <el-icon :size="16" color="#c0c4cc"><ArrowRight /></el-icon>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Check, Link, ArrowRight } from '@element-plus/icons-vue'
import { notificationService } from '@/services/notification'
import type { Notification } from '@/types/notification'

const router = useRouter()
const notifications = ref<Notification[]>([])
const unreadCount = ref(0)
const loading = ref(false)
const filter = ref<'all' | 'unread'>('all')

// ── 事件类型中文映射 ──────────────────────────────────────
const EVENT_LABELS: Record<string, string> = {
  contract_signed: '合同签署',
  payment_pending: '待支付',
  payment_failed: '支付失败',
  payment_processing: '处理中',
  payment_expiring_3h: '即将截止',
  payment_expiring_in_3_hours: '即将截止',
  payment_succeeded: '支付成功',
  booking_confirmed: '预订确认',
  order_auto_cancelled: '已取消',
  payment_review: '核对中',
  refund_pending: '退款中',
  refunded: '已退款',
  contract_expiring: '合同临期',
  // 旧类型兼容
  booking_created: '预约创建',
  booking_approved: '预约通过',
  booking_rejected: '预约拒绝',
  booking_cancelled: '预约取消',
  booking_completed: '预约完成',
  payment_received: '支付到账',
  payment_created: '支付发起',
  payment_expired: '支付过期',
  contract_generated: '合同生成',
  auth_registration: '注册成功',
  auth_password_reset: '密码重置',
  repair_created: '报修创建',
  repair_assigned: '报修分配',
  repair_completed: '报修完成',
  repair_status_change: '报修更新',
  system: '系统通知',
}

function getEventLabel(type: string): string {
  return EVENT_LABELS[type] || type
}

// ── 格式化时间 ──────────────────────────────────────────
function formatTime(dateStr: string): string {
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60_000) return '刚刚'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}分钟前`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}小时前`
  return d.toLocaleDateString('zh-CN')
}

// ── 数据获取 ────────────────────────────────────────────
async function fetchNotifications() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filter.value !== 'all') params.filter = filter.value
    notifications.value = await notificationService.list(params)
  } finally {
    loading.value = false
  }
}

async function fetchUnreadCount() {
  try {
    const result = await notificationService.getUnreadCount()
    unreadCount.value = result.count
  } catch { /* 铃铛后台静默刷新 */ }
}

// ── 消息点击 → 乐观标记已读 + 跳转 ─────────────────────
async function handleClick(notification: Notification) {
  // 1. 乐观标记已读
  if (!notification.is_read) {
    notification.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
    // 2. 调用后端已读接口（不阻塞跳转）
    notificationService.markRead(notification.id).catch(() => {
      // 乐观回滚
      notification.is_read = false
      unreadCount.value += 1
    })
  }

  // 3. 根据实体类型跳转
  if (notification.order_id) {
    router.push(`/orders/${notification.order_id}`)
  } else if (notification.entity_type === 'property' && notification.property_id) {
    router.push(`/properties/${notification.property_id}`)
  }
}

async function handleMarkAllRead() {
  await notificationService.markAllRead()
  notifications.value.forEach(n => (n.is_read = true))
  unreadCount.value = 0
}

onMounted(() => {
  fetchNotifications()
  fetchUnreadCount()
})
</script>

<style scoped>
.notifications-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 16px;
}

.notifications-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}

.notifications-header h2 {
  font-size: 22px;
  color: #303133;
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* ── 消息卡片 ────────────────────────────── */
.notification-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.notification-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  background: #fff;
  border-radius: 12px;
  cursor: pointer;
  transition: box-shadow 0.2s, transform 0.15s;
  border: 1px solid #f0f0f0;
}

.notification-card:hover {
  box-shadow: 0 2px 12px rgba(0,0,0,.08);
  transform: translateY(-1px);
}

.notification-card.unread {
  background: #f0f7ff;
  border-left: 3px solid #409eff;
}

.card-left {
  flex-shrink: 0;
  padding-top: 4px;
}

.unread-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  background: #409eff;
  border-radius: 50%;
}

.read-icon {
  color: #c0c4cc;
}

.card-body {
  flex: 1;
  min-width: 0;
}

.card-title {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 8px;
}

.event-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  background: #ecf5ff;
  color: #409eff;
  white-space: nowrap;
}

.card-content {
  margin: 8px 0 6px;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-footer {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-time {
  font-size: 12px;
  color: #c0c4cc;
}

.card-link {
  font-size: 12px;
  color: #409eff;
  display: flex;
  align-items: center;
  gap: 2px;
}

.card-right {
  flex-shrink: 0;
  align-self: center;
}

/* ── 响应式 ─────────────────────────────── */
@media (max-width: 768px) {
  .notifications-page { padding: 16px 12px; }
  .notifications-header { flex-direction: column; align-items: flex-start; }
}
</style>
