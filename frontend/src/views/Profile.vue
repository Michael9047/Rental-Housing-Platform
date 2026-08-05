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
          </div>
          <div class="user-contact">
            <span v-if="user?.email">📧 {{ user.email }}</span>
            <span v-if="user?.phone">📱 {{ maskPhone(user.phone) }}</span>
            <span>📅 {{ formatDate(user?.created_at || '') }} 加入</span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- ===== Tab 主体 ===== -->
    <el-card shadow="never" class="tabs-card">
      <el-tabs v-model="activeTab" class="profile-tabs" type="border-card">

        <!-- Tab1: 我的合同 -->
        <el-tab-pane label="📄 我的合同" name="contracts">
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
                <el-button text @click="router.push(`/building/${row.property_id}`)">查看房源</el-button>
                <el-button v-if="row.booking_id && !['paid','cancelled','refunded','payment_expired'].includes(row.payment_status) && row.booking_status !== 'confirmed'" type="primary" @click="router.push(`/booking/payment/${row.booking_id}/deposit`)">继续支付</el-button>
                <el-button v-if="row.booking_id && ['payment_expired','cancelled'].includes(row.payment_status)" type="warning" @click="router.push(`/booking/${row.property_id}/move-in-date`)">重新预订</el-button>
              </div>
            </el-card>
          </div>
        </el-tab-pane>

        <!-- Tab2: 我的账单 / 我的订单 -->
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
                <el-button text type="primary" @click="router.push(`/my-orders/${order.booking_id}`)">查看详情</el-button>
                <el-button text @click="router.push(`/building/${order.property_id}`)">查看房源</el-button>
                <el-button v-if="order.agreement_id && order.booking_status !== 'confirmed'" text @click="router.push(`/my-contracts/${order.agreement_id}`)">查看合同</el-button>
                <el-button v-if="order.payment_status === 'payment_processing'" text @click="refreshOrders">刷新状态</el-button>
                <el-button v-if="order.booking_id && !['paid','cancelled','refunded','payment_expired'].includes(order.payment_status) && order.booking_status !== 'confirmed'" type="primary" @click="router.push(`/booking/payment/${order.booking_id}/deposit`)">继续支付</el-button>
                <el-button v-if="order.booking_id && ['payment_expired','cancelled'].includes(order.payment_status)" type="warning" @click="router.push(`/booking/${order.property_id}/move-in-date`)">重新预订</el-button>
              </div>
            </el-card>
          </div>
        </el-tab-pane>

        <!-- Tab3: 我的信息（租客管理） -->
        <el-tab-pane label="👤 我的信息" name="my-info">
          <div class="tab-toolbar">
            <span class="toolbar-hint">管理租客档案，签合同时可直接选择租客信息填入</span>
            <el-button type="primary" @click="openAddTenant">+ 添加租客</el-button>
          </div>

          <el-empty v-if="tenants.length === 0 && !tenantLoading" description="还没有租客档案，点击上方按钮添加" />
          <div v-else class="tenant-list" v-loading="tenantLoading">
            <el-card v-for="t in tenants" :key="t.id" shadow="hover" :class="['tenant-card', { 'is-default': t.is_default }]">
              <div class="tenant-card-body">
                <div class="tenant-card-main">
                  <div class="tenant-card-header">
                    <span class="tenant-label">{{ t.label || '未命名' }}</span>
                    <el-tag v-if="t.is_default" type="success" size="small" effect="dark">默认</el-tag>
                  </div>
                  <div class="tenant-card-info">
                    <span v-if="t.chinese_name">{{ t.chinese_name }}</span>
                    <span v-if="t.phone">📱 {{ maskPhone(t.phone) }}</span>
                    <span v-if="t.school_name">🎓 {{ t.school_name }}</span>
                  </div>
                </div>
                <div class="tenant-card-actions">
                  <el-button size="small" text type="primary" @click="openEditTenant(t)">编辑</el-button>
                  <el-button v-if="!t.is_default" size="small" text type="success" @click="setDefaultTenant(t.id)">设为默认</el-button>
                  <el-button size="small" text type="danger" @click="deleteTenant(t)">删除</el-button>
                </div>
              </div>
            </el-card>
          </div>

          <!-- 添加/编辑租客弹窗 -->
          <el-dialog v-model="showTenantDialog" :title="editingTenant ? '编辑租客' : '添加租客'" width="640px" :close-on-click-modal="false">
            <el-form label-width="100px" label-position="top" size="small">
              <el-row :gutter="16">
                <el-col :span="8"><el-form-item label="中文姓名"><el-input v-model="tenantForm.chinese_name" placeholder="与证件一致" /></el-form-item></el-col>
                <el-col :span="8"><el-form-item label="名（拼音大写）"><el-input v-model="tenantForm.given_name_pinyin" placeholder="如 MING" @input="tenantForm.given_name_pinyin = tenantForm.given_name_pinyin.toUpperCase()" /></el-form-item></el-col>
                <el-col :span="8"><el-form-item label="姓（拼音大写）"><el-input v-model="tenantForm.surname_pinyin" placeholder="如 WANG" @input="tenantForm.surname_pinyin = tenantForm.surname_pinyin.toUpperCase()" /></el-form-item></el-col>
              </el-row>
              <el-row :gutter="16">
                <el-col :span="8"><el-form-item label="出生日期"><el-date-picker v-model="tenantForm.birth_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
                <el-col :span="8"><el-form-item label="性别"><el-radio-group v-model="tenantForm.gender"><el-radio value="male" size="small">男</el-radio><el-radio value="female" size="small">女</el-radio></el-radio-group></el-form-item></el-col>
              </el-row>
              <el-form-item label="手机号"><el-input v-model="tenantForm.phone" placeholder="手机号" /></el-form-item>
              <el-form-item label="邮箱"><el-input v-model="tenantForm.email" placeholder="邮箱" /></el-form-item>
              <el-row :gutter="16">
                <el-col :span="8"><el-form-item label="国籍/地区"><el-select v-model="tenantForm.nationality" style="width:100%" filterable><el-option v-for="c in nationalityOptions" :key="c" :label="c" :value="c" /></el-select></el-form-item></el-col>
                <el-col :span="8"><el-form-item label="学校"><el-input v-model="tenantForm.school_name" placeholder="学校全称" /></el-form-item></el-col>
                <el-col :span="8"><el-form-item label="入学年级"><el-select v-model="tenantForm.enrollment_grade" style="width:100%"><el-option v-for="g in gradeOptions" :key="g" :label="g" :value="g" /></el-select></el-form-item></el-col>
              </el-row>
              <el-row :gutter="16">
                <el-col :span="8"><el-form-item label="专业（英文）"><el-input v-model="tenantForm.major_english" placeholder="如 Computer Science" /></el-form-item></el-col>
                <el-col :span="8"><el-form-item label="签证类型"><el-input v-model="tenantForm.visa_type" placeholder="如 Student Pass" /></el-form-item></el-col>
                <el-col :span="8"><el-form-item label="签证到期日"><el-date-picker v-model="tenantForm.visa_expiry" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
              </el-row>
              <el-row :gutter="16">
                <el-col :span="8"><el-form-item label="公民身份国家"><el-input v-model="tenantForm.citizenship_country" placeholder="如 China" /></el-form-item></el-col>
              </el-row>
              <el-form-item label="标签"><el-input v-model="tenantForm.label" placeholder="可选，如：本人、室友A" maxlength="50" /></el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="showTenantDialog = false">取消</el-button>
              <el-button type="primary" :loading="savingTenant" @click="saveTenant">{{ editingTenant ? '保存修改' : '添加' }}</el-button>
            </template>
          </el-dialog>
        </el-tab-pane>

        <!-- Tab4: 设置 -->
        <el-tab-pane label="⚙️ 设置" name="settings">
          <el-card shadow="never" class="setting-card">
            <template #header>🔐 账号安全</template>
            <el-form label-width="100px" size="default">
              <el-form-item label="手机号">
                <span class="security-value">{{ user?.phone ? maskPhone(user.phone) : '未绑定' }}</span>
                <el-button size="small" text type="primary" @click="openChangePhone" style="margin-left:12px">更换手机号</el-button>
              </el-form-item>
              <el-form-item label="密码">
                <span class="security-value">********</span>
                <el-button size="small" text type="primary" @click="showChangePassword = true" style="margin-left:12px">修改密码</el-button>
              </el-form-item>
              <el-form-item label="微信">
                <el-tag :type="user?.wechat_openid ? 'success' : 'info'" size="small">{{ user?.wechat_openid ? '已绑定' : '未绑定' }}</el-tag>
                <el-button size="small" text type="primary" @click="bindWechat" style="margin-left:12px">{{ user?.wechat_openid ? '换绑' : '绑定' }}</el-button>
              </el-form-item>
            </el-form>
          </el-card>
          <el-row :gutter="24">
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

    <!-- 修改密码弹窗 -->
    <el-dialog v-model="showChangePassword" title="修改密码" width="400px">
      <el-form label-width="100px">
        <el-form-item label="旧密码">
          <el-input v-model="passwordForm.old_password" type="password" placeholder="请输入旧密码" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="passwordForm.new_password" type="password" placeholder="至少8位" show-password />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="passwordForm.confirm_password" type="password" placeholder="再次输入新密码" show-password @keyup.enter="submitChangePassword" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showChangePassword = false">取消</el-button>
        <el-button type="primary" :loading="changingPassword" @click="submitChangePassword">确认修改</el-button>
      </template>
    </el-dialog>

    <!-- 更换手机号弹窗 -->
    <el-dialog v-model="showChangePhone" title="更换手机号" width="400px">
      <el-form label-width="100px">
        <el-form-item label="当前手机号">
          <span class="security-value">{{ user?.phone ? maskPhone(user.phone) : '未绑定' }}</span>
        </el-form-item>
        <el-form-item label="新手机号">
          <el-input v-model="phoneForm.new_phone" placeholder="请输入新手机号" maxlength="11" />
        </el-form-item>
        <el-form-item label="验证码">
          <div style="display:flex;gap:12px;width:100%">
            <el-input v-model="phoneForm.sms_code" placeholder="6位验证码" maxlength="6" style="flex:1" @keyup.enter="submitChangePhone" />
            <el-button :disabled="phoneCodeCountdown > 0" :loading="sendingPhoneCode" @click="sendPhoneCode" style="min-width:110px">
              {{ phoneCodeCountdown > 0 ? `${phoneCodeCountdown}s 后重发` : '发送验证码' }}
            </el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showChangePhone = false">取消</el-button>
        <el-button type="primary" :loading="changingPhone" @click="submitChangePhone">确认更换</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UserFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { authService } from '@/services/auth'
