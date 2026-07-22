<!-- 预订流程统一布局，提供步骤指示和前进、返回导航。 -->
<template>
  <div class="booking-flow-shell">
    <el-card shadow="never" class="flow-card">
      <div class="flow-heading">
        <div>
          <p class="flow-eyebrow">房源预订</p>
          <h1>{{ title }}</h1>
        </div>
        <el-button text @click="goBack">退出流程</el-button>
      </div>

      <div class="flow-steps-scroll">
        <el-steps :active="currentStep" finish-status="success" align-center class="flow-steps">
          <el-step v-for="step in steps" :key="step" :title="step" />
        </el-steps>
      </div>

      <div class="flow-content">
        <slot />
      </div>

      <div class="flow-actions">
        <el-button size="large" @click="goPrevious">{{ previousLabel }}</el-button>
        <el-button v-if="nextRoute" type="primary" size="large" :disabled="nextDisabled" @click="goNext">
          {{ nextLabel }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

const props = withDefaults(defineProps<{
  title: string
  currentStep: number
  previousRoute?: string
  nextRoute?: string
  nextDisabled?: boolean
  manualNext?: boolean
  previousLabel?: string
  nextLabel?: string
}>(), {
  previousLabel: '返回',
  nextLabel: '下一步',
})

const emit = defineEmits<{
  (event: 'next'): void
}>()

const route = useRoute()
const router = useRouter()
const steps = ['入住日期', '租期选择', '个人信息', '紧急联系人', '信息确认与授权', '合同']

function routeParams() {
  return { propertyId: String(route.params.propertyId) }
}

function goPrevious() {
  if (props.previousRoute) {
    router.push({ name: props.previousRoute, params: routeParams() })
    return
  }
  router.push({ name: 'property-detail', params: { id: routeParams().propertyId } })
}

function goNext() {
  if (!props.nextRoute) return
  if (props.manualNext) {
    emit('next')
    return
  }
  router.push({ name: props.nextRoute, params: routeParams() })
}

function goBack() {
  router.push({ name: 'property-detail', params: { id: routeParams().propertyId } })
}
</script>

<style scoped>
.booking-flow-shell {
  width: min(calc(100% - 48px), 1160px);
  max-width: 1160px;
  margin: 0 auto;
  padding: 12px 0 40px;
}

.flow-card {
  border-radius: var(--radius);
}

.flow-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.flow-heading h1 {
  margin: 4px 0 0;
  font-size: 26px;
}

.flow-eyebrow {
  margin: 0;
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
}

.flow-steps {
  margin: 32px 0;
}

.flow-steps-scroll {
  max-width: 100%;
}

.flow-steps :deep(.el-step) {
  flex: 1 0 calc(100% / 6);
  min-width: 0;
}

.flow-steps :deep(.el-step__title) {
  white-space: nowrap;
}

.flow-content {
  min-height: 280px;
  padding: 32px;
  border: 1px dashed var(--border);
  border-radius: var(--radius);
  background: var(--bg-light);
}

.flow-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 24px;
}

@media (max-width: 768px) {
  .booking-flow-shell {
    width: min(calc(100% - 24px), 1160px);
  }

  .flow-steps-scroll {
    overflow-x: auto;
    padding-bottom: 8px;
  }

  .flow-steps {
    min-width: 760px;
  }

  .flow-steps :deep(.el-step) {
    min-width: 126px;
  }

  .flow-content {
    padding: 20px;
  }
}
</style>
