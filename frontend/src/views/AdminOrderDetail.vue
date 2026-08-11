<template>
  <main v-loading="loading" class="page-container">
    <el-page-header content="订单详情" @back="router.push({ name: 'admin-orders' })" />
    <el-result v-if="error" icon="error" :title="error" sub-title="请返回订单管理列表后重试。" />

    <template v-else-if="order">
      <section class="detail-header">
        <div><h2>订单 #{{ order.id }}</h2><p>{{ order.institute_name }} · {{ order.unit_type_name }}</p></div>
        <status-tag :status="order.status" />
      </section>

      <el-card shadow="never" header="订单与租客信息">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="订单编号">#{{ order.id }}</el-descriptions-item>
          <el-descriptions-item label="订单创建时间">{{ formatDate(order.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="完成/取消时间">{{ formatDate(order.finalized_at) }}</el-descriptions-item>
          <el-descriptions-item label="取消原因">{{ order.status_reason || '-' }}</el-descriptions-item>
          <el-descriptions-item label="租客姓名">{{ order.tenant_name }}</el-descriptions-item>
          <el-descriptions-item label="电话">{{ order.phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="公寓">{{ order.institute_name }}</el-descriptions-item>
          <el-descriptions-item label="房型/房号">{{ order.unit_type_name }}{{ order.room_number ? ` / ${order.room_number}` : '' }}</el-descriptions-item>
          <el-descriptions-item label="入住日期">{{ order.move_in_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="租期">{{ order.lease_months ? `${order.lease_months}个月` : '-' }}</el-descriptions-item>
          <el-descriptions-item label="租约开始日期">{{ order.contract_start || '-' }}</el-descriptions-item>
          <el-descriptions-item label="租约结束日期">{{ order.contract_end || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never" class="detail-card" header="房源费用参考">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="房源月租">{{ formatPropertyMoney(order.monthly_rent) }}</el-descriptions-item>
          <el-descriptions-item label="参考租金总额">{{ formatPropertyMoney(order.total_rent) }}</el-descriptions-item>
          <el-descriptions-item label="房源押金">{{ formatPropertyMoney(order.property_deposit) }}</el-descriptions-item>
          <el-descriptions-item label="房源计价币种">{{ order.property_currency || '-' }}</el-descriptions-item>
        </el-descriptions>
        <p class="hint">以上为房源费用参考，不是平台本次应收金额。</p>
      </el-card>

      <el-card shadow="never" class="detail-card" header="平台预订金">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="实际已支付金额">{{ formatMoney(order.booking_deposit_minor, order.payment_currency) }}</el-descriptions-item>
          <el-descriptions-item label="支付状态">{{ order.payment_status || '-' }}</el-descriptions-item>
          <el-descriptions-item label="支付时间">{{ formatDate(order.paid_at) }}</el-descriptions-item>
          <el-descriptions-item label="支付渠道">{{ order.payment_method || '-' }}</el-descriptions-item>
          <el-descriptions-item label="退款状态">{{ order.refund_status || '不适用' }}</el-descriptions-item>
          <el-descriptions-item label="退款时间">{{ formatDate(order.refund_at) }}</el-descriptions-item>
          <el-descriptions-item label="退款参考编号">{{ order.refund_reference || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never" class="detail-card" header="合同信息">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="合同状态">{{ order.contract_status || '-' }}</el-descriptions-item>
          <el-descriptions-item label="合同模板">{{ order.contract_template_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="模板版本">{{ order.contract_template_version || '-' }}</el-descriptions-item>
          <el-descriptions-item label="合同生成时间">{{ formatDate(order.contract_generated_at) }}</el-descriptions-item>
          <el-descriptions-item label="租客签署时间">{{ formatDate(order.contract_signed_at) }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </template>
  </main>
</template>

<script setup lang="ts">
import { defineComponent, h, onMounted, ref } from 'vue'
import { ElTag } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'

const StatusTag = defineComponent({
  props: { status: { type: String, required: true } },
  setup(props) {
    return () => h(ElTag, { type: props.status === 'completed' ? 'success' : 'info' }, () => (
      props.status === 'completed' ? '预订成功' : '已取消'
    ))
  },
})

const route = useRoute()
const router = useRouter()
const order = ref<any>()
const loading = ref(true)
const error = ref('')

function formatMoney(amountMinor: number | null, currency = 'CNY') {
  if (amountMinor === null || amountMinor === undefined) return '-'
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency, minimumFractionDigits: 2 }).format(amountMinor / 100).replace('¥', 'CNY ')
}

function formatPropertyMoney(amount: number | null) {
  if (amount === null || amount === undefined || !order.value?.property_currency) return '-'
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: order.value.property_currency, minimumFractionDigits: 2 }).format(amount).replace('¥', 'CNY ')
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
}

onMounted(async () => {
  try {
    order.value = (await api.get(`/admin/orders/${route.params.id}`)).data
  } catch (requestError: any) {
    const code = requestError?.response?.status
    error.value = code === 403 ? '无权查看该订单' : code === 404 ? '订单不存在或尚未归档' : '订单详情加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.page-container { padding: 24px; }
.detail-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 24px 0 16px; }
.detail-header h2 { margin: 0; }
.detail-header p { margin: 8px 0 0; color: var(--text-muted); }
.detail-card { margin-top: 16px; }
.hint { margin: 14px 0 0; color: var(--text-muted); line-height: 1.6; }
@media (max-width: 768px) { .page-container { padding: 16px; } :deep(.el-descriptions__body table) { min-width: 0; } }
</style>