import { bookingService } from '@/services/booking'
import { contractService } from '@/services/contract'
import type { TenantContractItem } from '@/services/contract'
import { paymentService, type TenantOrderItem } from '@/services/payment'
import { remainingPaymentSeconds } from '@/utils/orderPresentation'
import { profileService, type DashboardSummary } from '@/services/profile'
import { tenantService, type TenantProfile, type TenantCreateData } from '@/services/tenant'
import { storeToRefs } from 'pinia'
import type { Booking } from '@/types/booking'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { user } = storeToRefs(authStore)

const activeTab = ref((route.query.tab as string) || 'bills')
const pageLoading = ref(false)
const contractFilter = ref('pending_effective')
const billTab = ref('pending')

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

// ── 账号安全 ──────────────────────────────
const showChangePassword = ref(false)
const showChangePhone = ref(false)
const changingPassword = ref(false)
const changingPhone = ref(false)
const sendingPhoneCode = ref(false)
const phoneCodeCountdown = ref(0)
let phoneCodeTimer: ReturnType<typeof setInterval> | null = null

const passwordForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const phoneForm = ref({ new_phone: '', sms_code: '' })

async function submitChangePassword() {
  if (!passwordForm.value.old_password) { ElMessage.warning('请输入旧密码'); return }
  if (!passwordForm.value.new_password || passwordForm.value.new_password.length < 8) { ElMessage.warning('新密码至少8位'); return }
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) { ElMessage.warning('两次输入的密码不一致'); return }
  changingPassword.value = true
  try {
    await authService.changePassword({ old_password: passwordForm.value.old_password, new_password: passwordForm.value.new_password })
    ElMessage.success('密码已修改，请重新登录')
    passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
    showChangePassword.value = false
    authStore.logout()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '修改失败，请重试')
  } finally {
    changingPassword.value = false
  }
}

