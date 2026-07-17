<template>
  <el-card shadow="never" class="step-card">
    <template #header>
      <div class="card-header">
        <span class="card-title">请仔细阅读下方内容</span>
        <span class="card-subtitle">
          在提交您的信息之前，请仔细阅读以下内容。您的填写进度将在每一步自动保存，您可以随时返回继续完成申请。
        </span>
      </div>
    </template>

    <!-- Property Info -->
    <div class="property-info-box" v-if="bookingFlow.property">
      <div class="info-row">
        <span class="info-label">公寓楼名称：</span>
        <span class="info-value">{{ bookingFlow.property.title }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">国家/地区：</span>
        <span class="info-value">{{ bookingFlow.property.country || '英国' }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">城市：</span>
        <span class="info-value">{{ bookingFlow.property.district }}</span>
      </div>
      <div class="info-row" v-if="bookingFlow.applicant.school_name">
        <span class="info-label">留学学校：</span>
        <span class="info-value">{{ bookingFlow.applicant.school_name }}</span>
      </div>
    </div>

    <!-- Payment Info -->
    <div class="payment-info-box">
      <h4 class="payment-title">预订需缴纳的费用</h4>
      <div class="payment-row">
        <span>总租金</span>
        <span>{{ formatPrice(bookingFlow.total_price) }}</span>
      </div>
      <div class="payment-row">
        <span>预付租金</span>
        <span>{{ formatPrice(firstPayment) }}</span>
      </div>
      <div class="payment-note">* 交易手续费将根据您选择的付款方式而有所不同</div>
    </div>

    <!-- Agreements List -->
    <div class="agreements-list">
      <div class="agreement-item">
        <span class="agreement-num">1.</span>
        <span>我已阅读并同意</span>
        <el-link type="primary" :underline="false" @click="showAgreement('booking')">《订房授权书》</el-link>
      </div>

      <div class="agreement-item">
        <span class="agreement-num">2.</span>
        <span>为了申请房源预订，我同意平台将我本次填写的信息跨境提交给房源供应方，并使用这些信息帮我申请房源，详见</span>
        <el-link type="primary" :underline="false" @click="showAgreement('data')">《个人信息出境授权声明》</el-link>
        <span>。请注意，</span>
        <span class="highlight-text">个人敏感信息包含（住址信息：联系地址；担保人地址：联系地址；紧急联系人地址：联系地址），</span>
        <span>我们将严格遵守</span>
        <el-link type="primary" :underline="false" @click="showAgreement('privacy')">《隐私政策》</el-link>
        <span>按照个人信息保护相关规定进行处理，仅用于申请房源预订，不会用于其他用途。</span>
      </div>

      <div class="agreement-item">
        <span class="agreement-num">3.</span>
        <span>我已阅读</span>
        <el-link type="primary" :underline="false" @click="showAgreement('cancel')">《公寓退订政策》</el-link>
        <span>，确认本份订单即代表我知晓本公寓退单政策的细则，若产生退单的行为，将严格遵照公寓规定完成后续处理。</span>
      </div>
    </div>

    <!-- Free Cancellation Note -->
    <div class="free-cancel-box">
      <el-icon :size="20" color="#67c23a"><CircleCheckFilled /></el-icon>
      <span>本房源支持免责退订的情况有：</span>
      <ul class="cancel-list">
        <li>签证被拒（需提供拒签证明）</li>
        <li>学校offer被撤回（需提供相关证明）</li>
        <li>入住前30天以上取消预订（扣除服务费）</li>
      </ul>
    </div>

    <!-- Checkboxes -->
    <div class="checkboxes-section">
      <el-checkbox v-model="bookingFlow.agreements_accepted.booking_auth">
        我已阅读并同意《公寓退订政策》
      </el-checkbox>
      <el-checkbox v-model="bookingFlow.agreements_accepted.data_transfer">
        我已阅读并同意上述协议中数据跨境事项
      </el-checkbox>
      <el-checkbox v-model="bookingFlow.agreements_accepted.cancellation">
        我已阅读并同意上述协议中收集个人敏感信息事项
      </el-checkbox>
    </div>

    <!-- Confirm Button -->
    <div class="step-footer">
      <el-button size="large" @click="$emit('prev')">上一步</el-button>
      <el-button
        type="primary"
        size="large"
        :disabled="!allChecked"
        @click="handleConfirm"
      >
        我已阅读并同意上述内容
      </el-button>
    </div>

    <!-- Agreement Dialog -->
    <AgreementDialog v-model="agreementDialogVisible" :type="currentAgreementType" />
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { CircleCheckFilled } from '@element-plus/icons-vue'
import { useBookingFlowStore } from '@/stores/bookingFlow'
import { formatPriceWithDual } from '@/data/currency'
import AgreementDialog from '@/components/booking/AgreementDialog.vue'

const emit = defineEmits<{
  (e: 'prev'): void
  (e: 'confirm'): void
}>()

const bookingFlow = useBookingFlowStore()

const agreementDialogVisible = ref(false)
const currentAgreementType = ref('booking')

const allChecked = computed({
  get: () =>
    bookingFlow.agreements_accepted.booking_auth &&
    bookingFlow.agreements_accepted.data_transfer &&
    bookingFlow.agreements_accepted.cancellation,
  set: (val) => {
    bookingFlow.agreements_accepted.booking_auth = val
    bookingFlow.agreements_accepted.data_transfer = val
    bookingFlow.agreements_accepted.cancellation = val
    bookingFlow.saveToStorage()
  },
})

const countryCode = computed(() => bookingFlow.property?.country || 'CN')

const firstPayment = computed(() => {
  if (!bookingFlow.property) return 0
  const monthly = Number(bookingFlow.property.price_monthly) || 0
  return Math.round(monthly + bookingFlow.deposit_amount + bookingFlow.service_fee)
})

function formatPrice(priceCNY: number): string {
  return formatPriceWithDual(priceCNY, countryCode.value)
}

function showAgreement(type: string) {
  currentAgreementType.value = type
  agreementDialogVisible.value = true
}

function handleConfirm() {
  if (!allChecked.value) return
  emit('confirm')
}
</script>

<style scoped>
.step-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-title {
  font-size: 18px;
  font-weight: 700;
}

.card-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: normal;
  line-height: 1.6;
}

.property-info-box {
  background: #f5f7fa;
  border-radius: var(--radius);
  padding: 16px 20px;
  margin-bottom: 16px;
}

.info-row {
  display: flex;
  padding: 6px 0;
  font-size: 14px;
}

.info-label {
  color: var(--text-secondary);
  min-width: 100px;
}

.info-value {
  color: var(--text-primary);
  font-weight: 500;
  flex: 1;
}

.payment-info-box {
  background: #ecf5ff;
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 20px;
}

.payment-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 12px;
}

