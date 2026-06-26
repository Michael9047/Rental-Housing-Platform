<template>
  <div class="profile-page">

    <!-- User Info Card -->
    <el-card shadow="never" class="user-card">
      <div class="user-info">
        <el-avatar :size="56" :icon="UserFilled" />
        <div class="user-detail">
          <div class="user-name-row">
            <span class="user-name">{{ user?.username || '未登录' }}</span>
            <el-tag :type="roleTagType" size="small">{{ roleLabel }}</el-tag>
            <el-tag v-if="user?.wechat_openid" type="success" size="small" effect="plain">已绑定微信</el-tag>
          </div>
          <div class="user-contact">
            <span v-if="user?.email">📧 {{ user.email }}</span>
            <span v-if="user?.phone">📱 {{ maskPhone(user.phone) }}</span>
            <span>📅 注册于 {{ formatDate(user?.created_at || '') }}</span>
          </div>
        </div>
        <el-button type="primary" round @click="router.push('/profile/edit')">编辑资料</el-button>
      </div>
    </el-card>

    <!-- Stats Cards -->
    <div class="stats-row">
      <div class="stat-card" @click="activeTab = 'bookings'">
        <span class="stat-icon">📋</span>
        <div class="stat-info">
          <div class="stat-num">{{ bookings.length }}</div>
          <div class="stat-label">我的预订</div>
        </div>
      </div>
      <div class="stat-card" @click="activeTab = 'contracts'">
        <span class="stat-icon">💳</span>
        <div class="stat-info">
          <div class="stat-num">{{ pendingPayments }}</div>
          <div class="stat-label">支付中心</div>
        </div>
      </div>
      <div class="stat-card" @click="activeTab = 'favorites'">
        <span class="stat-icon">⭐</span>
        <div class="stat-info">
          <div class="stat-num">{{ favorites.length }}</div>
          <div class="stat-label">收藏房源</div>
        </div>
      </div>
    </div>

    <!-- Tab Navigation -->
    <el-card shadow="never" class="tabs-card">
      <el-tabs v-model="activeTab" class="profile-tabs">
        <el-tab-pane label="📋 我的预订" name="bookings">
          <div v-loading="bookingsLoading">
            <el-empty v-if="bookings.length === 0" description="暂无任何预订记录">
              <el-button type="primary" @click="$router.push('/')">去找房</el-button>
            </el-empty>

            <el-table v-else :data="bookings" stripe class="data-table">
              <el-table-column label="房源" min-width="200">
                <template #default="{ row }">
                  <div class="table-property">
                    <span class="table-prop-name" @click="$router.push(`/property/${row.property_id}`)">
                      房源 #{{ row.property_id }}
                    </span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="预约时间" width="140">
                <template #default="{ row }">{{ row.scheduled_date || '待定' }}</template>
              </el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="bookingStatusTag(row.status)" size="small">
                    {{ bookingStatusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="220">
                <template #default="{ row }">
                  <el-button v-if="row.status === 'pending'" size="small" type="danger" text @click="cancelBooking(row)">
                    取消预订
                  </el-button>
                  <el-button v-if="row.status === 'pending' || row.status === 'approved'" size="small" type="primary" @click="goConfirmRent(row)">
                    确认租房
                  </el-button>
                  <el-button v-if="row.status === 'completed'" size="small" text type="primary" @click="$router.push(`/property/${row.property_id}`)">
                    查看房源
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <el-tab-pane label="💳 支付中心" name="contracts">
          <el-empty v-if="contracts.length === 0" description="暂无支付记录，完成押金支付后自动生成电子合同">
            <el-button type="primary" @click="$router.push('/search')">去选房</el-button>
          </el-empty>

          <el-table v-else :data="contracts" stripe class="data-table">
            <el-table-column label="订单编号" width="100">
              <template #default="{ row }">#{{ row.bookingId }}</template>
            </el-table-column>
            <el-table-column label="房源" min-width="160">
              <template #default="{ row }">
                <span class="table-prop-name" @click="$router.push(`/property/${row.propertyId}`)">
                  {{ row.propertyTitle }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="押金金额" width="120">
              <template #default="{ row }">¥{{ row.depositAmount }}</template>
            </el-table-column>
            <el-table-column label="支付时间" width="160">
              <template #default="{ row }">{{ row.paidAt || row.updatedAt }}</template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="row.isPaid ? 'success' : 'warning'" size="small">
                  {{ row.isPaid ? '✓ 已支付押金' : '待支付' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="viewContract(row)">查看合同</el-button>
                <el-button size="small" text type="primary" @click="downloadContract(row)">下载</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="⭐ 收藏房源" name="favorites">
          <el-empty v-if="favorites.length === 0" description="暂无收藏房源，浏览房源页可点击收藏心仪公寓">
            <el-button type="primary" @click="$router.push('/search')">去浏览房源</el-button>
          </el-empty>

          <div v-else class="fav-grid">
            <PropertyCard
              v-for="p in favorites"
              :key="p.id"
              :property="p"
              :show-quick-book="true"
              @book="openBookingDialog"
            />
          </div>
        </el-tab-pane>

      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UserFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { usePropertyStore } from '@/stores/property'
import { bookingService } from '@/services/booking'
import { contractService } from '@/services/contract'
import { propertyService } from '@/services/property'
import { storeToRefs } from 'pinia'
import PropertyCard from '@/components/PropertyCard.vue'
import type { Booking } from '@/types/booking'
import type { UserRole } from '@/types/user'
import type { Property } from '@/types/property'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const propertyStore = usePropertyStore()
const { user } = storeToRefs(authStore)

const activeTab = ref((route.query.tab as string) || 'bookings')
const bookings = ref<Booking[]>([])
const bookingsLoading = ref(false)
const contracts = ref<any[]>([])
const contractsLoading = ref(false)

// Load paid bookings as payment records
async function fetchContracts() {
  contractsLoading.value = true
  try {
    const bookingList = await bookingService.list()
    const paidList: any[] = []
    for (const b of bookingList) {
      // Show bookings that have paid deposit
      const isPaid = b.deposit_status === 'paid' || b.deposit_status === 'confirmed'
      if (isPaid || b.status === 'completed') {
        paidList.push({
          id: `HT${String(b.id).padStart(8, '0')}`,
          bookingId: b.id,
          propertyId: b.property_id,
          propertyTitle: `房源 #${b.property_id}`,
          depositAmount: b.deposit_amount || 0,
          paidAt: b.updated_at ? new Date(b.updated_at).toLocaleDateString('zh-CN') : '',
          updatedAt: b.updated_at ? new Date(b.updated_at).toLocaleDateString('zh-CN') : '',
          startDate: b.scheduled_date || '待定',
          endDate: '待签署后确认',
          monthlyRent: b.deposit_amount || 0,
          currency: '¥',
          isPaid: isPaid,
          status: b.status === 'completed' ? '已签署' : '已支付押金',
        })
      }
    }
    contracts.value = paidList
  } catch {
    contracts.value = []
  } finally {
    contractsLoading.value = false
  }
}

function viewContract(row: any) {
  router.push({ path: `/contract/${row.bookingId}` })
}

async function downloadContract(row: any) {
  try {
    await contractService.download(row.id)
    ElMessage.success(`合同 ${row.id} 下载中...`)
  } catch {
    ElMessage.info(`合同 ${row.id} 下载（需后端合同数据）`)
  }
}
const favorites = ref<Property[]>([])

const pendingPayments = computed(() =>
  bookings.value.filter((b) =>
    b.status !== 'cancelled' && b.status !== 'rejected' && b.deposit_status !== 'paid' && b.deposit_status !== 'confirmed'
  ).length
)

const roleLabels: Record<UserRole, string> = { tenant: '租客', landlord: '房东', admin: '管理员' }
const roleLabel = computed(() => roleLabels[user.value?.role || 'tenant'])
const roleTagType = computed(() => {
  if (user.value?.role === 'admin') return 'danger'
  if (user.value?.role === 'landlord') return 'warning'
  return 'info'
})

// Booking helpers
const bookingStatusLabels: Record<string, string> = {
  pending: '待确认', approved: '已确认', rejected: '已拒绝',
  cancelled: '已取消', completed: '已完成',
}
const bookingStatusTags: Record<string, string> = {
  pending: 'warning', approved: 'success', rejected: 'danger',
  cancelled: 'info', completed: '',
}
function bookingStatusLabel(s: string) { return bookingStatusLabels[s] || s }
function bookingStatusTag(s: string) { return bookingStatusTags[s] || 'info' }

// Bookings
async function fetchBookings() {
  bookingsLoading.value = true
  try {
    bookings.value = await bookingService.list()
  } catch { bookings.value = [] }
  finally { bookingsLoading.value = false }
}

async function cancelBooking(booking: Booking) {
  try {
    await ElMessageBox.confirm('确定取消此预约？', '确认取消', {
      confirmButtonText: '确定', cancelButtonText: '返回', type: 'warning',
    })
    await bookingService.cancel(booking.id)
    ElMessage.success('预约已取消')
    fetchBookings()
  } catch { /* cancelled */ }
}

function goConfirmRent(booking: Booking) {
  router.push({ path: `/booking/payment/${booking.id}` })
}

function openBookingDialog(p: Property) {
  // Could show BookingDateDialog here — for simplicity navigate directly
  window.open(`/booking/confirm?property_id=${p.id}`, '_self')
}

// Utils
function maskPhone(phone: string | null): string {
  if (!phone) return '未设置'
  if (phone.length < 11) return phone
  return phone.slice(0, 3) + '****' + phone.slice(-4)
}

function formatDate(d: string): string {
  if (!d) return ''
  return new Date(d).toLocaleDateString('zh-CN')
}

onMounted(async () => {
  await authStore.fetchCurrentUser()
  fetchBookings()
  fetchContracts()
  // Load favorites (use same property list for now — in production use actual favorites API)
  try {
    favorites.value = await propertyService.list({ limit: 6 })
  } catch { favorites.value = [] }
})
</script>

<style scoped>
.profile-page {
  max-width: 1000px;
  margin: 0 auto;
}

.profile-page h2 {
  font-size: 22px;
  color: var(--text-primary);
  margin-bottom: 20px;
}

/* ── User Card ─────────────────────── */

.user-card {
  margin-bottom: 20px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 20px;
}

.user-detail {
  flex: 1;
}

.user-name-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.user-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.user-contact {
  display: flex;
  gap: 20px;
  font-size: 13px;
  color: var(--text-muted);
}

/* ── Stats ─────────────────────────── */

.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  background: var(--bg-white);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  padding: 20px 16px;
  display: flex;
  align-items: center;
  gap: 14px;
  cursor: pointer;
  transition: all 0.2s;
  box-sizing: border-box;
  min-height: 80px;
  width: 100%;
}

.stat-card:hover {
  border-color: var(--primary);
  box-shadow: var(--shadow);
  transform: translateY(-2px);
}

.last-row {
  margin-bottom: 0;
}

.stat-icon {
  font-size: 28px;
}

.stat-num {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: 13px;
  color: var(--text-muted);
}

/* ── Tabs ──────────────────────────── */

.tabs-card {
  border-radius: var(--radius) !important;
}

.profile-tabs :deep(.el-tabs__item) {
  font-size: 15px;
  font-weight: 500;
}

.data-table {
  width: 100%;
}

.table-property {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-prop-name {
  color: var(--primary);
  cursor: pointer;
  font-weight: 500;
}

.table-prop-name:hover {
  text-decoration: underline;
}

.fav-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

</style>