function openChangePhone() {
  phoneForm.value = { new_phone: '', sms_code: '' }
  showChangePhone.value = true
}

async function sendPhoneCode() {
  const phone = phoneForm.value.new_phone.trim()
  if (!phone || !/^1[3-9]\d{9}$/.test(phone)) { ElMessage.warning('请输入正确的手机号'); return }
  sendingPhoneCode.value = true
  try {
    await authService.sendSmsCode({ phone })
    ElMessage.success('验证码已发送')
    phoneCodeCountdown.value = 60
    phoneCodeTimer = setInterval(() => {
      phoneCodeCountdown.value--
      if (phoneCodeCountdown.value <= 0 && phoneCodeTimer) { clearInterval(phoneCodeTimer); phoneCodeTimer = null }
    }, 1000)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '发送失败，请重试')
  } finally {
    sendingPhoneCode.value = false
  }
}

async function submitChangePhone() {
  const phone = phoneForm.value.new_phone.trim()
  if (!phone || !/^1[3-9]\d{9}$/.test(phone)) { ElMessage.warning('请输入正确的手机号'); return }
  if (!phoneForm.value.sms_code || phoneForm.value.sms_code.length !== 6) { ElMessage.warning('请输入6位验证码'); return }
  changingPhone.value = true
  try {
    await authService.changePhone({ new_phone: phone, sms_code: phoneForm.value.sms_code })
    ElMessage.success('手机号已修改')
    showChangePhone.value = false
    authStore.fetchCurrentUser()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '修改失败，请重试')
  } finally {
    changingPhone.value = false
  }
}

