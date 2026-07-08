<template>
  <div class="booking-flow-page" v-loading="loading">
    <div class="page-header">
      <el-button text :icon="ArrowLeft" @click="handleBack">返回</el-button>
      <h2>预订房源</h2>
    </div>

    <!-- Steps Indicator -->
    <el-steps :active="activeStep" finish-status="success" align-center class="flow-steps">
      <el-step title="选择起租日" />
      <el-step title="选择租期" />
      <el-step title="填写个人信息" />
      <el-step title="确认协议" />
      <el-step title="支付" />
    </el-steps>

    <!-- Property Summary -->
    <el-card v-if="bookingFlow.property" shadow="never" class="property-summary-card">
      <div class="summary-row">
        <div class="summary-left">
          <div class="summary-title">{{ bookingFlow.property.title }}</div>
          <div class="summary-addr">{{ bookingFlow.property.address }}</div>
        </div>
        <div class="summary-right">
          <div class="summary-price">
            <span class="price-num">{{ formatPrice(Number(bookingFlow.property.price_monthly) || 0) }}</span>
            <span class="price-unit">/月</span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- Step 1: Start Date -->
    <div v-if="activeStep === 1">
      <StartDateStep @next="handleNextDate" />
    </div>

    <!-- Step 2: Lease Duration -->
    <div v-if="activeStep === 2">
      <LeaseStep @prev="bookingFlow.prevStep" @next="handleNextLease" />
    </div>

    <!-- Step 3: Personal Info (3 sub-steps) -->
    <div v-if="activeStep === 3">
      <PersonalInfoStep
        @prev="handleInfoPrev"
        @next="handleInfoNext"
      />
    </div>

    <!-- Step 4: Agreements -->
    <div v-if="activeStep === 4">
      <AgreementStep @prev="bookingFlow.prevStep" @confirm="handleConfirmAgreements" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { usePropertyStore } from '@/stores/property'
import { useBookingFlowStore } from '@/stores/bookingFlow'
import { useAuthStore } from '@/stores/auth'
import { formatPriceWithDual } from '@/data/currency'
import StartDateStep from '@/components/booking/StartDateStep.vue'
import LeaseStep from '@/components/booking/LeaseStep.vue'
import PersonalInfoStep from '@/components/booking/PersonalInfoStep.vue'
import AgreementStep from '@/components/booking/AgreementStep.vue'
import { bookingService } from '@/services/booking'

const route = useRoute()
const router = useRouter()
const propertyStore = usePropertyStore()
const bookingFlow = useBookingFlowStore()
const authStore = useAuthStore()

const loading = ref(false)

const countryCode = computed(() => bookingFlow.property?.country || 'CN')

function formatPrice(priceCNY: number): string {
  return formatPriceWithDual(priceCNY, countryCode.value)
}

const activeStep = computed(() => {
  if (bookingFlow.current_step === 3) return 3
  return bookingFlow.current_step
})

const propertyId = computed(() => {
  return Number(route.query.property_id) || bookingFlow.property?.id || 0
})

async function loadProperty() {
  if (!propertyId.value) {
    ElMessage.error('房源信息异常，请从房源详情页重新进入')
    router.push('/')
    return
  }

  if (bookingFlow.property && bookingFlow.property.id === propertyId.value) {
    return
  }

  loading.value = true
  try {
    const property = await propertyStore.fetchById(propertyId.value)
    if (property) {
      bookingFlow.setProperty(property)
      if (authStore.user) {
        bookingFlow.prefillFromUser(authStore.user)
      }
    }
  } catch {
    ElMessage.error('加载房源信息失败')
  } finally {
    loading.value = false
  }
}

function handleNextDate() {
  bookingFlow.nextStep()
}

function handleNextLease() {
  bookingFlow.nextStep()
}

function handleInfoPrev() {
  bookingFlow.prevStep()
}

function handleInfoNext() {
  bookingFlow.nextStep()
}

async function handleConfirmAgreements() {
  if (!bookingFlow.property) return
  loading.value = true
  try {
    const result = await bookingService.create({
      property_id: bookingFlow.property.id,
      message: '',
      scheduled_date: bookingFlow.start_date,
      deposit_amount: bookingFlow.deposit_amount,
      service_fee: bookingFlow.service_fee,
      // @ts-ignore
      lease_months: bookingFlow.lease_months,
      // @ts-ignore
      application_data: {
        applicant: bookingFlow.applicant,
        guarantor: bookingFlow.guarantor,
        emergency: bookingFlow.emergency,
      },
    })
    ElMessage.success('申请提交成功，请完成支付')
    bookingFlow.reset()
    router.push(`/booking/payment/${result.id}/deposit`)
  } catch (err: any) {
    const status = err?.response?.status
    const detail = err?.response?.data?.detail
    if (status === 409) {
      ElMessage.warning('您已对该房源发起过预约')
    } else if (detail && typeof detail === 'string') {
      ElMessage.error(detail)
    } else {
      ElMessage.error('提交失败，请重试')
    }
  } finally {
    loading.value = false
  }
}

function handleBack() {
  if (bookingFlow.current_step > 1) {
    bookingFlow.prevStep()
  } else {
    router.back()
  }
}



onMounted(() => {
  loadProperty()
})
</script>

<style scoped>
.booking-flow-page {
  max-width: 960px;
  margin: 0 auto;
  padding-bottom: 40px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 22px;
  margin: 0;
}

.flow-steps {
  margin-bottom: 24px;
}

.property-summary-card {
  margin-bottom: 20px;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.summary-left {
  flex: 1;
}

.summary-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.summary-addr {
  font-size: 13px;
  color: var(--text-muted);
}

.summary-price {
  text-align: right;
}

.price-num {
  font-size: 24px;
  font-weight: 700;
  color: var(--danger);
}

.price-unit {
  font-size: 13px;
  color: var(--text-muted);
  margin-left: 2px;
}
</style>
