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
          <div class="stat-num">{{ bookings.length }}</div>
          <div class="stat-label">看房预约</div>
        </div>
      </div>
      <div class="stat-card" @click="activeTab = 'bills'">
        <span class="stat-icon">💳</span>
        <div class="stat-info">
          <div class="stat-num">{{ unpaidCount }}</div>
          <div class="stat-label">待支付</div>
        </div>
      </div>
      <div class="stat-card" @click="activeTab = 'contracts'">
        <span class="stat-icon">📄</span>
        <div class="stat-info">
          <div class="stat-num">{{ contracts.length }}</div>
          <div class="stat-label">我的合同</div>
        </div>
      </div>
      <div class="stat-card" @click="activeTab = 'favorites'">
        <span class="stat-icon">❤️</span>
        <div class="stat-info">
          <div class="stat-num">{{ favorites.length }}</div>
          <div class="stat-label">收藏</div>
        </div>
      </div>
    </div>

    <!-- ===== Tab 主体 ===== -->
    <el-card shadow="never" class="tabs-card">
      <el-tabs v-model="activeTab" class="profile-tabs" type="border-card">

        <!-- Tab1: 看房预约 -->
        <el-tab-pane label="📅 看房预约" name="bookings">
          <div class="tab-toolbar">
            <el-radio-group v-model="bookingFilter" size="small">
              <el-radio-button value="all">全部 ({{ bookings.length }})</el-radio-button>
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
          <div class="tab-toolbar">
            <el-radio-group v-model="contractFilter" size="small">
              <el-radio-button value="active">生效中</el-radio-button>
              <el-radio-button value="expiring">快到期了</el-radio-button>
              <el-radio-button value="ended">已结束</el-radio-button>
            </el-radio-group>
          </div>
          <el-empty v-if="filteredContracts.length === 0" description="还没有合同，支付押金后会自动生成电子合同" />
          <el-table v-else :data="filteredContracts" stripe>
            <el-table-column label="房源" min-width="150">
              <template #default="{ row }">
                <span class="link-text" @click="$router.push(`/property/${row.propertyId}`)">{{ row.propertyTitle }}</span>
              </template>
            </el-table-column>
            <el-table-column label="租期" width="170">
              <template #default="{ row }">{{ row.startDate }} ~ {{ row.endDate }}</template>
            </el-table-column>
            <el-table-column label="月租金" width="100" prop="rent" />
            <el-table-column label="押金" width="90" prop="deposit" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === '生效中' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="router.push(`/contract/${row.bookingId}`)">查看合同</el-button>
                <el-button size="small" text @click="downloadContract(row)">下载</el-button>
              </template>
            </el-table-column>
          </el-table>
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

        <!-- Tab4: 我的账单（简化版） -->
        <el-tab-pane label="💳 我的账单" name="bills">
          <div class="tab-toolbar">
            <el-radio-group v-model="billTab" size="small">
              <el-radio-button value="unpaid">待支付</el-radio-button>
              <el-radio-button value="paid">已支付</el-radio-button>
            </el-radio-group>
          </div>

          <!-- 待支付 -->
          <template v-if="billTab === 'unpaid'">
            <el-empty v-if="unpaidOrders.length === 0" description="没有待支付的账单">
              <el-button type="primary" @click="$router.push('/search')">去选房</el-button>
            </el-empty>
            <div v-else class="bill-list">
              <div v-for="d in unpaidOrders" :key="d.bookingId" class="bill-card">
                <div class="bill-left">
                  <span class="bill-title">🏠 房源 #{{ d.propertyId }}</span>
                  <span class="bill-desc">押金（租房定金）</span>
                </div>
                <div class="bill-right">
                  <span class="bill-amount">¥{{ d.amount }}</span>
                  <span class="bill-note">支付后自动生成租房合同</span>
                  <el-button type="primary" size="small" round @click="router.push(`/booking/payment/${d.bookingId}/deposit`)">去支付</el-button>
                </div>
              </div>
            </div>
          </template>

          <!-- 已支付 -->
          <template v-if="billTab === 'paid'">
            <el-empty v-if="paidOrders.length === 0" description="还没有已支付的账单" />
            <div v-else class="bill-list">
              <div v-for="d in paidOrders" :key="d.bookingId" class="bill-card paid">
                <div class="bill-left">
                  <span class="bill-title">✅ 房源 #{{ d.propertyId }}</span>
                  <span class="bill-desc">押金已付 · 合同已生成</span>
                </div>
                <div class="bill-right">
                  <span class="bill-amount">¥{{ d.amount }}</span>
                  <span class="bill-note">{{ d.payTime }}</span>
                  <el-button size="small" text type="primary" @click="router.push(`/contract/${d.bookingId}`)">查看合同</el-button>
                </div>
              </div>
            </div>
          </template>
        </el-tab-pane>

        <!-- Tab5: 报修 -->
        <el-tab-pane label="🔧 报修" name="repairs">
          <div class="tab-toolbar">
            <el-button type="primary" size="small" @click="showNewRepair = true">我要报修</el-button>
          </div>
          <el-empty v-if="repairs.length === 0" description="没有报修记录，一切正常 👍" />
          <el-table v-else :data="repairs" stripe>
            <el-table-column label="房源" prop="property" min-width="140" />
            <el-table-column label="问题" prop="desc" min-width="180" />
            <el-table-column label="提交时间" prop="date" width="110" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="repairTag(row.status)" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="viewRepair(row)">看进度</el-button>
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
    <el-dialog v-model="showNewRepair" title="我要报修" width="420px">
      <el-form label-width="70px">
        <el-form-item label="房源"><el-select style="width:100%" placeholder="选房源"><el-option v-for="b in bookings" :key="b.id" :label="'房源 #'+b.property_id" :value="b.property_id" /></el-select></el-form-item>
        <el-form-item label="哪里坏了"><el-select style="width:100%" placeholder="选类型"><el-option label="💧 水电" value="utility" /><el-option label="🔌 家电" value="appliance" /><el-option label="🪟 门窗" value="door" /><el-option label="🧱 墙面地面" value="structure" /><el-option label="其他" value="other" /></el-select></el-form-item>
        <el-form-item label="描述一下"><el-input type="textarea" :rows="3" placeholder="简单说说哪里出了问题..." /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showNewRepair = false">算了</el-button><el-button type="primary" @click="submitRepair">提交</el-button></template>
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
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UserFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { bookingService } from '@/services/booking'
import { contractService } from '@/services/contract'
import { propertyService } from '@/services/property'
import { storeToRefs } from 'pinia'
import PropertyCard from '@/components/PropertyCard.vue'
import { favoriteService } from '@/services/favorite'
import type { Booking } from '@/types/booking'
import type { Property } from '@/types/property'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { user } = storeToRefs(authStore)