function bindWechat() { ElMessage.info('请用微信扫码绑定') }

// ── 租客档案管理 ───────────────────────────
const nationalityOptions = ['中国大陆','中国香港','中国澳门','中国台湾','英国','美国','加拿大','澳大利亚','新加坡','日本','韩国','德国','法国','其他']
const gradeOptions = ['本科一年级','本科二年级','本科三年级','本科四年级','硕士','博士','语言课程','其他']

const tenants = ref<TenantProfile[]>([])
const tenantLoading = ref(false)
const showTenantDialog = ref(false)
const savingTenant = ref(false)
const editingTenant = ref<TenantProfile | null>(null)
const tenantForm = ref<TenantCreateData>({
  label: '', chinese_name: '', given_name_pinyin: '', surname_pinyin: '',
  birth_date: '', gender: '', phone: '', email: '', nationality: '中国大陆',
  school_name: '', enrollment_grade: '', major_english: '',
  visa_type: '', visa_expiry: '', citizenship_country: '',
})

function resetTenantForm() {
  tenantForm.value = {
    label: '', chinese_name: '', given_name_pinyin: '', surname_pinyin: '',
    birth_date: '', gender: '', phone: '', email: '', nationality: '中国大陆',
    school_name: '', enrollment_grade: '', major_english: '',
    visa_type: '', visa_expiry: '', citizenship_country: '',
  }
}

function openAddTenant() {
  editingTenant.value = null
  resetTenantForm()
  showTenantDialog.value = true
}

function openEditTenant(t: TenantProfile) {
  editingTenant.value = t
  tenantForm.value = {
    label: t.label || '', chinese_name: t.chinese_name || '',
    given_name_pinyin: t.given_name_pinyin || '', surname_pinyin: t.surname_pinyin || '',
    birth_date: t.birth_date || '', gender: t.gender || '',
    phone: t.phone || '', email: t.email || '',
    nationality: t.nationality || '中国大陆', school_name: t.school_name || '',
    enrollment_grade: t.enrollment_grade || '', major_english: t.major_english || '',
    visa_type: t.visa_type || '', visa_expiry: t.visa_expiry || '',
    citizenship_country: t.citizenship_country || '',
  }
  showTenantDialog.value = true
}

async function saveTenant() {
  savingTenant.value = true
  try {
    if (editingTenant.value) {
      await tenantService.update(editingTenant.value.id, tenantForm.value)
      ElMessage.success('租客信息已更新')
    } else {
      await tenantService.create(tenantForm.value)
      ElMessage.success('租客已添加')
    }
    showTenantDialog.value = false
    await fetchTenants()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '保存失败')
  } finally {
    savingTenant.value = false
  }
}

async function setDefaultTenant(id: number) {
  try {
    await tenantService.setDefault(id)
    ElMessage.success('已设为默认租客')
    await fetchTenants()
  } catch { ElMessage.error('设置失败') }
}

