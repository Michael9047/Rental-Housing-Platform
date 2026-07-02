<template>
  <div class="contract-page" v-loading="loading">
    <div class="page-header">
      <el-button text :icon="ArrowLeft" @click="$router.back()">返回</el-button>
      <h2>电子合同</h2>
    </div>

    <el-empty v-if="!loading && !contract && !booking" description="合同数据未找到" />

    <el-card v-if="!contract && booking" shadow="never" class="info-card">
      <div class="flow-header">
        <div>
          <h3>签约信息确认</h3>
          <p>预约 #{{ booking.id }} · 房源 #{{ booking.property_id }}</p>
        </div>
        <el-tag :type="contractInfoTag" round>{{ contractInfoLabel }}</el-tag>
      </div>

      <el-alert
        v-if="booking.contract_info_status !== 'confirmed'"
        type="info"
        show-icon
        :closable="false"
        class="info-alert"
        title="合同会在租客提交签约信息、房东确认后自动生成。"
      />

      <el-form
        v-if="canEditContractInfo"
        ref="formRef"
        :model="contractForm"
        :rules="rules"
        label-position="top"
        class="contract-info-form"
      >
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12">
            <el-form-item label="真实姓名" prop="contract_real_name">
              <el-input v-model="contractForm.contract_real_name" placeholder="请输入真实姓名" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="身份证号" prop="contract_id_card_no">
              <el-input v-model="contractForm.contract_id_card_no" placeholder="请输入身份证号" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :xs="24" :sm="12">
            <el-form-item label="联系电话" prop="contract_phone">
              <el-input v-model="contractForm.contract_phone" placeholder="请输入联系电话" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="租赁期限" prop="lease_dates">
              <el-date-picker
                v-model="leaseDates"
                type="daterange"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="补充约定">
          <el-input
            v-model="contractForm.contract_extra_terms"
            type="textarea"
            :rows="4"
            maxlength="2000"
            show-word-limit
            placeholder="例如付款周期、能否养宠、提前退租等，没有可不填"
          />
        </el-form-item>

        <div class="flow-actions">
          <el-button type="primary" :loading="submittingInfo" @click="submitContractInfo">
            提交给房东确认
          </el-button>
        </div>
      </el-form>

      <template v-else>
        <el-descriptions :column="2" border class="contract-meta">
          <el-descriptions-item label="租客姓名">{{ booking.contract_real_name || '未填写' }}</el-descriptions-item>
          <el-descriptions-item label="身份证号">{{ maskedIdCard }}</el-descriptions-item>
          <el-descriptions-item label="联系电话">{{ maskedPhone }}</el-descriptions-item>
          <el-descriptions-item label="租期">
            {{ booking.lease_start_date || '未填写' }} ~ {{ booking.lease_end_date || '未填写' }}
          </el-descriptions-item>
          <el-descriptions-item label="补充约定" :span="2">
            {{ booking.contract_extra_terms || '无' }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="canConfirmContractInfo" class="flow-actions">
          <el-button type="primary" :loading="confirmingInfo" @click="confirmContractInfo">
            确认并生成合同
          </el-button>
        </div>

        <el-result
          v-else-if="booking.contract_info_status === 'pending_landlord'"
          icon="info"
          title="等待房东确认"
          sub-title="房东确认租客信息和租期后，系统会生成电子合同。"
        />

        <div v-else-if="booking.contract_info_status === 'confirmed'" class="flow-actions">
          <el-button type="primary" :loading="generating" @click="generateConfirmedContract">
            生成电子合同
          </el-button>
        </div>
      </template>
    </el-card>

    <template v-if="contract">
      <el-card shadow="never" class="contract-card">
        <div class="contract-watermark">电子合同</div>

        <div class="contract-header">
          <h1>房屋租赁合同</h1>
          <p class="contract-no">合同编号：{{ contract.id }}</p>
          <el-tag :type="contract.status === 'signed' ? 'success' : 'warning'" round>
            {{ contract.status === 'signed' ? '已签署' : '待签署' }}
          </el-tag>
        </div>

        <el-divider />

        <el-descriptions :column="2" border class="contract-meta">
          <el-descriptions-item label="预约编号">#{{ contract.booking_id }}</el-descriptions-item>
          <el-descriptions-item label="房源编号">#{{ contract.property_id }}</el-descriptions-item>
          <el-descriptions-item label="租客编号">#{{ contract.tenant_id }}</el-descriptions-item>
          <el-descriptions-item label="模板">{{ contract.template_name }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(contract.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="签署时间">
            {{ contract.signed_at ? formatDate(contract.signed_at) : '未签署' }}
          </el-descriptions-item>
        </el-descriptions>

        <pre class="contract-content">{{ contract.content }}</pre>
      </el-card>

      <div class="download-bar">
        <el-button
          v-if="contract.status !== 'signed'"
          type="primary"
          size="large"
          round
          :loading="signing"
          @click="handleSign"
        >
          签署合同
        </el-button>
        <el-button size="large" round @click="handleDownload">下载合同文本</el-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { bookingService } from '@/services/booking'
import { contractService, type Contract } from '@/services/contract'
import { useAuthStore } from '@/stores/auth'
import type { Booking } from '@/types/booking'

const route = useRoute()
const authStore = useAuthStore()
const contract = ref<Contract | null>(null)
const booking = ref<Booking | null>(null)
const loading = ref(false)
const signing = ref(false)
const submittingInfo = ref(false)
const confirmingInfo = ref(false)
const generating = ref(false)
const formRef = ref<FormInstance>()

const contractForm = reactive({
  contract_real_name: '',
  contract_id_card_no: '',
  contract_phone: '',
  contract_extra_terms: '',
})
const leaseDates = ref<[string, string] | null>(null)

const rules: FormRules = {
  contract_real_name: [{ required: true, message: '请输入真实姓名', trigger: 'blur' }],
  contract_id_card_no: [{ required: true, message: '请输入身份证号', trigger: 'blur' }],
  contract_phone: [{ required: true, message: '请输入联系电话', trigger: 'blur' }],
  lease_dates: [
    {
      validator: (_rule, value, callback) => {
        if (!leaseDates.value?.[0] || !leaseDates.value?.[1]) callback(new Error('请选择租赁期限'))
        else callback()
      },
      trigger: 'change',
    },
  ],
}

const isTenant = computed(() => authStore.user?.role === 'tenant' || authStore.user?.role === 'admin')
const isLandlord = computed(() => authStore.user?.role === 'landlord' || authStore.user?.role === 'admin')
const canEditContractInfo = computed(() => {
  if (!booking.value || !isTenant.value) return false
  return booking.value.contract_info_status !== 'pending_landlord' && booking.value.contract_info_status !== 'confirmed'
})
const canConfirmContractInfo = computed(() => (
  !!booking.value
  && isLandlord.value
  && booking.value.contract_info_status === 'pending_landlord'
))

const contractInfoLabel = computed(() => {
  const status = booking.value?.contract_info_status
  if (status === 'pending_landlord') return '待房东确认'
  if (status === 'confirmed') return '已确认'
  return '待租客填写'
})

const contractInfoTag = computed(() => {
  const status = booking.value?.contract_info_status
  if (status === 'pending_landlord') return 'warning'
  if (status === 'confirmed') return 'success'
  return 'info'
})

const maskedIdCard = computed(() => {
  const id = booking.value?.contract_id_card_no || ''
  if (id.length <= 8) return id || '未填写'
  return `${id.slice(0, 3)}***********${id.slice(-4)}`
})

const maskedPhone = computed(() => {
  const phone = booking.value?.contract_phone || ''
  if (phone.length < 7) return phone || '未填写'
  return `${phone.slice(0, 3)}****${phone.slice(-4)}`
})

function formatDate(d: string): string {
  if (!d) return ''
  return new Date(d).toLocaleString('zh-CN')
}

async function loadContract() {
  const id = String(route.params.id || '')
  if (!id) return

  loading.value = true
  try {
    if (/^\d+$/.test(id)) {
      await loadBookingFlow(Number(id))
    } else {
      contract.value = await contractService.get(id)
    }
  } catch {
    contract.value = null
    booking.value = null
  } finally {
    loading.value = false
  }
}

function fillContractForm(source: Booking) {
  contractForm.contract_real_name = source.contract_real_name || authStore.user?.username || ''
  contractForm.contract_id_card_no = source.contract_id_card_no || ''
  contractForm.contract_phone = source.contract_phone || authStore.user?.phone || ''
  contractForm.contract_extra_terms = source.contract_extra_terms || ''
  leaseDates.value = source.lease_start_date && source.lease_end_date
    ? [source.lease_start_date, source.lease_end_date]
    : null
}

async function loadBookingFlow(bookingId: number) {
  booking.value = await bookingService.getById(bookingId)
  fillContractForm(booking.value)
  const existingContract = await contractService.getByBookingOptional(bookingId)
  if (existingContract) {
    contract.value = existingContract
    return
  }
  if (booking.value.contract_info_status === 'confirmed') {
    contract.value = await contractService.generate(bookingId)
  }
}

async function submitContractInfo() {
  if (!booking.value || !formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid || !leaseDates.value) return

  submittingInfo.value = true
  try {
    booking.value = await bookingService.updateContractInfo(booking.value.id, {
      contract_real_name: contractForm.contract_real_name,
      contract_id_card_no: contractForm.contract_id_card_no,
      contract_phone: contractForm.contract_phone,
      lease_start_date: leaseDates.value[0],
      lease_end_date: leaseDates.value[1],
      contract_extra_terms: contractForm.contract_extra_terms || undefined,
    })
    ElMessage.success('签约信息已提交，等待房东确认')
  } finally {
    submittingInfo.value = false
  }
}

async function confirmContractInfo() {
  if (!booking.value) return
  confirmingInfo.value = true
  try {
    booking.value = await bookingService.confirmContractInfo(booking.value.id)
    contract.value = await contractService.generate(booking.value.id)
    ElMessage.success('签约信息已确认，合同已生成')
  } finally {
    confirmingInfo.value = false
  }
}

async function generateConfirmedContract() {
  if (!booking.value) return
  generating.value = true
  try {
    contract.value = await contractService.generate(booking.value.id)
  } finally {
    generating.value = false
  }
}

async function handleSign() {
  if (!contract.value) return
  signing.value = true
  try {
    contract.value = await contractService.sign(contract.value.id)
    ElMessage.success('合同已签署')
  } catch {
    ElMessage.error('签署失败，请确认当前账号是否为合同租客')
  } finally {
    signing.value = false
  }
}

async function handleDownload() {
  if (!contract.value) return
  try {
    const content = await contractService.download(contract.value.id)
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `contract-${contract.value.id}.txt`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('合同下载失败')
  }
}

onMounted(loadContract)
</script>

<style scoped>
.contract-page {
  max-width: 860px;
  margin: 0 auto;
  padding-bottom: 80px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 22px;
  margin: 0;
}

.contract-card {
  border-radius: var(--radius) !important;
  position: relative;
  overflow: hidden;
  line-height: 1.8;
}

.info-card {
  border-radius: var(--radius) !important;
}

.flow-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.flow-header h3 {
  margin: 0 0 6px;
  font-size: 20px;
  color: var(--text-primary);
}

.flow-header p {
  margin: 0;
  font-size: 14px;
  color: var(--text-muted);
}

.info-alert {
  margin-bottom: 18px;
}

.contract-info-form {
  margin-top: 8px;
}

.flow-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 20px;
}

.contract-watermark {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotate(-25deg);
  font-size: 120px;
  font-weight: 900;
  color: rgba(64, 158, 255, 0.04);
  pointer-events: none;
  white-space: nowrap;
  z-index: 0;
}

.contract-header,
.contract-meta,
.contract-content {
  position: relative;
  z-index: 1;
}

.contract-header {
  text-align: center;
  padding: 20px 0 10px;
}

.contract-header h1 {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.contract-no {
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.contract-content {
  margin-top: 20px;
  padding: 18px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text-primary);
  font-family: inherit;
  font-size: 14px;
  white-space: pre-wrap;
}

.download-bar {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 20px;
}

@media print {
  .page-header,
  .download-bar,
  .info-card {
    display: none !important;
  }

  .contract-card {
    box-shadow: none !important;
    border: 1px solid #ddd !important;
  }

  .contract-watermark {
    color: rgba(0, 0, 0, 0.03) !important;
  }
}

@media (max-width: 640px) {
  .flow-header {
    flex-direction: column;
  }

  .flow-actions,
  .download-bar {
    flex-direction: column;
  }
}
</style>
