<template>
  <main class="contract-detail" v-loading="loading">
    <el-result v-if="error" icon="error" title="无法查看合同" :sub-title="error">
      <template #extra><el-button @click="router.push('/profile?tab=contracts')">返回我的合同</el-button></template>
    </el-result>
    <template v-else-if="contract">
      <div class="page-actions">
        <el-button @click="router.push('/profile?tab=contracts')">返回我的合同</el-button>
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
          <div><dt>预订状态</dt><dd>{{ contract.reservation_status === 'confirmed' ? '预订成功' : '预订未成功' }}</dd></div>
          <div><dt>房源</dt><dd><router-link :to="`/property/${contract.property_id}`">{{ contract.property_name }}</router-link></dd></div>
        </dl>
      </el-card>

      <article class="agreement-paper">
        <p class="template-notice">业务开发模板，待房源所在地法务审核</p>
        <template v-if="contract.snapshot?.sections?.length">
          <section v-for="section in contract.snapshot.sections" :key="section.number" class="agreement-section">
            <h2>{{ section.title_zh }}</h2><h3>{{ section.title_en }}</h3>
            <p>{{ section.zh }}</p><p class="english">{{ section.en }}</p>
          </section>
        </template>
        <pre v-else class="locked-content">{{ contract.content }}</pre>
        <section class="signature-block">
          <h2>租客电子签名 / Tenant Electronic Signature</h2>
          <img v-if="signatureObjectUrl" :src="signatureObjectUrl" alt="租客签署时锁定的电子签名" />
          <p>签署时间 / Signed At: {{ formatDateTime(contract.signed_at) }}</p>
          <p>合同版本及哈希 / Agreement Version and Hash: v{{ contract.agreement_version }} · {{ contract.agreement_content_hash }}</p>
        </section>
      </article>
    </template>
  </main>
</template>

<script setup lang="ts">
// 本页面只读取签署时锁定的合同快照，不重新生成或修改合同。
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { contractService, type TenantContractDetail } from '@/services/contract'

const route = useRoute()
const router = useRouter()
const loading = ref(true)
const error = ref('')
const contract = ref<TenantContractDetail | null>(null)
const signatureObjectUrl = ref('')

const paymentLabel = computed(() => contract.value?.status_labels[0] || contract.value?.payment_status || '未知')

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

async function loadContract() {
  try {
    const id = String(route.params.id)
    contract.value = await contractService.getMine(id)
    try {
      const signature = await contractService.getSignature(id)
      signatureObjectUrl.value = URL.createObjectURL(signature)
    } catch {
      // 合同正文仍可查看；签名文件暂不可用时不掩盖合同元数据。
    }
  } catch (reason: any) {
    error.value = reason?.response?.status === 404 ? '合同不存在或您无权查看。' : '合同暂时无法加载，请稍后重试。'
  } finally {
    loading.value = false
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
onBeforeUnmount(() => { if (signatureObjectUrl.value) URL.revokeObjectURL(signatureObjectUrl.value) })
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
.agreement-paper { padding: 48px 58px; border: 1px solid var(--border); background: #fff; box-shadow: 0 8px 28px rgb(0 0 0 / 6%); }
.template-notice { padding: 10px; text-align: center; color: #ad6800; background: #fffbe6; }
.agreement-section { margin: 30px 0; page-break-inside: avoid; } .agreement-section h2 { margin: 0; font-size: 18px; } .agreement-section h3 { margin: 4px 0 14px; font-size: 15px; color: #555; }
.agreement-section p { line-height: 1.75; white-space: pre-wrap; } .english { color: #444; }
.locked-content { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.75; }
.signature-block { margin-top: 44px; padding-top: 24px; border-top: 1px solid #bbb; } .signature-block img { display: block; width: min(420px, 100%); max-height: 180px; margin: 18px 0; object-fit: contain; object-position: left center; }
@media (max-width: 768px) { .contract-detail { width: min(100% - 20px, 980px); } .agreement-paper { padding: 26px 20px; } .meta-grid { grid-template-columns: 1fr; } .hash { grid-column: auto; } .title-row { flex-direction: column; } }
</style>