async function deleteTenant(t: TenantProfile) {
  try {
    await ElMessageBox.confirm(`确定删除「${t.label || t.chinese_name || '未命名'}」吗？`, '删除租客', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' })
    await tenantService.delete(t.id)
    ElMessage.success('已删除')
    await fetchTenants()
  } catch { /* cancelled */ }
}

async function fetchTenants() {
  tenantLoading.value = true
  try { tenants.value = await tenantService.listMine() }
  catch { tenants.value = [] }
  finally { tenantLoading.value = false }
}

const notifSite = ref(true)
const notifSms = ref(true)

// ── Computed ──
const filteredContracts = computed(() => {
  return contracts.value.filter(c => c.category === contractFilter.value)
})

const successfulOrderStatuses = new Set(['paid', 'success', 'confirmed'])
const filteredOrders = computed(() => orders.value.filter(order => billTab.value === 'successful'
  ? order.booking_status === 'confirmed' && successfulOrderStatuses.has(order.payment_status)
  : order.booking_status !== 'confirmed'))

// ── Actions ──
async function fetchAll() {
  pageLoading.value = true
  summaryLoading.value = true
  const [summaryResult, contractsResult, ordersResult] = await Promise.allSettled([
    profileService.getSummary(), contractService.listMine(), paymentService.listMyOrders(),
  ])
  if (summaryResult.status === 'fulfilled') { summary.value = summaryResult.value; summaryError.value = false } else { summary.value = null; summaryError.value = true }
  summaryLoading.value = false
  if (contractsResult.status === 'fulfilled') { contracts.value = contractsResult.value; contractsError.value = false } else { console.error('contractsResult rejected:', contractsResult.reason); contractsError.value = true }
  if (ordersResult.status === 'fulfilled') { orders.value = ordersResult.value; ordersError.value = false } else { console.error('ordersResult rejected:', ordersResult.reason); ordersError.value = true }
  pageLoading.value = false
}

async function downloadContract(row: TenantContractItem) {
  try { const link = await contractService.getSignedDownloadLink(row.agreement_id); if (!link.url) { ElMessage.info(link.message || '签署版 PDF 正在生成'); return }; window.location.assign(link.url); ElMessage.success('合同下载已开始') }
  catch { ElMessage.error('合同下载失败，请稍后重试') }
}

const contractDateTime = (value: string) => new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
const contractMoney = (minor: number | null, currency: string | null) => minor === null || !currency ? '—' : new Intl.NumberFormat('zh-CN', { style: 'currency', currency }).format(minor / 100)
const duration = (seconds: number) => `${String(Math.floor(seconds / 3600)).padStart(2, '0')}:${String(Math.floor(seconds % 3600 / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
const remainingSeconds = (order: TenantOrderItem) => Math.min(order.remaining_payment_seconds, remainingPaymentSeconds(order.expires_at, orderNow.value))

async function refreshOrders() { try { orders.value = await paymentService.listMyOrders(); ordersError.value = false } catch { ordersError.value = true } }

function maskPhone(p: string | null): string { return p && p.length >= 11 ? p.slice(0, 3) + '****' + p.slice(-4) : (p || '未设置') }
function formatDate(d: string): string { return d ? new Date(d).toLocaleDateString('zh-CN') : '' }

onMounted(() => {
  if (route.query.selectedContractId || route.query.selectedOrderId) { const query = { ...route.query }; delete query.selectedContractId; delete query.selectedOrderId; router.replace({ query }) }
  authStore.fetchCurrentUser(); fetchAll(); fetchTenants()
  orderTimer = window.setInterval(() => { orderNow.value = Date.now() }, 1000)
})
onBeforeUnmount(() => {
  window.clearInterval(orderTimer)
  if (phoneCodeTimer) clearInterval(phoneCodeTimer)
})
</script>

<style scoped>
.profile-page { width: 960px; max-width: 100%; margin: 0 auto; }

.user-card { margin-bottom: 20px; }
.user-info { display: flex; align-items: center; gap: 20px; }
.user-detail { flex: 1; }
.user-name-row { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.user-name { font-size: 20px; font-weight: 700; color: var(--text-primary); }
.user-contact { display: flex; gap: 16px; font-size: 13px; color: var(--text-muted); flex-wrap: wrap; }
.user-actions { display: flex; gap: 10px; flex-shrink: 0; }

.tabs-card { border-radius: var(--radius) !important; }
.profile-tabs :deep(.el-tabs__item) { font-size: 14px; }
.tab-toolbar { margin-bottom: 16px; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 10px; }

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

.setting-card { margin-bottom: 16px; }
.security-value { font-size: 14px; color: var(--text-primary); font-weight: 500; }
.toolbar-hint { font-size: 13px; color: var(--text-muted); }
.tenant-list { display: flex; flex-direction: column; gap: 12px; }
.tenant-card { border-radius: var(--radius); transition: all 0.2s; }
.tenant-card.is-default { border-color: var(--primary); border-width: 2px; }
.tenant-card-body { display: flex; justify-content: space-between; align-items: center; }
.tenant-card-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.tenant-label { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.tenant-card-info { display: flex; gap: 16px; font-size: 13px; color: var(--text-muted); flex-wrap: wrap; }
.tenant-card-actions { display: flex; gap: 4px; flex-shrink: 0; }

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
