<!-- 预订流程第四步：填写并校验紧急联系人及住址信息。 -->
<template>
  <BookingFlowLayout
    title="紧急联系人信息"
    :current-step="3"
    previous-route="booking-personal-info"
    next-route="booking-review"
    previous-label="上一步"
    next-label="下一步：信息确认"
    :next-disabled="submitting"
    manual-next
    @next="submitForm"
  >
    <el-form label-position="top" class="contact-form booking-form-standard booking-control-form" @submit.prevent>
      <div class="section-title"><h2>紧急联系人信息</h2><span>{{ completedPersonal }}/8</span></div>
      <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" />
      <div class="emergency-form-grid">
        <ContactField label="中文姓名" field="chinese_name" help="请填写紧急联系人的真实姓名" />
        <div class="booking-field">
          <label class="booking-field__label">与申请人的关系</label>
          <el-form-item class="booking-field__control" :error="visibleError('relationship')">
            <el-select v-model="form.relationship" @blur="touch('relationship')" @change="change('relationship')">
              <el-option v-for="relation in relationships" :key="relation" :label="relation" :value="relation" />
            </el-select>
          </el-form-item>
          <p class="booking-field__help">请选择联系人与申请人的实际关系</p>
        </div>
        <ContactField label="名的英文大写拼音" field="given_name_pinyin" pinyin />
        <ContactField label="姓的英文大写拼音" field="surname_pinyin" pinyin />
        <div class="booking-field">
          <label class="booking-field__label">出生日期</label>
          <el-form-item class="booking-field__control" :error="visibleError('birth_date')">
            <el-date-picker v-model="form.birth_date" value-format="YYYY-MM-DD" type="date" :disabled-date="(date: Date) => date > new Date()" @blur="touch('birth_date')" @change="change('birth_date')" />
          </el-form-item>
          <p class="booking-field__help">紧急联系人须年满 18 周岁，且年龄不能超过 100 周岁</p>
        </div>
        <div class="booking-field">
          <label class="booking-field__label">手机国家区号和手机号</label>
          <el-form-item class="booking-field__control" :error="phoneError">
            <div class="phone-control">
              <el-select v-model="form.phone_country_code" @change="change('phone_country_code')"><el-option v-for="item in phoneCodes" :key="item.value" :label="item.label" :value="item.value" /></el-select>
              <el-input v-model="form.phone" inputmode="numeric" maxlength="15" @blur="touch('phone')" @input="phoneInput" />
            </div>
          </el-form-item>
          <p class="booking-field__help">请填写可正常接听和接收通知的号码</p>
        </div>
        <ContactField label="邮箱" field="email" help="用于接收预订进度通知，请填写可正常联系的邮箱" />
        <div class="booking-field">
          <label class="booking-field__label">性别</label>
          <el-form-item class="booking-field__control" :error="visibleError('gender')">
            <el-radio-group v-model="form.gender" @change="change('gender')"><el-radio value="male">男</el-radio><el-radio value="female">女</el-radio><el-radio value="other">其他</el-radio></el-radio-group>
          </el-form-item>
          <p class="booking-field__help">请选择联系人证件所示性别</p>
        </div>
      </div>

      <div class="section-title address-title">
        <div><h2>紧急联系人住址</h2><span>{{ completedAddress }}/3</span></div>
        <el-checkbox :model-value="contactStore.sameAsApplicant" @change="toggleSameAddress">地址与个人信息相同</el-checkbox>
      </div>
      <div class="emergency-form-grid">
        <AddressSelector :model-value="form" :disabled="contactStore.sameAsApplicant" />
        <ContactField label="详细联系地址" field="address_line" help="请填写街道、门牌号和房间号等详细信息" :disabled="contactStore.sameAsApplicant" />
        <ContactField label="邮政编码" field="postal_code" help="支持字母、数字、空格和连字符" :disabled="contactStore.sameAsApplicant" />
      </div>
      <div class="section-title other-title"><h2>其他信息</h2></div>
      <div class="emergency-form-grid">
        <ContactField label="顾问工号（选填）" field="consultant_id" help="如有专属顾问，请填写顾问工号；没有可留空" />
      </div>
      <el-alert v-if="submitError" :title="submitError" type="error" :closable="false" />
    </el-form>
  </BookingFlowLayout>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElFormItem, ElInput } from 'element-plus'
