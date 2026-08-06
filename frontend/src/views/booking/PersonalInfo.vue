<!-- 预订流程第三步：填写并校验个人信息与住址信息。 -->
<template>
  <BookingFlowLayout
    title="填写个人信息"
    :current-step="2"
    previous-route="booking-lease-term"
    next-route="booking-emergency-contact"
    :next-disabled="submitting"
    manual-next
    @next="submitForm"
  >
    <el-form ref="formRef" :model="form" :rules="formRules" label-position="top" class="personal-form booking-form-standard booking-control-form" @submit.prevent>
      <div class="section-heading">
        <div><h2>个人信息</h2><p>请确保姓名和证件信息真实一致。</p></div>
        <el-button @click="fillFromAccount">从账户资料填充</el-button>
      </div>

      <div class="personal-form-grid">
        <FormField label="中文姓名" field="chinese_name" help="请填写与证件一致的中文姓名" />
        <div class="booking-field">
          <label class="booking-field__label">出生日期</label>
          <el-form-item class="booking-field__control" prop="birth_date" :error="visibleError('birth_date')">
            <el-date-picker v-model="form.birth_date" value-format="YYYY-MM-DD" type="date" :disabled-date="disableBirthDate" @blur="touch('birth_date')" @change="change('birth_date')" />
          </el-form-item>
          <p class="booking-field__help">申请人须年满 18 周岁，且年龄不能超过 100 周岁</p>
        </div>
        <FormField label="名的英文大写拼音" field="given_name_pinyin" pinyin />
        <FormField label="姓的英文大写拼音" field="surname_pinyin" pinyin />
        <div class="booking-field">
          <label class="booking-field__label">性别</label>
          <el-form-item class="booking-field__control" prop="gender" :error="visibleError('gender')">
            <el-radio-group v-model="form.gender" @change="change('gender')">
              <el-radio value="male">男</el-radio><el-radio value="female">女</el-radio><el-radio value="other">其他</el-radio>
            </el-radio-group>
          </el-form-item>
          <p class="booking-field__help">请选择证件所示性别</p>
        </div>
        <div class="booking-field">
          <label class="booking-field__label">手机国家区号和手机号</label>
          <el-form-item class="booking-field__control" prop="phone" :error="phoneError">
            <div class="phone-control">
              <el-select v-model="form.phone_country_code" @change="change('phone_country_code')">
                <el-option v-for="item in phoneCodes" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
              <el-input v-model="form.phone" inputmode="numeric" maxlength="15" @blur="touch('phone')" @input="phoneInput" />
            </div>
          </el-form-item>
          <p class="booking-field__help">用于接收预订进度通知，请填写可正常联系的号码</p>
        </div>
        <FormField label="邮箱" field="email" help="用于接收预订进度通知，请填写可正常联系的邮箱" />
        <div class="booking-field">
          <label class="booking-field__label">护照国籍/地区</label>
          <el-form-item class="booking-field__control" prop="nationality" :error="visibleError('nationality')">
            <el-select v-model="form.nationality" filterable @blur="touch('nationality')" @change="change('nationality')">
              <el-option v-for="country in countries" :key="country" :label="country" :value="country" />
            </el-select>
          </el-form-item>
          <p class="booking-field__help">请按护照签发信息选择国籍或地区</p>
        </div>
      </div>

      <h2 class="subheading">学习信息</h2>
      <div class="personal-form-grid">
        <FormField label="学校" field="school_name" help="请填写当前或即将入读的学校全称" />
        <div class="booking-field">
          <label class="booking-field__label">入学年级</label>
          <el-form-item class="booking-field__control" prop="enrollment_grade" :error="visibleError('enrollment_grade')">
            <el-select v-model="form.enrollment_grade" @blur="touch('enrollment_grade')" @change="change('enrollment_grade')">
              <el-option v-for="grade in grades" :key="grade" :label="grade" :value="grade" />
            </el-select>
          </el-form-item>
          <p class="booking-field__help">请选择预订入住时对应的入学年级</p>
        </div>
        <FormField label="专业英文名称" field="major_english" help="请填写学校录取材料中的专业英文名称" />
      </div>

      <h2 class="subheading">住址信息</h2>
      <div class="personal-form-grid">
        <AddressSelector :model-value="form" />
        <FormField label="详细联系地址" field="address_line" help="请填写街道、门牌号和房间号等详细信息" />
        <FormField label="邮政编码" field="postal_code" help="支持字母、数字、空格和连字符" />
      </div>

      <el-alert v-if="submitError" :title="submitError" type="error" :closable="false" />
    </el-form>
  </BookingFlowLayout>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElFormItem, ElInput, ElMessage, type FormInstance, type FormRules } from 'element-plus'
