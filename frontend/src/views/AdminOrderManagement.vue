<template>
  <main class="page-container">
    <header class="page-header">
      <div>
        <h2>订单管理</h2>
        <p>查看已完成预订及已取消的订单。</p>
      </div>
      <el-button @click="loadOrders">重新加载</el-button>
    </header>

    <section class="filters" aria-label="订单筛选">
      <el-input
        v-model="keyword"
        clearable
        placeholder="搜索订单号、租客姓名、电话或公寓"
        @keyup.enter="search"
        @clear="search"
      />
      <el-select v-model="status" aria-label="订单状态" @change="search">
        <el-option label="全部" value="all" />
        <el-option label="预订成功" value="completed" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
      <el-button type="primary" @click="search">搜索</el-button>
    </section>

    <el-table
      v-loading="loading"
      :data="orders"
      class="orders-table desktop-table"
      empty-text="暂无已完成或已取消订单"
      @row-click="openOrder"
    >
      <el-table-column label="订单编号" min-width="104">
        <template #default="{ row }">#{{ row.id }}</template>
      </el-table-column>
      <el-table-column prop="tenant_name" label="租客姓名" min-width="100" />
      <el-table-column prop="phone" label="电话" min-width="126">
        <template #default="{ row }">{{ row.phone || '-' }}</template>
      </el-table-column>
      <el-table-column prop="institute_name" label="公寓名称" min-width="150" show-overflow-tooltip />
      <el-table-column prop="unit_type_name" label="房型" min-width="120" show-overflow-tooltip />
      <el-table-column label="预订金" min-width="130" align="right">
        <template #default="{ row }">{{ formatMoney(row.booking_deposit_minor, row.payment_currency) }}</template>
      </el-table-column>
      <el-table-column label="订单状态" min-width="116" align="center">
        <template #default="{ row }"><status-tag :status="row.status" /></template>
      </el-table-column>
      <el-table-column label="完成/取消时间" min-width="176">
        <template #default="{ row }">{{ formatDate(row.finalized_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click.stop="openOrder(row)">查看详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <section v-loading="loading" class="mobile-orders" aria-label="订单列表">
      <el-empty v-if="!orders.length" :description="emptyText" />
      <button
        v-for="order in orders"
        :key="order.id"
        class="order-card"
        type="button"
        @click="openOrder(order)"
      >
        <span class="card-title">#{{ order.id }} · {{ order.tenant_name }}</span>
        <status-tag :status="order.status" />
        <span>{{ order.phone || '-' }}</span>
        <span>{{ order.institute_name }}</span>
        <span>预订金：{{ formatMoney(order.booking_deposit_minor, order.payment_currency) }}</span>
        <span class="detail-link">查看详情</span>
      </button>
    </section>

    <div class="pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadOrders"
      />
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { ElMessage, ElTag } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'

interface AdminOrderRow {
  id: number
  tenant_name: string
  phone: string | null
  institute_name: string
  unit_type_name: string
  booking_deposit_minor: number | null
  payment_currency: string
  status: 'completed' | 'cancelled'
  finalized_at: string | null
}

const StatusTag = defineComponent({
  props: { status: { type: String, required: true } },
  setup(props) {
    return () => h(ElTag, { type: props.status === 'completed' ? 'success' : 'info', effect: 'light' }, () => (
      props.status === 'completed' ? '预订成功' : '已取消'
    ))
  },
})

const router = useRouter()
const route = useRoute()
const orders = ref<AdminOrderRow[]>([])
const loading = ref(false)
const keyword = ref(typeof route.query.keyword === 'string' ? route.query.keyword : '')
const status = ref(typeof route.query.status === 'string' ? route.query.status : 'all')
const page = ref(Number(route.query.page) || 1)
const pageSize = 20
const total = ref(0)
const emptyText = computed(() => (keyword.value || status.value !== 'all'
  ? '未找到符合条件的订单'
  : '暂无已完成或已取消订单'))

function formatMoney(amountMinor: number | null, currency = 'CNY') {
  if (amountMinor === null || amountMinor === undefined) return '-'
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amountMinor / 100).replace('¥', 'CNY ')
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
}

function syncQuery() {
  router.replace({
    query: {
      ...(keyword.value ? { keyword: keyword.value } : {}),
      ...(status.value !== 'all' ? { status: status.value } : {}),
      ...(page.value > 1 ? { page: String(page.value) } : {}),
    },
  })
}

async function loadOrders() {
  loading.value = true
  try {
    const { data } = await api.get('/admin/orders', {
      params: { page: page.value, page_size: pageSize, keyword: keyword.value || undefined, status: status.value },
    })
    orders.value = data.items
    total.value = data.total
    syncQuery()
  } catch (error: any) {
    orders.value = []
    total.value = 0
    ElMessage.error(error?.response?.data?.detail || '订单列表加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  loadOrders()
}

function openOrder(order: AdminOrderRow) {
  router.push({ name: 'admin-order-detail', params: { id: order.id } })
}

onMounted(loadOrders)
</script>

<style scoped>
.page-container { padding: 24px; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.page-header h2 { margin: 0; }
.page-header p { margin: 8px 0 0; color: var(--text-muted); }
.filters { display: flex; gap: 12px; margin: 24px 0 16px; }
.filters .el-input { max-width: 440px; }
.filters .el-select { width: 150px; }
.orders-table { width: 100%; cursor: pointer; }
.pagination { display: flex; justify-content: flex-end; margin-top: 20px; }
.mobile-orders { display: none; }

@media (max-width: 768px) {
  .page-container { padding: 16px; }
  .filters { flex-wrap: wrap; }
  .filters .el-input { width: 100%; max-width: none; }
  .desktop-table { display: none; }
  .mobile-orders { display: grid; gap: 12px; }
  .order-card {
    display: grid; grid-template-columns: 1fr auto; gap: 8px; width: 100%;
    padding: 16px; text-align: left; color: inherit; background: var(--bg-white);
    border: 1px solid var(--border); border-radius: 8px; cursor: pointer;
  }
  .card-title { font-weight: 700; }
  .order-card > span:not(.card-title):not(.detail-link) { grid-column: 1 / -1; color: var(--text-muted); }
  .detail-link { color: var(--primary); font-weight: 600; }
  .pagination { justify-content: center; overflow-x: auto; }
}
</style>
