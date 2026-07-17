<template>
  <el-card shadow="never" class="step-card">
    <template #header>
      <div class="card-header">
        <span class="card-title">📋 填写个人信息</span>
        <span class="card-subtitle">
          第 {{ localSubStep }}/3 步：{{ stepTitle }}
        </span>
      </div>
    </template>

    <!-- Info bar -->
    <div class="info-bar" v-if="bookingFlow.lease_months > 0">
      <div class="info-row">
        <span>租期：{{ bookingFlow.lease_months }}个月</span>
        <span>起租日：{{ bookingFlow.start_date }}</span>
      </div>
      <div class="info-price">
        总租金：<span class="price">{{ formatPrice(bookingFlow.total_price) }}</span>
      </div>
    </div>

    <!-- Sub Steps Tabs -->
    <el-tabs v-model="localSubStep" class="info-tabs" @tab-change="onTabChange">
      <el-tab-pane label="申请人信息" :name="1" />
      <el-tab-pane label="担保人信息" :name="2" />
      <el-tab-pane label="紧急联系人" :name="3" />
    </el-tabs>

    <!-- Step 1: Applicant -->
    <div v-show="localSubStep === 1">
      <ApplicantForm ref="applicantFormRef" />
    </div>

    <!-- Step 2: Guarantor -->
    <div v-show="localSubStep === 2">
      <GuarantorForm ref="guarantorFormRef" />
    </div>

    <!-- Step 3: Emergency -->
    <div v-show="localSubStep === 3">
      <EmergencyForm ref="emergencyFormRef" />
    </div>

    <div class="step-footer">
      <el-button size="large" @click="handlePrev">
        上一步
      </el-button>
      <el-button type="primary" size="large" @click="handleNext">
        {{ nextButtonText }}
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useBookingFlowStore } from '@/stores/bookingFlow'
import { formatPriceWithDual } from '@/data/currency'
import ApplicantForm from '@/components/booking/ApplicantForm.vue'
import GuarantorForm from '@/components/booking/GuarantorForm.vue'
import EmergencyForm from '@/components/booking/EmergencyForm.vue'

const emit = defineEmits<{
  (e: 'prev'): void
  (e: 'next'): void
}>()

const bookingFlow = useBookingFlowStore()

const applicantFormRef = ref<InstanceType<typeof ApplicantForm>>()
const guarantorFormRef = ref<InstanceType<typeof GuarantorForm>>()
const emergencyFormRef = ref<InstanceType<typeof EmergencyForm>>()

const localSubStep = ref(1)

const countryCode = computed(() => bookingFlow.property?.country || 'CN')

function formatPrice(priceCNY: number): string {
  return formatPriceWithDual(priceCNY, countryCode.value)
}

const stepTitle = computed(() => {
  const titles: Record<number, string> = {
    1: '申请人基本信息',
    2: '担保人信息',
    3: '紧急联系人信息',
  }
  return titles[localSubStep.value] || ''
})

const nextButtonText = computed(() => {
  if (localSubStep.value === 1) return '下一步：担保人信息 →'
  if (localSubStep.value === 2) return '下一步：紧急联系人 →'
  return '下一步：确认协议 →'
})

function onTabChange(name: string | number) {
  // tab 切换只做展示用，不直接改步骤
}

function validateCurrentStep(): boolean {
  if (localSubStep.value === 1) {
    const result = applicantFormRef.value?.validate() ?? false
    if (!result) {
      ElMessage.warning('请完善申请人信息的必填项')
    }
    return result
  }
  if (localSubStep.value === 2) {
    const result = guarantorFormRef.value?.validate() ?? false
    if (!result) {
      ElMessage.warning('请完善担保人信息的必填项')
    }
    return result
  }
  if (localSubStep.value === 3) {
    const result = emergencyFormRef.value?.validate() ?? false
    if (!result) {
      ElMessage.warning('请完善紧急联系人的必填项')
    }
    return result
  }
  return true
}

function handlePrev() {
  if (localSubStep.value === 1) {
    emit('prev')
  } else {
    localSubStep.value = localSubStep.value - 1
  }
}

function handleNext() {
  if (!validateCurrentStep()) {
    ElMessage.warning('请完善当前页面的必填项')
    return
  }

  if (localSubStep.value === 3) {
    emit('next')
  } else {
    localSubStep.value = localSubStep.value + 1
  }
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
  font-size: 16px;
  font-weight: 600;
}

.card-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: normal;
}

.info-bar {
  background: linear-gradient(135deg, var(--primary-light) 0%, #e8f4ff 100%);
  border-radius: var(--radius);
  padding: 14px 20px;
  margin-bottom: 20px;
}

.info-row {
  display: flex;
  gap: 24px;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.info-price {
  font-size: 14px;
  color: var(--text-primary);
}

.info-price .price {
  color: var(--danger);
  font-weight: 700;
  font-size: 18px;
}

.info-tabs {
  margin-bottom: 20px;
}

.step-footer {
  display: flex;
  justify-content: space-between;
  padding-top: 16px;
  border-top: 1px solid var(--border-light);
}
</style>
