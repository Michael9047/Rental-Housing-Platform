<template>
  <main class="simulation-page">
    <el-alert title="仅开发环境：仅模拟通知，不修改订单、支付、合同或退款状态。" type="warning" :closable="false" show-icon />
    <el-card class="panel">
      <template #header><strong>通知模拟触发</strong></template>
      <el-form label-width="110px" @submit.prevent>
        <el-form-item label="选择订单"><el-select v-model="bookingId" class="wide" filterable placeholder="选择权限范围内的订单"><el-option v-for="order in orders" :key="order.id" :label="`订单 #${order.id}（${order.status}）`" :value="order.id" /></el-select></el-form-item>
        <el-form-item label="通知事件"><el-select v-model="eventType" class="wide"><el-option v-for="event in events" :key="event" :label="eventLabels[event] || event" :value="event" /></el-select></el-form-item>
        <el-form-item label="模拟结果"><el-radio-group v-model="outcome"><el-radio value="success">成功</el-radio><el-radio value="retry_success">首次失败，重试成功</el-radio><el-radio value="failed">持续失败</el-radio></el-radio-group></el-form-item>
        <el-form-item><el-button type="primary" :loading="loading" :disabled="!bookingId || !eventType" @click="dispatch">模拟触发</el-button></el-form-item>
      </el-form>
    </el-card>
    <el-card v-if="results.length" class="panel">
      <template #header><strong>本次模拟结果</strong></template>
      <el-table :data="results" style="width:100%" size="small">
        <el-table-column prop="recipient" label="收件人（脱敏）" min-width="150" />
        <el-table-column prop="role" label="角色" min-width="100" />
        <el-table-column prop="channel" label="渠道" min-width="90" />
        <el-table-column prop="status" label="状态" min-width="110"><template #default="{ row }"><el-tag :type="tagType(row.status)">{{ row.status }}</el-tag></template></el-table-column>
        <el-table-column prop="attempts" label="重试次数" min-width="90" />
        <el-table-column label="时间" min-width="170"><template #default="{ row }">{{ formatTime(row.sent_at) }}</template></el-table-column>
        <el-table-column prop="detail" label="详情/内部跳转" min-width="220" />
      </el-table>
      <p class="hint">站内消息已写入消息中心；请以对应租户或管理员身份打开“消息中心”验证跳转。</p>
    </el-card>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { adminService } from '@/services/admin'

const bookingId = ref<number | undefined>()
const eventType = ref('PAYMENT_SUCCEEDED')
const outcome = ref<'success' | 'retry_success' | 'failed'>('success')
const loading = ref(false)
const results = ref<Array<{ recipient: string; role: string; channel: string; status: string; attempts: number; sent_at: string; detail: string }>>([])
const orders = ref<Array<{ id: number; status: string; institute_id: number | null }>>([])
const events = ref<string[]>(['PAYMENT_SUCCEEDED', 'PAYMENT_FAILED', 'PAYMENT_EXPIRING_3H', 'CONTRACT_SENT', 'CONTRACT_EXPIRING_12H', 'CONTRACT_SIGNED', 'BOOKING_SUCCEEDED', 'BOOKING_FAILED_OR_CANCELLED', 'REFUND_STARTED', 'REFUND_COMPLETED', 'REFUND_FAILED', 'ORDER_EXCEPTION', 'ADMIN_CONTRACT_CONFIRMATION_REQUIRED'])
const eventLabels: Record<string, string> = { PAYMENT_SUCCEEDED: '支付成功', PAYMENT_FAILED: '支付失败', PAYMENT_EXPIRING_3H: '支付剩余 3 小时', CONTRACT_SENT: '合同已发送', CONTRACT_EXPIRING_12H: '签约剩余 12 小时', CONTRACT_SIGNED: '合同已签署', BOOKING_SUCCEEDED: '预订成功', BOOKING_FAILED_OR_CANCELLED: '订单取消/失败', REFUND_STARTED: '退款已发起', REFUND_COMPLETED: '退款已完成', REFUND_FAILED: '退款失败', ORDER_EXCEPTION: '订单异常', ADMIN_CONTRACT_CONFIRMATION_REQUIRED: '管理员合同确认提醒' }
const formatTime = (value: string) => new Date(value).toLocaleString('zh-CN')
const tagType = (status: string) => status === 'sent' ? 'success' : status === 'failed' ? 'danger' : 'info'
function errorMessage(error: unknown, fallback: string): string {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = error.response
    if (typeof response === 'object' && response !== null && 'data' in response) {
      const data = response.data
      if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string') return data.detail
    }
  }
  return error instanceof Error ? error.message : fallback
}
async function dispatch() { if (!bookingId.value) return; loading.value = true; try { const response = await adminService.dispatchNotificationSimulation({ booking_id: bookingId.value, event_type: eventType.value, outcome: outcome.value }); results.value = response.results; ElMessage.success('通知模拟已完成') } catch (error: unknown) { ElMessage.error(errorMessage(error, '通知模拟失败')) } finally { loading.value = false } }
onMounted(async () => {
  try { events.value = (await adminService.getNotificationSimulationEvents()).items } catch { /* 使用内置事件列表 */ }
  try { orders.value = (await adminService.getNotificationSimulationOrders()).items } catch (error: unknown) { ElMessage.error(errorMessage(error, '订单列表加载失败')) }
})
</script>

<style scoped>
.simulation-page{width:min(1080px,calc(100% - 32px));margin:0 auto;padding:28px 0 48px}.panel{margin-top:18px}.wide{width:min(420px,100%)}.hint{margin:14px 0 0;color:#667085;font-size:13px}@media(max-width:768px){.simulation-page{width:calc(100% - 24px);padding-top:16px}}
</style>
