<!-- 订单不可变快照生成的中英双语合同阅读、打印和 PDF 下载页。 -->
<template>
  <BookingFlowLayout title="合同 / Agreement" :current-step="5" previous-label="返回信息确认">
    <div v-loading="loading" class="contract-shell">
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" />
      <template v-if="contract && snapshot">
        <div class="contract-actions no-print">
          <span>合同版本 V{{ contract.version }} · {{ contract.status }}</span>
          <div><el-button @click="printContract">打印 / Print</el-button><el-button type="primary" :loading="downloading" @click="downloadPdf">下载 PDF / Download PDF</el-button></div>
        </div>

        <article class="contract-document">
          <header>
            <h1>房屋预订及租赁协议</h1>
            <h2>Housing Reservation and Tenancy Agreement</h2>
            <p class="development-notice">{{ value('development_notice') }}</p>
          </header>

          <table class="cover-fields">
            <tbody><tr v-for="field in coverFields" :key="field.label"><th>{{ field.label }}</th><td>{{ field.value || '—' }}</td></tr></tbody>
          </table>

          <section v-for="section in snapshot.sections" :key="section.number" class="clause">
            <h3>第{{ section.number }}条 {{ section.title_zh }}</h3>
            <h4>Article {{ section.number }} {{ section.title_en }}</h4>
            <p>{{ section.zh }}</p><p class="english">{{ section.en }}</p>
          </section>

          <section class="signature-section">
            <div class="signature-box">
              <strong>租客 / Tenant</strong>
              <p>租客姓名 / Tenant Name</p><div class="signature-line">{{ value('tenant_name_cn') }} / {{ value('tenant_name_en') }}</div>
              <p>租客电子签名 / Tenant Electronic Signature</p><div class="signature-line"></div>
              <p>签署时间 / Signed At</p><div class="signature-line"></div>
            </div>
            <div class="signature-box">
              <strong>出租方或供应方 / Provider</strong>
              <p>{{ value('provider_name') }}</p><p>{{ value('provider_execution_mode') }}</p>
              <p>本文件不包含伪造签名或印章。<br>No signature or seal is represented by this document.</p>
            </div>
          </section>
          <p class="record">合同版本及哈希 / Agreement Version and Hash: V{{ contract.version }} · {{ contract.content_hash }}<br>平台记录 / Platform Record: {{ value('platform_name') }} · {{ contract.generated_at }}</p>
          <section class="tenant-signing no-print">
            <h3>租客电子签名 / Tenant Electronic Signature</h3>
            <template v-if="contract.status !== 'signed'">
              <p>租客法定姓名 / Tenant Legal Name：<strong>{{ value('tenant_name_cn') }}</strong></p>
              <el-checkbox v-model="nameConfirmed">我确认上述姓名与本人有效身份证件一致。</el-checkbox>
              <SignaturePad ref="signaturePadRef" @change="signatureStrokes = $event" />
              <el-checkbox v-model="signatureConsent">我已阅读并同意使用电子签名签署本合同</el-checkbox>
              <div class="sign-actions"><el-button @click="router.push({ name: 'booking-review', params: route.params })">返回确认页</el-button><el-button type="primary" :loading="signing" :disabled="!canSign" @click="confirmSigning">确认签署合同</el-button></div>
            </template>
            <el-result v-else icon="success" title="合同已确认并锁定" :sub-title="`签署时间：${contract.signed_at || ''}`" />
          </section>
        </article>
      </template>
    </div>
  </BookingFlowLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import BookingFlowLayout from '@/components/booking/BookingFlowLayout.vue'
import SignaturePad, { type SignaturePoint } from '@/components/booking/SignaturePad.vue'
import { bookingService } from '@/services/booking'
import { contractService, type Contract, type ContractSnapshot } from '@/services/contract'

