<template>
  <main class="contract-detail" v-loading="loading">
    <el-result v-if="error" icon="error" title="无法查看合同" :sub-title="error">
      <template #extra><el-button @click="router.push(backPath)">{{ backLabel }}</el-button></template>
    </el-result>
    <template v-else-if="contract">
      <div class="page-actions">
        <el-button @click="router.push(backPath)">{{ backLabel }}</el-button>
        <el-button :disabled="!contract.signed_pdf_available" @click="downloadPdf">下载已签署 PDF</el-button>
      </div>
      <el-card shadow="never" class="summary-card">
        <div class="title-row">
          <div><h1>房屋预订及租赁协议</h1><p>Housing Reservation and Tenancy Agreement</p></div>
          <el-tag size="large">{{ contract.category_label }}</el-tag>
        </div>
        <el-alert v-if="contract.invalid_reason" type="warning" :closable="false" :title="contract.invalid_reason" />
        <dl class="meta-grid">
          <div><dt>合同编号</dt><dd>{{ contract.agreement_number }}</dd></div>
          <div><dt>订单编号</dt><dd>{{ contract.order_id }}</dd></div>
          <div><dt>合同版本</dt><dd>v{{ contract.agreement_version }}</dd></div>
          <div><dt>签署时间</dt><dd>{{ formatDateTime(contract.signed_at) }}</dd></div>
          <div class="hash"><dt>合同哈希</dt><dd>{{ contract.agreement_content_hash }}</dd></div>
          <div><dt>合同状态</dt><dd>{{ contract.category_label }}</dd></div>
          <div><dt>支付状态</dt><dd>{{ paymentLabel }}</dd></div>
          <div><dt>预订状态</dt><dd>{{ contract.booking_status === 'confirmed' ? '预订成功' : '预订未成功' }}</dd></div>
          <div><dt>房源</dt><dd><router-link :to="`/property/${contract.property_id}`">{{ contract.property_name }}</router-link></dd></div>
        </dl>
      </el-card>

      <section class="pdf-preview" v-loading="pdfLoading" element-loading-text="正在加载已签署合同">
        <iframe
          v-if="pdfObjectUrl"
          :src="pdfObjectUrl"
          :title="`${contract.agreement_number} 已签署合同 PDF`"
          class="pdf-frame"
        />
        <el-result
          v-else-if="pdfError"
          icon="warning"
          title="合同预览暂不可用"
          :sub-title="pdfError"
        >
          <template #extra>
            <el-button :disabled="!contract.signed_pdf_available" @click="loadPdfPreview">重新加载</el-button>
            <el-button type="primary" :disabled="!contract.signed_pdf_available" @click="downloadPdf">下载已签署 PDF</el-button>
          </template>
        </el-result>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
// 本页面预览并下载同一份已签署 PDF，不再重新渲染历史合同模板正文。
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { contractService, type TenantContractDetail } from '@/services/contract'
import { extractErrorMessage } from '@/services/api'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const loading = ref(true)
const error = ref('')
const contract = ref<TenantContractDetail | null>(null)
const pdfLoading = ref(false)
const pdfError = ref('')
const pdfObjectUrl = ref('')
const isBm = computed(() => authStore.user?.role === 'landlord')
const backPath = computed(() => isBm.value ? '/contracts/landlord' : '/profile?tab=contracts')
const backLabel = computed(() => isBm.value ? '返回合约管理' : '返回我的合同')

const paymentLabel = computed(() => contract.value?.status_labels[0] || contract.value?.payment_status || '未知')

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

async function loadContract() {
  try {
    const id = String(route.params.id)
    contract.value = isBm.value
      ? await contractService.getManaged(id)
      : await contractService.getMine(id)
    await loadPdfPreview()
  } catch (reason: any) {
    const status = reason?.response?.status
    const detail = extractErrorMessage(reason)
    error.value = status === 404
      ? '合同不存在或您无权查看。'
      : status === 401
        ? '登录状态已失效，请重新登录。'
        : detail || '合同暂时无法加载，请稍后重试。'
  } finally {
    loading.value = false
  }
}

async function loadPdfPreview() {
  if (!contract.value) return
  if (!contract.value.signed_pdf_available) {
    pdfError.value = '已签署 PDF 正在生成，请稍后重新加载。'
    return
  }
  pdfLoading.value = true
  pdfError.value = ''
  try {
    const link = await contractService.getSignedDownloadLink(contract.value.agreement_id)
    if (!link.url) {
      pdfError.value = link.message || '已签署 PDF 正在生成，请稍后重新加载。'
      return
    }
    const response = await fetch(link.url, { credentials: 'same-origin' })
    if (!response.ok) throw new Error(`PDF 请求失败：${response.status}`)
    const pdf = await response.blob()
    if (pdfObjectUrl.value) URL.revokeObjectURL(pdfObjectUrl.value)
    pdfObjectUrl.value = URL.createObjectURL(pdf)
  } catch {
    pdfError.value = '无法加载已签署 PDF，您仍可尝试直接下载。'
  } finally {
    pdfLoading.value = false
  }
}

async function downloadPdf() {
  if (!contract.value) return
  try {
    const link = await contractService.getSignedDownloadLink(contract.value.agreement_id)
    if (!link.url) { ElMessage.info(link.message || '签署版 PDF 正在生成'); return }
    window.location.assign(link.url)
  } catch {
    ElMessage.error('合同下载失败，请稍后重试')
  }
}

onMounted(loadContract)
onBeforeUnmount(() => { if (pdfObjectUrl.value) URL.revokeObjectURL(pdfObjectUrl.value) })
</script>

<style scoped>
.contract-detail { width: min(980px, calc(100% - 32px)); min-height: 60vh; margin: 28px auto 60px; }
.page-actions { display: flex; justify-content: space-between; margin-bottom: 16px; }
.summary-card { margin-bottom: 20px; }
.title-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }
h1 { margin: 0 0 6px; font-size: 25px; } .title-row p { margin: 0 0 18px; color: var(--text-muted); }
.meta-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 32px; margin: 20px 0 0; }
.meta-grid div { min-width: 0; } dt { color: var(--text-muted); font-size: 13px; } dd { margin: 5px 0 0; overflow-wrap: anywhere; }
.hash { grid-column: 1 / -1; }
.pdf-preview { min-height: 72vh; overflow: hidden; border: 1px solid var(--border); border-radius: 8px; background: #f5f6f8; box-shadow: 0 8px 28px rgb(0 0 0 / 6%); }
.pdf-frame { display: block; width: 100%; height: 78vh; min-height: 640px; border: 0; background: #fff; }
@media (max-width: 768px) { .contract-detail { width: min(100% - 20px, 980px); } .meta-grid { grid-template-columns: 1fr; } .hash { grid-column: auto; } .title-row { flex-direction: column; } .pdf-frame { height: 70vh; min-height: 520px; } }
</style>
