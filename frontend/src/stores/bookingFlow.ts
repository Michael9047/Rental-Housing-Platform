import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { Property } from '@/types/property'

export interface ApplicantInfo {
  chinese_name: string
  given_name_pinyin: string
  surname_pinyin: string
  birth_date: string
  gender: 'male' | 'female' | ''
  phone: string
  email: string
  nationality: string
  school_name: string
  enrollment_grade: string
  major_english: string
  region: string
  address_detail: string
  postal_code: string
}

export interface GuarantorInfo {
  chinese_name: string
  given_name_pinyin: string
  surname_pinyin: string
  relation: string
  birth_date: string
  phone: string
  email: string
  gender: 'male' | 'female' | ''
  region: string
  address_detail: string
  postal_code: string
  same_as_applicant: boolean
}

export interface EmergencyContactInfo {
  chinese_name: string
  given_name_pinyin: string
  surname_pinyin: string
  relation: string
  birth_date: string
  phone: string
  email: string
  gender: 'male' | 'female' | ''
  region: string
  address_detail: string
  postal_code: string
  same_as_guarantor: boolean
  consultant_id: string
}

const STORAGE_KEY = 'booking_flow_data'

function createEmptyApplicant(): ApplicantInfo {
  return {
    chinese_name: '',
    given_name_pinyin: '',
    surname_pinyin: '',
    birth_date: '',
    gender: '',
    phone: '',
    email: '',
    nationality: '中国大陆',
    school_name: '',
    enrollment_grade: '',
    major_english: '',
    region: '',
    address_detail: '',
    postal_code: '',
  }
}

function createEmptyGuarantor(): GuarantorInfo {
  return {
    chinese_name: '',
    given_name_pinyin: '',
    surname_pinyin: '',
    relation: '',
    birth_date: '',
    phone: '',
    email: '',
    gender: '',
    region: '',
    address_detail: '',
    postal_code: '',
    same_as_applicant: false,
  }
}

function createEmptyEmergency(): EmergencyContactInfo {
  return {
    chinese_name: '',
    given_name_pinyin: '',
    surname_pinyin: '',
    relation: '',
    birth_date: '',
    phone: '',
    email: '',
    gender: '',
    region: '',
    address_detail: '',
    postal_code: '',
    same_as_guarantor: false,
    consultant_id: '',
  }
}

export const useBookingFlowStore = defineStore('bookingFlow', () => {
  const property = ref<Property | null>(null)
  const start_date = ref('')
  const lease_months = ref(0)
  const applicant = ref<ApplicantInfo>(createEmptyApplicant())
  const guarantor = ref<GuarantorInfo>(createEmptyGuarantor())
  const emergency = ref<EmergencyContactInfo>(createEmptyEmergency())
  const current_step = ref(1)
  const agreements_accepted = ref({
    booking_auth: false,
    data_transfer: false,
    personal_info: false,
    cancellation: false,
  })

  const total_price = computed(() => {
    if (!property.value || !lease_months.value) return 0
    return property.value.price_monthly * lease_months.value
  })

  const deposit_amount = computed(() => {
    if (!property.value) return 0
    return property.value.deposit_amount ?? property.value.price_monthly
  })

  const service_fee = computed(() => {
    if (!property.value || !property.value.service_fee_rate) return 0
    return Math.round(total_price.value * property.value.service_fee_rate)
  })

  const lease_options = computed(() => {
    return [
      { value: 1, label: '一个月' },
      { value: 2, label: '两个月' },
      { value: 3, label: '三个月' },
      { value: 6, label: '六个月' },
      { value: 12, label: '十二个月' },
    ]
  })

  function loadFromStorage() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const data = JSON.parse(saved)
        if (data.property) property.value = data.property
        if (data.start_date) start_date.value = data.start_date
        if (data.lease_months) lease_months.value = data.lease_months
        if (data.applicant) applicant.value = { ...createEmptyApplicant(), ...data.applicant }
        if (data.guarantor) guarantor.value = { ...createEmptyGuarantor(), ...data.guarantor }
        if (data.emergency) emergency.value = { ...createEmptyEmergency(), ...data.emergency }
        if (data.current_step) current_step.value = data.current_step
        if (data.agreements_accepted) agreements_accepted.value = { ...agreements_accepted.value, ...data.agreements_accepted }
      }
    } catch {
      // ignore
    }
  }

  function saveToStorage() {
    const data = {
      property: property.value,
      start_date: start_date.value,
      lease_months: lease_months.value,
      applicant: applicant.value,
      guarantor: guarantor.value,
      emergency: emergency.value,
      current_step: current_step.value,
      agreements_accepted: agreements_accepted.value,
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  }

  function clearStorage() {
    localStorage.removeItem(STORAGE_KEY)
  }

  function reset() {
    property.value = null
    start_date.value = ''
    lease_months.value = 0
    applicant.value = createEmptyApplicant()
    guarantor.value = createEmptyGuarantor()
    emergency.value = createEmptyEmergency()
    current_step.value = 1
    agreements_accepted.value = {
      booking_auth: false,
      data_transfer: false,
      personal_info: false,
      cancellation: false,
    }
    clearStorage()
  }

  function setProperty(p: Property) {
    property.value = p
    saveToStorage()
  }

  function setStartDate(date: string) {
    start_date.value = date
    saveToStorage()
  }

  function setLeaseMonths(months: number) {
    lease_months.value = months
    saveToStorage()
  }

  function nextStep() {
    if (current_step.value < 5) {
      current_step.value++
      saveToStorage()
    }
  }

  function prevStep() {
    if (current_step.value > 1) {
      current_step.value--
      saveToStorage()
    }
  }

  function goToStep(step: number) {
    current_step.value = step
    saveToStorage()
  }

  function prefillFromUser(user: any) {
    if (user?.email) applicant.value.email = user.email
    if (user?.phone) applicant.value.phone = user.phone
    if (user?.username) applicant.value.chinese_name = user.username
    saveToStorage()
  }

  watch(
    [applicant, guarantor, emergency, agreements_accepted],
    () => saveToStorage(),
    { deep: true }
  )

  loadFromStorage()

  return {
    property,
    start_date,
    lease_months,
    applicant,
    guarantor,
    emergency,
    current_step,
    agreements_accepted,
    total_price,
    deposit_amount,
    service_fee,
    lease_options,
    loadFromStorage,
    saveToStorage,
    clearStorage,
    reset,
    setProperty,
    setStartDate,
    setLeaseMonths,
    nextStep,
    prevStep,
    goToStep,
    prefillFromUser,
  }
})