const route = useRoute(); const router = useRouter()
const contract = ref<Contract | null>(null); const loading = ref(false); const downloading = ref(false); const errorMessage = ref('')
const signatureStrokes = ref<SignaturePoint[][]>([]); const signatureConsent = ref(false); const nameConfirmed = ref(false); const signing = ref(false)
const signaturePadRef = ref<InstanceType<typeof SignaturePad> | null>(null)
const idempotencyKey = crypto.randomUUID()
const snapshot = computed<ContractSnapshot | null>(() => contract.value?.snapshot || null)
const signatureMetrics = computed(() => { const points = signatureStrokes.value.flat(); let length = 0; signatureStrokes.value.forEach((stroke) => stroke.slice(1).forEach((point, index) => { const previous = stroke[index]; length += Math.hypot(point.x - previous.x, point.y - previous.y) })); return { points: points.length, length } })
const canSign = computed(() => Boolean(contract.value?.content_hash && nameConfirmed.value && signatureConsent.value && signatureMetrics.value.points >= 8 && signatureMetrics.value.length >= 0.2))
function value(key: string) { return String(snapshot.value?.[key] ?? '') }
const coverFields = computed(() => [
  ['合同编号 / Agreement Number', value('agreement_number')], ['订单编号 / Order Number', value('order_number')],
  ['合同版本 / Agreement Version', `V${value('agreement_version')}`], ['生成日期 / Generated Date', value('generated_at')],
  ['出租方或房源供应方全称 / Landlord or Accommodation Provider', value('provider_name')],
  ['平台名称及平台角色 / Platform and Its Role', `${value('platform_name')} — ${value('platform_role')}`],
  ['租客中文姓名和护照英文姓名 / Tenant Name', `${value('tenant_name_cn')} / ${value('tenant_name_en')}`],
  ['房源名称 / Property Name', value('property_name')], ['房源完整地址 / Property Address', value('property_address')],
  ['房源编号 / Property ID', value('property_id')], ['房型 / Room Type', value('room_type')],
  ['入住日期 / Commencement Date', value('commencement_date')], ['租赁终止日期 / Expiry Date', value('expiry_date')],
  ['租期 / Tenancy Term', `${value('tenancy_months')} 个月 / month(s)`], ['每月租金 / Monthly Rent', value('monthly_rent')],
  ['押金 / Deposit', value('deposit')], ['服务费 / Service Fee', value('service_fee')],
  ['当前应付金额 / Amount Due Now', value('amount_due_now')], ['计费币种 / Settlement Currency', value('settlement_currency')],
  ['人民币参考金额 / CNY Reference Amount', value('cny_reference_amount')],
  ['汇率及时间 / Exchange Rate and Timestamp', `${value('exchange_rate')} · ${value('exchange_rate_at')} · ${value('exchange_rate_source')}`],
].map(([label, fieldValue]) => ({ label, value: fieldValue })))

function printContract() { window.print() }
async function downloadPdf() {
  if (!contract.value) return
  downloading.value = true
  try {
    const blob = await contractService.download(contract.value.id); const url = URL.createObjectURL(blob)
    const link = document.createElement('a'); link.href = url; link.download = `${contract.value.agreement_number}.pdf`; link.click(); URL.revokeObjectURL(url)
  } catch { ElMessage.error('PDF 下载失败，请稍后重试') } finally { downloading.value = false }
}

async function confirmSigning() {
  if (!contract.value || !canSign.value) { ElMessage.warning('请完整签名并确认姓名及电子签名同意事项'); return }
  try { await ElMessageBox.confirm('签署后合同内容将被锁定，并进入押金支付步骤。是否确认？', '确认签署合同', { confirmButtonText: '确认签署', cancelButtonText: '返回检查', type: 'warning' }) } catch { return }
  signing.value = true
  try {
    const bookingId = Number(route.query.booking_id)
    const result = await contractService.confirmSignature(contract.value.id, { agreement_version: contract.value.version, agreement_content_hash: contract.value.content_hash!, tenant_name: value('tenant_name_cn'), consent_text_version: '2026.1', idempotency_key: idempotencyKey, strokes: signatureStrokes.value, name_confirmed: nameConfirmed.value, electronic_signature_consent: signatureConsent.value })
    contract.value = { ...contract.value, status: 'signed', signed_at: result.signed_at }
    ElMessage.success(result.pdf_status === 'pending' ? '合同已签署，签署版PDF正在生成' : '合同签署成功，合同内容已锁定')
    await router.push(`/booking/payment/${bookingId}/deposit`)
  } catch (error: any) {
    const data = error?.response?.data || {}; const code = data.code || data.detail?.code || 'SIGNING_ERROR'; const message = data.message || data.detail?.message || data.detail || '合同签署暂时不可用，请稍后重试'
    if (data.request_id) console.warn(`[contract-sign] request_id=${data.request_id} code=${code}`)
    if (code === 'AGREEMENT_VERSION_MISMATCH') {
      ElMessage.error('合同内容已更新，请重新阅读最新版本后签署')
      signaturePadRef.value?.clear(); signatureStrokes.value = []; nameConfirmed.value = false; signatureConsent.value = false
      contract.value = await contractService.getByBooking(Number(route.query.booking_id))
    } else ElMessage.error(String(message))
  }
  finally { signing.value = false }
}

