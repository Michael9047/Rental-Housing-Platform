<template>
  <main class="notification-center">
    <section class="notification-toolbar">
      <div class="toolbar-title"><h1>消息中心</h1><p>{{ unreadCount }} 条未读消息</p></div>
      <div class="toolbar-actions">
        <el-radio-group v-model="filter" size="small" aria-label="消息筛选"><el-radio-button label="all">全部</el-radio-button><el-radio-button label="unread">未读</el-radio-button></el-radio-group>
        <el-button text @click="router.push('/profile')">返回个人中心</el-button>
        <el-button :disabled="unreadCount === 0" @click="markAllRead">{{ unreadCount ? '全部标为已读' : '已全部读完' }}</el-button>
      </div>
    </section>

    <el-skeleton v-if="loading" class="notification-skeleton" :rows="6" animated />
    <section v-else-if="loadError" class="notification-feedback"><p>消息暂时无法加载。</p><el-button type="primary" @click="load">重试</el-button></section>
    <section v-else-if="items.length === 0" class="notification-feedback">暂无消息</section>
    <ul v-else class="notification-list" aria-live="polite">
      <li v-for="item in filteredItems" :key="item.id" class="notification-list-item">
        <RouterLink v-if="orderRoute(item)" :to="orderRoute(item)!" class="notification-card" :class="cardClasses(item)" :aria-label="cardLabel(item)" @click="markReadOptimistically(item)">
          <span class="notification-icon" aria-hidden="true">{{ typeIcon(item) }}</span>
          <span class="notification-content"><span class="notification-title-row"><span v-if="!item.is_read" class="unread-dot" aria-label="未读"></span><strong>{{ item.title }}</strong></span><span class="notification-body">{{ item.body || item.content || '关联订单通知' }}</span><span class="notification-meta"><span>订单 {{ item.order_id }}</span><time>{{ formatDate(item.created_at) }}</time></span></span>
          <span class="notification-action"><el-tag size="small" effect="plain">{{ statusText(item) }}</el-tag><span>{{ actionText(item) }} →</span></span>
        </RouterLink>
        <article v-else class="notification-card unavailable" :class="cardClasses(item)" :aria-label="cardLabel(item)">
          <span class="notification-icon" aria-hidden="true">{{ typeIcon(item) }}</span>
          <span class="notification-content"><span class="notification-title-row"><span v-if="!item.is_read" class="unread-dot" aria-label="未读"></span><strong>{{ item.title }}</strong></span><span class="notification-body">{{ item.body || item.content || '关联订单不可用' }}</span><span class="notification-meta"><time>{{ formatDate(item.created_at) }}</time></span></span>
          <span class="notification-action"><span>关联订单不可用</span></span>
        </article>
      </li>
    </ul>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { notificationService } from '@/services/notification'
import type { Notification } from '@/types/booking'

const router = useRouter(); const items = ref<Notification[]>([]); const unreadCount = ref(0); const loading = ref(true); const loadError = ref(false); const filter = ref('all')
const filteredItems = computed(() => filter.value === 'unread' ? items.value.filter((item) => !item.is_read) : items.value)
const orderRoute = (item: Notification) => item.entity_type === 'order' && item.entity_id ? `/my-orders/${item.entity_id}` : null
const formatDate = (value: string) => new Date(value).toLocaleString('zh-CN', { dateStyle: 'medium', timeStyle: 'short' })
const statusText = (item: Notification) => ({ payment_pending: '待支付', payment_processing: '处理中', payment_failed: '支付失败', paid: '已支付', payment_expired: '已失效', payment_review: '退款核对', refunded: '已退款' }[item.payment_status || ''] || '订单通知')
const actionText = (item: Notification) => ({ payment_pending: '查看并支付', payment_processing: '查看支付状态', payment_failed: '重新支付', paid: '查看预订', payment_expired: '查看取消详情', payment_review: '查看退款状态', refunded: '查看退款详情' }[item.payment_status || ''] || '查看订单')
const typeIcon = (item: Notification) => item.payment_status === 'paid' ? '✓' : ['payment_failed', 'payment_expired'].includes(item.payment_status || '') ? '!' : item.payment_status === 'payment_processing' ? '…' : '●'
const cardClasses = (item: Notification) => ({ unread: !item.is_read, danger: ['payment_failed', 'payment_expired'].includes(item.payment_status || ''), success: item.payment_status === 'paid' })
const cardLabel = (item: Notification) => `${item.order_id ? `查看订单 ${item.order_id}` : '查看消息'}：${item.title}`
async function load() { loading.value = true; loadError.value = false; try { const result = await notificationService.list({ page: 1, page_size: 50 }); items.value = result.items; unreadCount.value = (await notificationService.getUnreadCount()).count } catch { loadError.value = true } finally { loading.value = false } }
function markReadOptimistically(item: Notification) { if (item.is_read) return; item.is_read = true; unreadCount.value = Math.max(0, unreadCount.value - 1); window.dispatchEvent(new Event('notifications:changed')); notificationService.markRead(item.id).catch(() => { item.is_read = false; unreadCount.value += 1; window.dispatchEvent(new Event('notifications:changed')) }) }
async function markAllRead() { if (!unreadCount.value) return; const previous = unreadCount.value; items.value.forEach((item) => { item.is_read = true }); unreadCount.value = 0; window.dispatchEvent(new Event('notifications:changed')); try { await notificationService.markAllRead() } catch { unreadCount.value = previous; await load() } }
onMounted(load)
</script>

