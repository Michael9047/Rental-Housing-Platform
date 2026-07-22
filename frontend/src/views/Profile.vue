<template>
  <div class="profile-page" v-loading="pageLoading">
    <!-- ===== 头部 ===== -->
    <el-card shadow="never" class="user-card">
      <div class="user-info">
        <el-avatar :size="64" :icon="UserFilled" />
        <div class="user-detail">
          <div class="user-name-row">
            <span class="user-name">{{ user?.username || '未登录' }}</span>
            <el-tag type="info" size="small">租客</el-tag>
            <el-tag v-if="user?.status === 'active'" type="success" size="small">已实名</el-tag>
            <el-tag v-else type="warning" size="small">待认证</el-tag>
          </div>
          <div class="user-contact">
            <span v-if="user?.email">📧 {{ user.email }}</span>
            <span v-if="user?.phone">📱 {{ maskPhone(user.phone) }}</span>
            <span>📅 {{ formatDate(user?.created_at || '') }} 加入</span>
          </div>
        </div>
        <div class="user-actions">
          <el-button type="primary" round @click="router.push('/profile/edit')">编辑资料</el-button>
          <el-button round @click="showVerify = true">实名认证</el-button>
        </div>
      </div>
    </el-card>

    <!-- ===== 统计卡片 ===== -->
    <div class="stats-grid">
      <div class="stat-card" @click="activeTab = 'bookings'">
        <span class="stat-icon">📅</span>
        <div class="stat-info">
          <div class="stat-num">{{ summaryLoading ? '…' : summary?.viewing_appointments ?? '—' }}</div>
          <div class="stat-label">看房预约</div>
        </div>
      </div>
      <div class="stat-card" @click="activeTab = 'bills'">
        <span class="stat-icon">💳</span>
        <div class="stat-info">
          <div class="stat-num">{{ summaryLoading ? '…' : summary?.payable_orders ?? '—' }}</div>
          <div class="stat-label">待支付</div>
        </div>
      </div>
      <div class="stat-card" @click="activeTab = 'contracts'">
        <span class="stat-icon">📄</span>
        <div class="stat-info">
          <div class="stat-num">{{ summaryLoading ? '…' : summary?.signed_contracts ?? '—' }}</div>
          <div class="stat-label">我的合同</div>
        </div>
      </div>
      <div class="stat-card" @click="activeTab = 'favorites'">
        <span class="stat-icon">❤️</span>
        <div class="stat-info">
          <div class="stat-num">{{ summaryLoading ? '…' : summary?.favorites ?? '—' }}</div>
          <div class="stat-label">收藏</div>
        </div>
      </div>
    </div>
    <el-alert v-if="summaryError" type="warning" :closable="false" title="顶部统计暂时无法加载，请稍后重试" class="summary-error" />

    <!-- ===== Tab 主体 ===== -->
    <el-card shadow="never" class="tabs-card">
      <el-tabs v-model="activeTab" class="profile-tabs" type="border-card">

        <!-- Tab1: 看房预约 -->
        <el-tab-pane label="📅 看房预约" name="bookings">
          <div class="tab-toolbar">
            <el-radio-group v-model="bookingFilter" size="small">
              <el-radio-button value="all">全部 ({{ viewingBookings.length }})</el-radio-button>
              <el-radio-button value="pending">待房东确认</el-radio-button>
              <el-radio-button value="approved">已同意</el-radio-button>
              <el-radio-button value="cancelled">已取消</el-radio-button>
              <el-radio-button value="completed">已完成</el-radio-button>
            </el-radio-group>
          </div>
          <el-empty v-if="filteredBookings.length === 0" description="还没有预约，去看看心仪的房源吧">
            <el-button type="primary" @click="$router.push('/search')">去找房</el-button>
          </el-empty>
          <el-table v-else :data="filteredBookings" stripe>
            <el-table-column label="房源" min-width="170">
              <template #default="{ row }">
                <span class="link-text" @click="$router.push(`/property/${row.property_id}`)">房源 #{{ row.property_id }}</span>
              </template>
            </el-table-column>
            <el-table-column label="看房时间" width="120">
              <template #default="{ row }">{{ row.scheduled_date || '待定' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="bookingTag(row.status)" size="small">{{ bookingLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button v-if="row.status === 'pending'" size="small" type="danger" text @click="cancelBooking(row)">取消预约</el-button>
                <el-button v-if="row.status === 'pending' || row.status === 'approved'" size="small" type="primary" @click="goPay(row)">确认租房</el-button>
                <el-button v-if="row.status === 'completed'" size="small" text type="primary" @click="$router.push(`/property/${row.property_id}`)">再看一次</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Tab2: 我的合同 -->
        <el-tab-pane label="📄 我的合同" name="contracts">
          <p class="contract-hint">签署完成的合同将在此显示；支付成功后合同及预订正式生效。</p>
          <div class="tab-toolbar">
            <el-radio-group v-model="contractFilter" size="small">
              <el-radio-button value="pending_effective">待生效</el-radio-button>
              <el-radio-button value="effective">已生效</el-radio-button>
              <el-radio-button value="expiring_soon">临期失效</el-radio-button>
              <el-radio-button value="invalid">已失效</el-radio-button>
            </el-radio-group>
          </div>
          <el-alert v-if="contractsError" type="error" :closable="false" title="合同列表加载失败" show-icon><template #default><el-button text @click="fetchAll">重试</el-button></template></el-alert>
          <el-empty v-else-if="filteredContracts.length === 0" description="当前分类暂无合同" />
          <div v-else class="contract-list">
            <el-card v-for="row in filteredContracts" :key="row.agreement_id" shadow="never" class="contract-card">
              <div class="contract-card-grid">
                <img v-if="row.property_image_url" :src="row.property_image_url" :alt="row.property_name" class="contract-property-image" />
                <div v-else class="contract-property-image placeholder">暂无图片</div>
                <div class="contract-main">
                  <div class="contract-title"><strong>{{ row.property_name }}</strong><el-tag>{{ row.category_label }}</el-tag></div>
                  <p>{{ row.property_address }}</p>
                  <p>合同：{{ row.agreement_number }} · 订单：{{ row.order_id }}</p>
                  <p>签署：{{ contractDateTime(row.signed_at) }} · 租期：{{ row.lease_start_date || '—' }} 至 {{ row.lease_end_date || '—' }}（{{ row.lease_months || '—' }}个月）</p>
                  <div class="contract-tags"><el-tag v-for="label in row.status_labels" :key="label" size="small">{{ label }}</el-tag></div>
                  <el-alert v-if="row.invalid_reason" type="warning" :closable="false" :title="row.invalid_reason" />
                  <p v-if="row.settlement_currency">实际支付金额：{{ contractMoney(row.settlement_amount_minor, row.settlement_currency) }}</p>
                  <p v-if="row.remaining_payment_seconds !== null">剩余支付时间：{{ duration(row.remaining_payment_seconds) }}</p>
                  <p v-if="row.remaining_contract_days !== null">剩余合同天数：{{ row.remaining_contract_days }}天</p>
                </div>
              </div>
              <div class="contract-actions">
                <el-button type="primary" text @click="router.push(`/my-contracts/${row.agreement_id}`)">查看合同</el-button>
                <el-button text :disabled="!row.signed_pdf_available" @click="downloadContract(row)">下载合同</el-button>
                <el-button text @click="router.push(`/booking/order/${row.booking_id}/payment-status`)">查看订单</el-button>
                <el-button text @click="router.push(`/property/${row.property_id}`)">查看房源</el-button>
                <el-button v-if="row.can_pay" type="primary" @click="router.push(`/booking/payment/${row.booking_id}/deposit`)">继续支付</el-button>
              </div>
            </el-card>
          </div>
        </el-tab-pane>

        <!-- Tab3: 收藏 -->
        <el-tab-pane label="❤️ 收藏" name="favorites">
          <el-empty v-if="favorites.length === 0" description="还没有收藏，遇到喜欢的房源点个❤️收藏起来吧">
            <el-button type="primary" @click="$router.push('/search')">去逛逛</el-button>
          </el-empty>
          <div v-else class="fav-grid">
            <PropertyCard v-for="p in favorites" :key="p.id" :property="p" :show-quick-book="true" @book="openBookingDialog" />
          </div>
        </el-tab-pane>

        <!-- Tab4: 我的账单 / 我的订单 -->
        <el-tab-pane label="💳 我的账单 / 订单" name="bills">
          <div class="tab-toolbar">
            <el-radio-group v-model="billTab" size="small">
              <el-radio-button value="pending">待处理</el-radio-button>
              <el-radio-button value="successful">已成功</el-radio-button>
            </el-radio-group>
          </div>
          <el-alert v-if="ordersError" type="error" :closable="false" title="订单列表加载失败" show-icon><template #default><el-button text @click="fetchAll">重试</el-button></template></el-alert>
          <el-empty v-else-if="filteredOrders.length === 0" description="当前分类暂无订单" />
          <div v-else class="order-list">
            <el-card v-for="order in filteredOrders" :key="order.booking_id" shadow="never" class="order-card">
              <div class="order-card-grid">
                <img v-if="order.property_image_url" :src="order.property_image_url" :alt="order.property_name" class="order-image" />
                <div v-else class="order-image placeholder">暂无图片</div>
                <div class="order-main">
                  <div class="order-title"><strong>{{ order.property_name }}</strong><el-tag>{{ order.status_label }}</el-tag></div>
                  <p>{{ order.property_city }} · {{ order.property_address }}</p>
                  <p>订单：{{ order.order_id }}</p>
                  <p>入住：{{ order.lease_start_date || '—' }} 至 {{ order.lease_end_date || '—' }} · {{ order.lease_months || '—' }}个月</p>
                  <p>当前应付：{{ contractMoney(order.settlement_amount_minor, order.settlement_currency) }} · 人民币：{{ contractMoney(order.cny_reference_amount_minor, 'CNY') }}</p>
                  <p>当地货币：{{ contractMoney(order.property_amount_minor, order.property_currency) }}</p>
                  <div class="order-tags"><el-tag size="small">订单：{{ order.status_label }}</el-tag><el-tag size="small">支付：{{ order.status_label }}</el-tag><el-tag size="small" :type="order.booking_status === 'confirmed' ? 'success' : 'info'">预订：{{ order.booking_status === 'confirmed' ? '成功' : '未成功' }}</el-tag></div>
                  <p>创建：{{ contractDateTime(order.created_at) }} · 截止：{{ contractDateTime(order.expires_at) }}</p>
                  <p v-if="remainingSeconds(order) > 0 && order.booking_status !== 'confirmed'">倒计时：{{ duration(remainingSeconds(order)) }}</p>
                  <el-alert v-if="order.failure_reason" :closable="false" type="warning" :title="order.failure_reason" />
                </div>
              </div>
              <div class="contract-actions">
                <el-button text type="primary" @click="router.push(`/my-orders/${order.booking_id}`)">{{ order.booking_status === 'confirmed' ? '查看预订' : '查看详情' }}</el-button>
                <el-button text @click="router.push(`/property/${order.property_id}`)">查看房源</el-button>
                <el-button v-if="order.payment_status === 'payment_processing'" text @click="refreshOrders">刷新状态</el-button>
                <el-button v-if="['payment_expired','cancelled'].includes(order.payment_status)" @click="router.push(`/booking/${order.property_id}/move-in-date`)">重新预订该房源</el-button>
                <el-button v-if="order.booking_status === 'confirmed'" text @click="router.push(`/my-contracts/${order.agreement_id}`)">查看合同</el-button>
                <el-button v-if="order.can_pay" type="primary" :loading="payingOrderId === order.booking_id" @click="enterPayment(order)">{{ order.payment_action_label }}</el-button>
              </div>
            </el-card>
          </div>
        </el-tab-pane>

        <!-- Tab5: 报修 -->
        <el-tab-pane label="🔧 报修" name="repairs">
          <div class="tab-toolbar">
            <el-button type="primary" size="small" @click="showNewRepair = true">我要报修</el-button>
          </div>
          <el-empty v-if="repairs.length === 0" description="没有报修记录，一切正常 👍" />
          <el-table v-else :data="repairs" stripe>
            <el-table-column label="房源" min-width="140">
              <template #default="{ row }">{{ row.property_title || `房源#${row.property_id}` }}</template>
            </el-table-column>
            <el-table-column label="问题" min-width="140">
              <template #default="{ row }">
                <el-tag size="small" type="warning" style="margin-right:6px">{{ issueTypeLabel(row.issue_type) }}</el-tag>
                <span>{{ row.description?.slice(0, 20) }}{{ row.description?.length > 20 ? '...' : '' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="提交时间" width="110">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="repairTag(row.status)" size="small">{{ repairStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="viewRepair(row)">查看详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Tab6: 消息 -->
        <el-tab-pane label="🔔 消息" name="messages">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-card shadow="never" class="msg-card">
                <template #header><span>💬 房东消息</span></template>
                <div v-for="m in chats" :key="m.id" class="msg-item">
                  <div class="msg-header">
                    <strong>{{ m.from }}</strong>
                    <span class="msg-time">{{ m.time }}</span>
                    <el-tag v-if="!m.read" size="small" type="danger">新</el-tag>
                  </div>
                  <p class="msg-text">{{ m.text }}</p>
                </div>
                <el-empty v-if="chats.length === 0" description="暂无消息" />
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="never" class="msg-card">
                <template #header><span>🔔 系统通知</span></template>
                <div v-for="n in notices" :key="n.id" class="msg-item">
                  <span class="msg-time">{{ n.time }}</span>
                  <p class="msg-text">{{ n.text }}</p>
                </div>
                <el-empty v-if="notices.length === 0" description="暂无通知" />
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>

        <!-- Tab7: 设置 -->
        <el-tab-pane label="⚙️ 设置" name="settings">
          <el-row :gutter="24">
            <el-col :span="12">
              <el-card shadow="never" class="setting-card">
                <template #header>🔐 账号安全</template>
                <el-form label-width="80px" size="small">
                  <el-form-item label="手机号"><el-input :model-value="user?.phone || ''" /></el-form-item>
                  <el-form-item label="密码"><el-input type="password" model-value="********" /></el-form-item>
                  <el-form-item label="微信">
                    <el-tag :type="user?.wechat_openid ? 'success' : 'info'" size="small">{{ user?.wechat_openid ? '已绑定' : '未绑定' }}</el-tag>
                    <el-button size="small" text type="primary" @click="bindWechat">{{ user?.wechat_openid ? '换绑' : '绑定' }}</el-button>
                  </el-form-item>
                  <el-form-item><el-button type="primary" size="small">保存修改</el-button></el-form-item>
                </el-form>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="never" class="setting-card">
                <template #header>🆔 实名认证</template>
                <p style="color:var(--text-secondary);font-size:13px;margin-bottom:10px">租房签约前需要完成实名认证</p>
                <el-upload action="#" :auto-upload="false" :show-file-list="false">
                  <el-button type="primary" size="small">📷 上传身份证</el-button>
                </el-upload>
              </el-card>
            </el-col>
          </el-row>
          <el-row :gutter="24" style="margin-top:16px">
            <el-col :span="12">
              <el-card shadow="never" class="setting-card">
                <template #header>🔔 通知设置</template>
                <div class="notif-switches">
                  <el-switch v-model="notifSite" active-text="App内通知" size="small" />
                  <el-switch v-model="notifSms" active-text="短信提醒" size="small" />
                </div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="never" class="setting-card">
                <template #header>❓ 帮助</template>
                <div class="help-links">
                  <el-button text @click="ElMessage.info('在线客服接入中')">💬 联系客服</el-button>
                  <el-button text @click="ElMessage.info('常见问题')">📖 常见问题</el-button>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>

      </el-tabs>
    </el-card>

    <!-- 报修弹窗 -->
    <el-dialog v-model="showNewRepair" title="我要报修" width="440px">
      <el-form label-width="70px">
        <el-form-item label="房源">
          <el-select v-model="repairForm.property_id" style="width:100%" placeholder="选择需要维修的房源">
            <el-option v-for="b in bookings" :key="b.id" :label="`房源 #${b.property_id}`" :value="b.property_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="哪里坏了">
          <el-select v-model="repairForm.issue_type" style="width:100%" placeholder="选择问题类型">
            <el-option v-for="(label, key) in ISSUE_TYPE_LABELS" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述一下">
          <el-input v-model="repairForm.description" type="textarea" :rows="3" placeholder="简单说说哪里出了问题..." />
        </el-form-item>
        <el-form-item label="预约时间">
          <el-input v-model="repairForm.scheduled_time" placeholder="例如：7月10日 上午（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNewRepair = false">算了</el-button>
        <el-button type="primary" :loading="showSubmitRepair" @click="submitRepair">提交</el-button>
      </template>
    </el-dialog>

    <!-- 实名认证弹窗 -->
    <el-dialog v-model="showVerify" title="实名认证" width="400px">
      <p style="color:var(--text-secondary);font-size:14px;margin-bottom:16px">完成实名认证后才能签署租房合同哦</p>
      <el-form label-width="80px">
        <el-form-item label="姓名"><el-input placeholder="身份证上的姓名" /></el-form-item>
        <el-form-item label="身份证号"><el-input placeholder="18位号码" /></el-form-item>
        <el-form-item label="证件照片"><el-upload action="#" :auto-upload="false"><el-button type="primary" size="small">📷 拍照或上传</el-button></el-upload></el-form-item>
      </el-form>
      <template #footer><el-button @click="showVerify = false">取消</el-button><el-button type="primary" @click="showVerify = false">提交认证</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UserFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { bookingService } from '@/services/booking'
import { contractService } from '@/services/contract'
import type { TenantContractItem } from '@/services/contract'
import { paymentService, type TenantOrderItem } from '@/services/payment'
import { remainingPaymentSeconds } from '@/utils/orderPresentation'
import { filterViewingAppointments } from '@/utils/profileSummary'
import { profileService, type DashboardSummary } from '@/services/profile'
import { clearStaleProfileSelections } from '@/utils/profileSelection'
import { propertyService } from '@/services/property'
import { repairService } from '@/services/repair'
import { storeToRefs } from 'pinia'
import PropertyCard from '@/components/PropertyCard.vue'
import { favoriteService } from '@/services/favorite'
import type { Booking } from '@/types/booking'
import type { Property } from '@/types/property'
import type { RepairRead, RepairIssueType } from '@/types/repair'
import { ISSUE_TYPE_LABELS, REPAIR_STATUS_LABELS, REPAIR_STATUS_TAGS } from '@/types/repair'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { user } = storeToRefs(authStore)

const activeTab = ref((route.query.tab as string) || 'bookings')
const pageLoading = ref(false)
const showVerify = ref(false)
const showNewRepair = ref(false)
const bookingFilter = ref('all')
const contractFilter = ref('pending_effective')
const billTab = ref('pending')

const bookings = ref<Booking[]>([])
const contracts = ref<TenantContractItem[]>([])
const orders = ref<TenantOrderItem[]>([])
const payingOrderId = ref<number | null>(null)
const orderNow = ref(Date.now())
const summary = ref<DashboardSummary | null>(null)
const summaryLoading = ref(true)
const summaryError = ref(false)
const contractsError = ref(false)
const ordersError = ref(false)
let orderTimer = 0
const favorites = ref<Property[]>([])
const repairs = ref<RepairRead[]>([])
const repairForm = ref({ property_id: 0, issue_type: 'other' as RepairIssueType, description: '', scheduled_time: '' })
const showSubmitRepair = ref(false)
const chats = ref([
  { id: 1, from: '张房东', time: '30分钟前', text: '明天下午2点可以看房，到了联系我', read: false },
  { id: 2, from: '李管家', time: '昨天', text: '房子还在的，随时欢迎来看', read: true },
])
const notices = ref([
  { id: 1, time: '今天 10:30', text: '✅ 预约通过啦 — 明天14:00看房，别迟到哦' },
  { id: 2, time: '昨天 18:00', text: '💳 押金已到账，电子合同已生成' },
])

const notifSite = ref(true)
const notifSms = ref(true)

// ── Computed ──
const bookingLabel = (s: string) => ({ pending: '待房东确认', approved: '已同意', rejected: '已拒绝', cancelled: '已取消', completed: '已完成' }[s] || s)
const bookingTag = (s: string) => ({ pending: 'warning', approved: 'success', rejected: 'danger', cancelled: 'info', completed: '' }[s] || 'info') as 'warning'|'success'|'danger'|'info'|''
const repairTag = (s: string) => ((REPAIR_STATUS_TAGS as Record<string, string>)[s] || 'info') as 'danger'|'warning'|'success'|'info'|''
const issueTypeLabel = (t: string) => (ISSUE_TYPE_LABELS as Record<string, string>)[t] || t
const repairStatusLabel = (s: string) => ((REPAIR_STATUS_LABELS as Record<string, string>)[s] || s)

const viewingBookings = computed(() => {
  return filterViewingAppointments(bookings.value, orders.value)
})

const filteredBookings = computed(() => {
  if (bookingFilter.value === 'all') return viewingBookings.value
  return viewingBookings.value.filter(b => b.status === bookingFilter.value)
})

const filteredContracts = computed(() => {
  return contracts.value.filter(c => c.category === contractFilter.value)
})

const successfulOrderStatuses = new Set(['paid'])
const filteredOrders = computed(() => orders.value.filter(order => billTab.value === 'successful'
  ? order.booking_status === 'confirmed' && successfulOrderStatuses.has(order.payment_status)
  : order.booking_status !== 'confirmed'))

// ── Actions ──
async function fetchAll() {
  pageLoading.value = true
  summaryLoading.value=true
  const [summaryResult,bookingsResult,contractsResult,ordersResult,favoritesResult,repairsResult]=await Promise.allSettled([
    profileService.getSummary(),bookingService.list(),contractService.listMine(),paymentService.listMyOrders(),favoriteService.list(),repairService.list(),
  ])
  if(summaryResult.status==='fulfilled'){summary.value=summaryResult.value;summaryError.value=false}else{summary.value=null;summaryError.value=true}
  summaryLoading.value=false
  if(bookingsResult.status==='fulfilled')bookings.value=bookingsResult.value
  if(contractsResult.status==='fulfilled'){contracts.value=contractsResult.value;contractsError.value=false}else{contractsError.value=true}
  if(ordersResult.status==='fulfilled'){orders.value=ordersResult.value;ordersError.value=false}else{ordersError.value=true}
  if(repairsResult.status==='fulfilled')repairs.value=repairsResult.value
  if(favoritesResult.status==='fulfilled'){
    const favItems = favoritesResult.value
    const ids = favItems.map((f) => f.property_id)
    if (ids.length > 0) {
      const results = await Promise.allSettled(ids.map((id) => propertyService.getById(id)))
      favorites.value = results
        .filter((r): r is PromiseFulfilledResult<Property> => r.status === 'fulfilled')
        .map((r) => r.value)
    } else {
      favorites.value = []
    }
  }
  pageLoading.value = false
}
async function cancelBooking(b: Booking) {
  try {
    await ElMessageBox.confirm('确定不看了吗？', '取消预约', { confirmButtonText: '确定', cancelButtonText: '我再想想', type: 'warning' })
    await bookingService.cancel(b.id)
    ElMessage.success('已取消')
    fetchAll()
  } catch { /* cancelled */ }
}
function goPay(b: Booking) { router.push({ path: `/booking/payment/${b.id}` }) }
async function downloadContract(row: TenantContractItem) {
  try { const link=await contractService.getSignedDownloadLink(row.agreement_id); if (!link.url) { ElMessage.info(link.message || '签署版 PDF 正在生成'); return }; window.location.assign(link.url); ElMessage.success('合同下载已开始') }
  catch { ElMessage.error('合同下载失败，请稍后重试') }
}
const contractDateTime=(value:string)=>new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value))
const contractMoney=(minor:number|null,currency:string|null)=>minor===null||!currency?'—':new Intl.NumberFormat('zh-CN',{style:'currency',currency}).format(minor/100)
const duration=(seconds:number)=>`${String(Math.floor(seconds/3600)).padStart(2,'0')}:${String(Math.floor(seconds%3600/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`
const remainingSeconds=(order:TenantOrderItem)=>Math.min(order.remaining_payment_seconds,remainingPaymentSeconds(order.expires_at,orderNow.value))
async function refreshOrders(){ try { orders.value=await paymentService.listMyOrders();ordersError.value=false } catch { ordersError.value=true } }
async function enterPayment(order:TenantOrderItem){
  payingOrderId.value=order.booking_id
  try {
    const result=await paymentService.validatePayment(order.booking_id)
    if(!result.can_pay){ ElMessage.warning(result.reason || '当前订单暂不能支付'); await refreshOrders(); return }
    await router.push(`/booking/payment/${order.booking_id}/deposit`)
  } catch(e:any) { ElMessage.error(e?.response?.data?.detail || '支付资格校验失败，请稍后重试') }
  finally { payingOrderId.value=null }
}
function openBookingDialog(p: Property) { router.push({ path: '/booking/confirm', query: { property_id: String(p.id) } }) }
function viewRepair(row: RepairRead) { router.push(`/repairs/${row.id}`) }

async function fetchRepairs() {
  try { repairs.value = await repairService.list() }
  catch { repairs.value = [] }
}

async function submitRepair() {
  if (!repairForm.value.property_id) { ElMessage.warning('请选择房源'); return }
  if (!repairForm.value.description.trim()) { ElMessage.warning('请描述问题'); return }
  showSubmitRepair.value = true
  try {
    await repairService.create({
      property_id: repairForm.value.property_id,
      issue_type: repairForm.value.issue_type,
      description: repairForm.value.description,
      scheduled_time: repairForm.value.scheduled_time || undefined,
    })
    ElMessage.success('报修已提交，房东会尽快处理')
    showNewRepair.value = false
    repairForm.value = { property_id: 0, issue_type: 'other', description: '', scheduled_time: '' }
    await fetchRepairs()
  } catch { ElMessage.error('提交失败，请重试') }
  finally { showSubmitRepair.value = false }
}
function bindWechat() { ElMessage.info('请用微信扫码绑定') }

function maskPhone(p: string | null): string { return p && p.length >= 11 ? p.slice(0, 3) + '****' + p.slice(-4) : (p || '未设置') }
function formatDate(d: string): string { return d ? new Date(d).toLocaleDateString('zh-CN') : '' }

onMounted(() => {
  clearStaleProfileSelections()
  if(route.query.selectedContractId||route.query.selectedOrderId){const query={...route.query};delete query.selectedContractId;delete query.selectedOrderId;router.replace({query})}
  authStore.fetchCurrentUser();fetchAll();orderTimer=window.setInterval(()=>{orderNow.value=Date.now()},1000)
})
onBeforeUnmount(()=>window.clearInterval(orderTimer))
</script>

<style scoped>
.profile-page { max-width: 1000px; margin: 0 auto; }

.user-card { margin-bottom: 20px; }
.user-info { display: flex; align-items: center; gap: 20px; }
.user-detail { flex: 1; }
.user-name-row { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.user-name { font-size: 20px; font-weight: 700; color: var(--text-primary); }
.user-contact { display: flex; gap: 16px; font-size: 13px; color: var(--text-muted); flex-wrap: wrap; }
.user-actions { display: flex; gap: 10px; flex-shrink: 0; }

.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.summary-error { margin-bottom: 16px; }
.stat-card { background: var(--bg-white); border-radius: var(--radius); border: 1px solid var(--border); padding: 14px; display: flex; align-items: center; gap: 12px; cursor: pointer; transition: all 0.2s; }
.stat-card:hover { border-color: var(--primary); box-shadow: var(--shadow); transform: translateY(-2px); }
.stat-icon { font-size: 24px; }
.stat-num { font-size: 20px; font-weight: 700; color: var(--text-primary); }
.stat-label { font-size: 12px; color: var(--text-muted); }

.tabs-card { border-radius: var(--radius) !important; }
.profile-tabs :deep(.el-tabs__item) { font-size: 14px; }
.tab-toolbar { margin-bottom: 16px; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
.link-text { color: var(--primary); cursor: pointer; font-weight: 500; }
.link-text:hover { text-decoration: underline; }

.contract-hint { margin: 0 0 16px; color: var(--text-secondary); line-height: 1.6; }
.contract-list { display: flex; flex-direction: column; gap: 16px; }
.contract-card { border-radius: var(--radius); }
.contract-card-grid { display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: 20px; }
.contract-property-image { width: 180px; height: 132px; border-radius: 8px; object-fit: cover; background: #f3f5f7; }
.contract-property-image.placeholder { display: grid; place-items: center; color: var(--text-muted); }
.contract-main { min-width: 0; }
.contract-main p { margin: 7px 0; color: var(--text-secondary); line-height: 1.5; }
.contract-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 17px; }
.contract-tags { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
.contract-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 4px; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border-light); }

.order-list { display: flex; flex-direction: column; gap: 16px; }
.order-card-grid { display: grid; grid-template-columns: 190px minmax(0, 1fr); gap: 20px; }
.order-image { width: 190px; height: 145px; border-radius: 9px; object-fit: cover; background: #f3f5f7; }
.order-image.placeholder { display: grid; place-items: center; color: var(--text-muted); }
.order-main { min-width: 0; }
.order-main p { margin: 7px 0; color: var(--text-secondary); line-height: 1.5; }
.order-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 17px; }
.order-tags { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }

.fav-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }

.bill-list { display: flex; flex-direction: column; gap: 10px; }
.bill-card { display: flex; justify-content: space-between; align-items: center; background: #fff; border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 20px; }
.bill-card.paid { background: #f6ffed; border-color: #b7eb8f; }
.bill-left { display: flex; flex-direction: column; gap: 4px; }
.bill-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.bill-desc { font-size: 12px; color: var(--text-muted); }
.bill-right { display: flex; align-items: center; gap: 14px; }
.bill-amount { font-size: 22px; font-weight: 700; color: var(--danger); }
.bill-note { font-size: 12px; color: var(--text-muted); }

.msg-card { height: 320px; overflow-y: auto; }
.msg-item { padding: 10px 0; border-bottom: 1px solid var(--border-light); }
.msg-item:last-child { border-bottom: none; }
.msg-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.msg-time { font-size: 12px; color: var(--text-muted); margin-left: auto; }
.msg-text { font-size: 13px; color: var(--text-secondary); margin: 4px 0; }

.setting-card { margin-bottom: 16px; }
.notif-switches { display: flex; flex-direction: column; gap: 10px; }
.help-links { display: flex; flex-direction: column; gap: 6px; }

@media (max-width: 768px) {
  .contract-card-grid { grid-template-columns: 1fr; }
  .contract-property-image { width: 100%; height: 180px; }
  .contract-title { align-items: flex-start; }
  .contract-actions { justify-content: flex-start; }
  .order-card-grid { grid-template-columns: 1fr; }
  .order-image { width: 100%; height: 190px; }
}
</style>