import BookingFlowLayout from '@/components/booking/BookingFlowLayout.vue'
import AddressSelector from '@/components/booking/AddressSelector.vue'
import { useBookingPersonalInfoStore } from '@/stores/bookingPersonalInfo'
import { useAuthStore } from '@/stores/auth'
import { bookingPersonalInfoService } from '@/services/bookingPersonalInfo'
import { bookingDraftService } from '@/services/bookingDraft'
import { normalizePinyin, requiredFields, validatePersonalInfo, validatePersonalInfoField, type PersonalInfoField } from '@/utils/personalInfoValidation'
import { restoreLegacyAddress } from '@/types/address'

const router = useRouter()
const route = useRoute()
const personalStore = useBookingPersonalInfoStore()
const authStore = useAuthStore()
const form = personalStore.form
const formRef = ref<FormInstance>()
const touched = reactive(new Set<PersonalInfoField>())
const submitted = ref(false)
const submitting = ref(false)
const submitError = ref('')
const errors = reactive(validatePersonalInfo(form))
const countries = ['中国大陆', '中国香港', '中国澳门', '中国台湾', '英国', '美国', '加拿大', '澳大利亚', '新加坡', '日本', '韩国', '德国', '法国', '其他']
const grades = ['本科一年级', '本科二年级', '本科三年级', '本科四年级', '硕士', '博士', '语言课程', '其他']
const phoneCodes = [{ label: '中国 +86', value: '+86' }, { label: '英国 +44', value: '+44' }, { label: '美国/加拿大 +1', value: '+1' }, { label: '澳大利亚 +61', value: '+61' }, { label: '新加坡 +65', value: '+65' }, { label: '日本 +81', value: '+81' }, { label: '韩国 +82', value: '+82' }]

function revalidate(field: PersonalInfoField) { errors[field] = validatePersonalInfoField(field, form[field]) }
function touch(field: PersonalInfoField) { touched.add(field); revalidate(field) }
function change(field: PersonalInfoField) { if (touched.has(field) || errors[field]) revalidate(field) }
function visibleError(field: PersonalInfoField) { return submitted.value || touched.has(field) ? errors[field] : '' }
const phoneError = computed(() => visibleError('phone_country_code') || visibleError('phone'))
function phoneInput(value: string) { form.phone = value.replace(/\D/g, ''); change('phone') }
function disableBirthDate(date: Date) { return date > new Date() }

const formRules: FormRules = Object.fromEntries(requiredFields.map((field) => [field, {
  validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
    const message = validatePersonalInfoField(field, value || '')
    callback(message ? new Error(message) : undefined)
  },
  trigger: ['blur', 'change'],
}]))

/** 将结构化地址映射回现有草稿接口使用的字段，避免重构后地址只显示不保存。 */
function createSubmitPayload() {
  return { ...form, address_detail: form.address_line || form.address_detail }
}