<style scoped>
.notification-center{width:min(960px,calc(100% - 32px));margin:0 auto;padding:28px 0 40px}.notification-toolbar{display:flex;justify-content:space-between;gap:20px;align-items:center;padding:22px 24px;margin-bottom:16px;background:#fff;border:1px solid #e9edf2;border-radius:14px;box-shadow:0 2px 10px rgba(15,23,42,.05)}.toolbar-title h1{margin:0;font-size:30px;line-height:1.25;color:#1f2937}.toolbar-title p{margin:6px 0 0;color:#667085;font-size:14px}.toolbar-actions{display:flex;align-items:center;justify-content:flex-end;gap:8px;flex-wrap:wrap}.notification-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:15px;width:100%}.notification-list-item{list-style:none;margin:0;padding:0;width:100%}.notification-card{width:100%;min-width:0;box-sizing:border-box;min-height:96px;padding:18px 20px;display:grid;grid-template-columns:44px minmax(0,1fr) auto;align-items:center;column-gap:16px;background:#fff;border:1px solid #e4e7ec;border-radius:14px;box-shadow:0 2px 8px rgba(15,23,42,.04);color:inherit;text-decoration:none;transition:transform .16s ease,box-shadow .16s ease,border-color .16s ease}.notification-card:not(.unavailable){cursor:pointer}.notification-card:not(.unavailable):hover{transform:translateY(-1px);border-color:#409eff;box-shadow:0 7px 18px rgba(15,23,42,.11)}.notification-card:focus-visible{outline:3px solid #409eff;outline-offset:2px}.notification-card.unread{background:#f4f8ff;border-left:4px solid #409eff;padding-left:17px}.notification-icon{width:38px;height:38px;display:grid;place-items:center;border-radius:50%;background:#eaf3ff;color:#2581d9;font-size:18px;font-weight:700}.notification-card.success .notification-icon{background:#ecf9ef;color:#2d9c4b}.notification-card.danger .notification-icon{background:#fff0f0;color:#d94a4a}.notification-content{min-width:0;display:block}.notification-title-row{display:flex;align-items:center;gap:8px;line-height:1.4}.notification-title-row strong{font-size:18px;font-weight:600;color:#273142;overflow-wrap:anywhere}.unread-dot{width:8px;height:8px;flex:0 0 8px;border-radius:50%;background:#409eff}.notification-body{display:block;margin-top:6px;color:#667085;font-size:14px;line-height:1.55;overflow-wrap:anywhere}.notification-meta{display:flex;gap:12px;flex-wrap:wrap;margin-top:8px;color:#8a94a6;font-size:13px;line-height:1.4}.notification-action{display:flex;align-items:flex-end;gap:8px;flex-direction:column;white-space:nowrap;color:#3b82f6;font-size:13px;font-weight:600}.unavailable{cursor:default;opacity:.82}.unavailable .notification-action{color:#8a94a6;font-weight:400}.notification-feedback{display:flex;min-height:180px;align-items:center;justify-content:center;gap:12px;flex-direction:column;background:#fff;border:1px solid #e4e7ec;border-radius:14px}.notification-skeleton{padding:24px;background:#fff;border-radius:14px}@media(max-width:1024px){.notification-center{width:min(960px,calc(100% - 48px))}}@media(max-width:768px){.notification-center{width:calc(100% - 24px);padding:16px 0 28px}.notification-toolbar{padding:18px 16px;align-items:flex-start;flex-direction:column}.toolbar-title h1{font-size:24px}.toolbar-actions{width:100%;justify-content:flex-start}.notification-card{grid-template-columns:36px minmax(0,1fr);padding:14px;column-gap:12px;min-height:44px}.notification-card.unread{padding-left:11px}.notification-icon{width:32px;height:32px;font-size:15px}.notification-title-row strong{font-size:16px}.notification-body{font-size:14px}.notification-action{grid-column:2;align-items:flex-start;flex-direction:row;justify-content:space-between;white-space:normal;margin-top:2px}.notification-meta{gap:8px}.toolbar-actions .el-button{min-height:36px}}
</style>