import BookingFlowLayout from '@/components/booking/BookingFlowLayout.vue'
import AddressSelector from '@/components/booking/AddressSelector.vue'
import { useBookingEmergencyContactStore } from '@/stores/bookingEmergencyContact'
import { useBookingPersonalInfoStore } from '@/stores/bookingPersonalInfo'
import { bookingEmergencyContactService } from '@/services/bookingEmergencyContact'
import { bookingDraftService } from '@/services/bookingDraft'
import { normalizePinyin, requiredContactFields, validateEmergencyContact, validateEmergencyContactField, type EmergencyContactField } from '@/utils/emergencyContactValidation'
import { restoreLegacyAddress } from '@/types/address'

const router = useRouter()
const route = useRoute()
const contactStore = useBookingEmergencyContactStore()
const applicantStore = useBookingPersonalInfoStore()
const form = contactStore.form
const touched = reactive(new Set<EmergencyContactField>())
const submitted = ref(false)
const submitting = ref(false)
const submitError = ref('')
const loadError = ref('')
const errors = reactive(validateEmergencyContact(form))
const relationships = ['父亲', '母亲', '配偶', '兄弟姐妹', '亲属', '朋友', '监护人', '其他']
const phoneCodes = [{ label: '中国 +86', value: '+86' }, { label: '英国 +44', value: '+44' }, { label: '美国/加拿大 +1', value: '+1' }, { label: '澳大利亚 +61', value: '+61' }, { label: '新加坡 +65', value: '+65' }]
const completedPersonal = computed(() => ['chinese_name', 'given_name_pinyin', 'surname_pinyin', 'relationship', 'birth_date', 'phone', 'email', 'gender'].filter((field) => form[field as EmergencyContactField]).length)
const completedAddress = computed(() => ['region', 'address_line', 'postal_code'].filter((field) => form[field as EmergencyContactField]).length)

function revalidate(field: EmergencyContactField) { errors[field] = validateEmergencyContactField(field, form[field]) }
function touch(field: EmergencyContactField) { touched.add(field); revalidate(field) }
function change(field: EmergencyContactField) { if (touched.has(field) || errors[field]) revalidate(field) }
function visibleError(field: EmergencyContactField) { return submitted.value || touched.has(field) ? errors[field] : '' }
const phoneError = computed(() => visibleError('phone_country_code') || visibleError('phone'))
function phoneInput(value: string) { form.phone = value.replace(/\D/g, ''); change('phone') }

function toggleSameAddress(value: string | number | boolean) {
  contactStore.setSameAsApplicant(Boolean(value), {
    ...applicantStore.form,
  })
  ;(['region', 'address_line', 'postal_code'] as EmergencyContactField[]).forEach(revalidate)
}

async function submitForm() {
  submitted.value = true
  Object.assign(errors, validateEmergencyContact(form))
  requiredContactFields.forEach((field) => touched.add(field))
  if (requiredContactFields.some((field) => errors[field]) || errors.consultant_id) return
  submitting.value = true
  submitError.value = ''
  try {
    await bookingEmergencyContactService.validate({ ...form })
    await bookingDraftService.save(Number(route.params.propertyId), {
      emergency_contact: { ...form },
      current_step: 'review',
    })
    await router.push({ name: 'booking-review', params: { propertyId: String(route.params.propertyId) } })
  } catch (error: any) {
    submitError.value = error?.response?.data?.detail?.[0]?.msg || error?.response?.data?.detail || '紧急联系人信息校验失败，请检查后重试'
  } finally { submitting.value = false }
}