async function scrollToFirstInvalidField() {
  await nextTick()
  const invalidField = document.querySelector('.booking-control-form .el-form-item.is-error, .booking-control-form .el-form-item__error')
  invalidField?.closest('.booking-field')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function fillFromAccount() {
  const user = authStore.user
  if (!user) return
  if (!form.chinese_name) form.chinese_name = user.username || ''
  if (!form.phone) form.phone = user.phone?.replace(/\D/g, '') || ''
  if (!form.email) form.email = user.email || ''
  ElMessage.success('已从账户资料填充可用信息')
}

async function submitForm() {
  if (submitting.value) return
  const propertyId = Number(route.params.propertyId)
  if (!Number.isSafeInteger(propertyId) || propertyId <= 0) {
    submitError.value = '当前房源编号缺失，请返回房源页面重新进入'
    return
  }
  submitted.value = true
  Object.assign(errors, validatePersonalInfo(form))
  requiredFields.forEach((field) => touched.add(field))
  const failed = requiredFields.filter((field) => errors[field])
  const elementValid = await formRef.value?.validate().then(() => true).catch(() => false) ?? false
  if (!elementValid || failed.length > 0) {
    submitError.value = `请填写所有必填项（${failed.join('、')}）`
    submitError.value = '请检查并补充未正确填写的信息'
    ElMessage.warning(submitError.value)
    await scrollToFirstInvalidField()
    return
  }
  submitting.value = true
  submitError.value = ''
  try {
    const payload = createSubmitPayload()
    const validationResult = await bookingPersonalInfoService.validate(payload)
    if (!validationResult.valid) throw new Error('个人信息校验未通过')
    await bookingDraftService.save(propertyId, {
      personal_info: payload,
      current_step: 'emergency_contact',
    })
    await router.push({ name: 'booking-emergency-contact', params: { propertyId: String(route.params.propertyId) } })
  } catch (error: any) {
    console.error('[personal-info] submit failed', {
      error,
      status: error?.response?.status,
      data: error?.response?.data,
      url: error?.config?.url,
      method: error?.config?.method,
      payload: error?.config?.data,
    })
    const status = error?.response?.status
    const detail = error?.response?.data?.detail
    const detailText = Array.isArray(detail)
      ? detail.map((item: any) => item.msg || JSON.stringify(item)).join('；')
      : detail
    if (status === 401) submitError.value = '当前登录已过期，请重新登录'
    else if (status) submitError.value = `保存个人信息失败：HTTP ${status}${detailText ? `，${detailText}` : ''}`
    else submitError.value = error?.message || '个人信息提交失败，请检查网络后重试'
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    const draft = await bookingDraftService.get(Number(route.params.propertyId))
    if (!draft.move_in_date || !draft.lease_months) {
      router.replace({ name: 'booking-lease-term', params: { propertyId: String(route.params.propertyId) } })
      return
    }
    if (draft.personal_info) {
      Object.assign(form, draft.personal_info)
      restoreLegacyAddress(form)
    }
  } catch {
    router.replace({ name: 'booking-move-in-date', params: { propertyId: String(route.params.propertyId) } })
  }
})

const FormField = defineComponent({
  props: { label: { type: String, required: true }, field: { type: String, required: true }, help: { type: String, default: '' }, pinyin: Boolean },
  setup(props) {
    const field = props.field as PersonalInfoField
    return () => h('div', { class: 'booking-field' }, [
      h('label', { class: 'booking-field__label' }, props.label),
      h(ElFormItem, { class: 'booking-field__control', prop: field, error: visibleError(field) }, () => h(ElInput, {
        modelValue: form[field],
        'onUpdate:modelValue': (inputValue: string) => { const value = props.pinyin ? normalizePinyin(inputValue) : inputValue; form[field] = value as never; change(field) },
        onBlur: () => touch(field),
      })),
      props.help ? h('p', { class: 'booking-field__help' }, props.help) : null,
    ])
  },
})
</script>

<style scoped>
.personal-form {
  display: grid;
  width: min(100%, 1040px);
  margin: 0 auto;
  gap: 28px;
}
.section-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.section-heading h2, .subheading { margin: 0; font-size: 18px; }
.section-heading p { margin: 6px 0 0; color: var(--text-muted); font-size: 13px; }
.subheading { padding-top: 24px; border-top: 1px solid var(--border-light); }
.personal-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: clamp(24px, 3vw, 48px);
  row-gap: 28px;
  width: 100%;
  align-items: start;
}
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

@media (max-width: 899px) {
  .personal-form { gap: 24px; }
  .personal-form-grid { grid-template-columns: minmax(0, 1fr); column-gap: 0; row-gap: 22px; }
  .section-heading { flex-direction: column; }
}
@media (max-width: 520px) { :global(.phone-control) { grid-template-columns: minmax(0, 1fr); } }
</style>