onMounted(async () => {
  const bookingId = Number(route.query.booking_id); if (!bookingId) { router.replace({ name: 'booking-review', params: route.params }); return }
  loading.value = true
  try {
    const booking = await bookingService.getById(bookingId)
    if (booking.property_id !== Number(route.params.propertyId)) throw new Error('订单与房源不匹配')
    try { contract.value = await contractService.getByBooking(bookingId) }
    catch (contractError: any) { if (contractError?.response?.status === 404) contract.value = await contractService.generate(bookingId); else throw contractError }
    if (contract.value.snapshot?.agreement_version !== contract.value.version || contract.value.snapshot?.content_hash !== contract.value.content_hash) throw new Error('合同快照版本或哈希不一致，请刷新后重试')
  } catch (error: any) { errorMessage.value = error?.response?.data?.detail || error?.message || '合同加载失败' }
  finally { loading.value = false }
})
</script>

<style scoped>
.contract-shell{max-width:980px;margin:0 auto}.contract-actions{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;padding:12px 16px;background:#f5f6f8;border-radius:8px}.contract-document{padding:48px 56px;background:#fff;border:1px solid #d8d8d8;box-shadow:0 4px 22px rgba(0,0,0,.08);font-family:"Noto Sans CJK SC","Microsoft YaHei","SimSun",sans-serif;color:#171717;line-height:1.72}.contract-document header{text-align:center;border-bottom:2px solid #222;padding-bottom:18px;margin-bottom:22px}.contract-document h1{margin:0;font-family:"Noto Serif CJK SC","SimSun",serif;font-size:30px}.contract-document h2{margin:4px 0 0;font-size:20px}.development-notice{color:#9a5b00;font-size:13px}.cover-fields{width:100%;border-collapse:collapse;table-layout:fixed;margin-bottom:26px}.cover-fields th,.cover-fields td{border:1px solid #777;padding:8px 10px;text-align:left;vertical-align:top;overflow-wrap:anywhere}.cover-fields th{width:40%;background:#f2f2f2}.clause{margin-bottom:20px;break-inside:avoid-page}.clause h3{margin:0;font-size:17px}.clause h4{margin:1px 0 6px;font-size:15px}.clause p{margin:4px 0}.english{color:#333}.signature-section{display:grid;grid-template-columns:1fr 1fr;gap:20px;border-top:2px solid #222;padding-top:22px;margin-top:30px;break-inside:avoid-page}.signature-box{min-height:220px;border:1px solid #777;padding:16px}.signature-line{min-height:34px;border-bottom:1px solid #333}.record{font-size:12px;color:#555;overflow-wrap:anywhere}@media(max-width:700px){.contract-document{padding:24px 18px}.contract-actions{align-items:flex-start;gap:10px;flex-direction:column}.signature-section{grid-template-columns:1fr}.cover-fields th{width:46%}}@media print{.no-print{display:none!important}.contract-shell{max-width:none}.contract-document{padding:0;border:0;box-shadow:none}}
.tenant-signing{display:grid;gap:16px;margin-top:30px;padding:22px;border:1px solid #b8bec5;border-radius:8px;background:#f8f9fa}.tenant-signing h3{margin:0}.sign-actions{display:flex;justify-content:space-between;gap:12px}
</style>