const ContactField = defineComponent({
  props: { label: { type: String, required: true }, field: { type: String, required: true }, help: { type: String, default: '' }, pinyin: Boolean, disabled: Boolean },
  setup(props) {
    const field = props.field as EmergencyContactField
    return () => h('div', { class: 'booking-field' }, [h('label', { class: 'booking-field__label' }, props.label), h(ElFormItem, { class: 'booking-field__control', error: visibleError(field) }, () => h(ElInput, {
      modelValue: form[field], disabled: props.disabled,
      'onUpdate:modelValue': (inputValue: string) => { const value = props.pinyin ? normalizePinyin(inputValue) : inputValue; form[field] = value as never; change(field) },
      onBlur: () => touch(field),
    })), props.help ? h('p', { class: 'booking-field__help' }, props.help) : null])
  },
})

watch(
  () => [contactStore.sameAsApplicant, applicantStore.form.region, applicantStore.form.address_line, applicantStore.form.postal_code],
  () => {
    if (contactStore.sameAsApplicant) contactStore.setSameAsApplicant(true, applicantStore.form)
  },
)

onMounted(async () => {
  try {
    const draft = await bookingDraftService.get(Number(route.params.propertyId))
    if (!draft.personal_info) {
      loadError.value = '未找到已保存的个人信息，请返回个人信息页重新提交'
      return
    }
    Object.assign(applicantStore.form, draft.personal_info)
    restoreLegacyAddress(applicantStore.form)
    if (draft.emergency_contact) {
      Object.assign(form, draft.emergency_contact)
      restoreLegacyAddress(form)
      if (draft.emergency_contact.same_as_personal_address) {
        contactStore.setSameAsApplicant(true, applicantStore.form)
      }
    }
  } catch (error: any) {
    console.error('[emergency-contact] draft load failed', error)
    const status = error?.response?.status
    const detail = error?.response?.data?.detail
    loadError.value = status
      ? `紧急联系人页面加载失败：HTTP ${status}${detail ? `，${typeof detail === 'string' ? detail : JSON.stringify(detail)}` : ''}`
      : '紧急联系人页面加载失败，请检查网络后重试'
  }
})
</script>

<style scoped>
.contact-form {
  display: grid;
  width: min(100%, 1040px);
  margin: 0 auto;
  gap: 28px;
}
.section-title { display: flex; align-items: baseline; gap: 8px; padding-bottom: 10px; border-bottom: 1px solid var(--border-light); }
.section-title h2 { margin: 0; font-size: 19px; }
.section-title span { font-weight: 700; }
.address-title { justify-content: space-between; align-items: center; margin-top: 8px; }
.other-title { margin-top: 8px; }
.address-title > div { display: flex; align-items: baseline; gap: 8px; }
.emergency-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: clamp(24px, 3vw, 48px); row-gap: 28px; width: 100%; align-items: start; }
:global(.booking-field) { display: flex; flex-direction: column; width: 100%; min-width: 0; position: relative; overflow: visible; }
:global(.booking-field__label) { display: block; margin: 0 0 8px; color: #26364a; font-size: 16px; line-height: 22px; font-weight: 400; }
:global(.booking-field__control) { width: 100%; margin: 0; }
:global(.booking-control-form) {
  --booking-control-height: 48px;
  --booking-control-padding: 4px 12px;
  --booking-control-radius: var(--radius-sm);
  --booking-control-border: 0 0 0 1px var(--el-border-color) inset;
}
:global(.booking-field__help) { position: static; display: block; width: 100%; margin: 7px 0 0; padding: 0; color: #3f7fc4; font-size: 13px; font-weight: 400; line-height: 20px; white-space: normal; overflow: visible; word-break: break-word; }
:global(.phone-control) { display: grid; grid-template-columns: minmax(140px, 0.36fr) minmax(0, 0.64fr); gap: 12px; width: 100%; }
@media (max-width: 899px) { .emergency-form-grid { grid-template-columns: minmax(0, 1fr); column-gap: 0; row-gap: 22px; } .address-title { align-items: flex-start; flex-direction: column; } }
@media (max-width: 520px) { :global(.phone-control) { grid-template-columns: minmax(0, 1fr); } }
</style>