const activeTab = ref((route.query.tab as string) || 'bookings')
const pageLoading = ref(false)
const showVerify = ref(false)
const showNewRepair = ref(false)
const bookingFilter = ref('all')
const contractFilter = ref('active')
const billTab = ref('unpaid')

const bookings = ref<Booking[]>([])
const favorites = ref<Property[]>([])
const repairs = ref<any[]>([])
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
const repairTag = (s: string) => ({ '待处理': 'danger', '维修中': 'warning', '已完成': 'success' }[s] || 'info') as 'danger'|'warning'|'success'|'info'

const filteredBookings = computed(() => {
  if (bookingFilter.value === 'all') return bookings.value
  return bookings.value.filter(b => b.status === bookingFilter.value)
})

const contracts = computed(() => {
  return bookings.value
    .filter(b => b.deposit_status === 'paid' || b.deposit_status === 'confirmed' || b.status === 'completed')
    .map(b => ({
      bookingId: b.id, propertyId: b.property_id, propertyTitle: `房源 #${b.property_id}`,
      startDate: b.scheduled_date || '—', endDate: b.status === 'completed' ? '已到期' : '续租中',
      rent: `¥${b.deposit_amount || 0}`, deposit: `¥${b.deposit_amount || 0}`,
      status: b.status === 'completed' ? '已结束' : '生效中',
    }))
})
const filteredContracts = computed(() => {
  if (contractFilter.value === 'active') return contracts.value.filter(c => c.status === '生效中')
  if (contractFilter.value === 'expiring') return contracts.value.filter(c => c.status === '快到期了')
  return contracts.value.filter(c => c.status === '已结束')
})

const unpaidCount = computed(() => bookings.value.filter(b => b.status !== 'cancelled' && b.deposit_status !== 'paid' && b.deposit_status !== 'confirmed').length)
const unpaidOrders = computed(() => bookings.value
  .filter(b => b.status !== 'cancelled' && b.status !== 'rejected' && b.deposit_status !== 'paid' && b.deposit_status !== 'confirmed')
  .map(b => ({ bookingId: b.id, propertyId: b.property_id, amount: b.deposit_amount || 0 })))
const paidOrders = computed(() => bookings.value
  .filter(b => b.deposit_status === 'paid' || b.deposit_status === 'confirmed')
  .map(b => ({ bookingId: b.id, propertyId: b.property_id, amount: b.deposit_amount || 0, payTime: b.updated_at ? new Date(b.updated_at).toLocaleDateString('zh-CN') : '' })))

// ── Actions ──
async function fetchAll() {
  pageLoading.value = true
  try { bookings.value = (await bookingService.list()).filter(b => b.deposit_status !== 'paid' && b.deposit_status !== 'confirmed') }
  catch { bookings.value = [] }
  try {
    const favItems = await favoriteService.list()
    const ids = favItems.map((f) => f.property_id)
    if (ids.length > 0) {
      const results = await Promise.allSettled(ids.map((id) => propertyService.getById(id)))
      favorites.value = results
        .filter((r): r is PromiseFulfilledResult<Property> => r.status === 'fulfilled')
        .map((r) => r.value)
    } else {
      favorites.value = []
    }
  } catch { favorites.value = [] }
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
async function downloadContract(row: any) {
  try { await contractService.download(row.id); ElMessage.success('正在下载...') }
  catch { ElMessage.info('下载功能接入中') }
}
function openBookingDialog(p: Property) { router.push({ path: '/booking/confirm', query: { property_id: String(p.id) } }) }
function viewRepair(row: any) { ElMessage.info(`工单 ${row.id}：${row.status}`) }
function submitRepair() { ElMessage.success('报修已提交，房东会尽快处理'); showNewRepair.value = false }
function bindWechat() { ElMessage.info('请用微信扫码绑定') }

function maskPhone(p: string | null): string { return p && p.length >= 11 ? p.slice(0, 3) + '****' + p.slice(-4) : (p || '未设置') }
function formatDate(d: string): string { return d ? new Date(d).toLocaleDateString('zh-CN') : '' }

// 每次进入个人中心都重新拉取数据
authStore.fetchCurrentUser()
fetchAll()
watch(() => route.path, () => {
  if (route.path === '/profile') {
    authStore.fetchCurrentUser()
    fetchAll()
  }
})
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
</style>