.payment-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  font-size: 14px;
  color: var(--text-primary);
}

.payment-row:last-child {
  font-size: 18px;
  font-weight: 700;
}

.payment-row:last-child span:last-child {
  color: var(--danger);
}

.payment-note {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 8px;
}

.agreements-list {
  margin-bottom: 20px;
}

.agreement-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--border-light);
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.agreement-item:last-child {
  border-bottom: none;
}

.agreement-num {
  font-weight: 600;
  margin-right: 4px;
}

.highlight-text {
  color: var(--danger);
}

.free-cancel-box {
  background: #f0f9eb;
  border-radius: var(--radius);
  padding: 14px 18px;
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.cancel-list {
  margin: 4px 0 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: normal;
}

.cancel-list li {
  padding: 3px 0;
}

.checkboxes-section {
  background: var(--bg-light);
  border-radius: var(--radius);
  padding: 14px 18px;
  margin-bottom: 20px;
}

.checkboxes-section :deep(.el-checkbox) {
  display: block;
  margin-bottom: 10px;
}

.checkboxes-section :deep(.el-checkbox:last-child) {
  margin-bottom: 0;
}

.step-footer {
  display: flex;
  justify-content: space-between;
  padding-top: 16px;
  border-top: 1px solid var(--border-light);
}
</style>
