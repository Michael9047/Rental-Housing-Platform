/** 紧急联系人表单验证工具。 */

export type EmergencyContactField =
  | 'chinese_name'
  | 'given_name_pinyin'
  | 'surname_pinyin'
  | 'relationship'
  | 'birth_date'
  | 'phone'
  | 'phone_country_code'
  | 'email'
  | 'gender'
  | 'region'
  | 'address_line'
  | 'postal_code'
  | 'consultant_id'

export interface EmergencyContactForm {
  chinese_name: string
  given_name_pinyin: string
  surname_pinyin: string
  relationship: string
  birth_date: string
  phone: string
  phone_country_code: string
  email: string
  gender: string
  region: string
  address_line: string
  postal_code: string
  consultant_id: string
  country_code: string
  country_name: string
  level1_code: string
  level1_name: string
  city_code: string
  city_name: string
  district_code: string
  district_name: string
  address_detail: string
  [key: string]: string
}

/** 必填字段 */
export const requiredContactFields: EmergencyContactField[] = [
  'chinese_name', 'relationship', 'birth_date', 'phone', 'email', 'gender',
]

/** 将拼音输入标准化为大写。 */
export function normalizePinyin(value: string): string {
  return value.toUpperCase().replace(/[^A-Z \-']/g, '')
}

/** 校验单个字段。 */
export function validateEmergencyContactField(
  field: EmergencyContactField,
  value: string,
): string {
  if (!value || !value.trim()) {
    if (requiredContactFields.includes(field)) return '此项为必填'
    return ''
  }
  switch (field) {
    case 'chinese_name':
      return value.trim().length >= 2 ? '' : '姓名至少2个字符'
    case 'given_name_pinyin':
    case 'surname_pinyin':
      if (!value.trim()) return ''
      return /^[A-Z \-']+$/.test(value) ? '' : '仅支持英文大写字母、空格和连字符'
    case 'birth_date': {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return '日期格式无效'
      const birth = new Date(value)
      const now = new Date()
      const age = now.getFullYear() - birth.getFullYear()
      if (age < 18) return '紧急联系人须年满18周岁'
      if (age > 100) return '年龄不能超过100周岁'
      return ''
    }
    case 'gender':
      return ['male', 'female', 'other'].includes(value) ? '' : '请选择性别'
    case 'phone':
      return /^\d{5,15}$/.test(value) ? '' : '手机号格式不正确'
    case 'email':
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? '' : '邮箱格式不正确'
    default:
      return ''
  }
}

/** 校验整个表单。 */
export function validateEmergencyContact(
  form: EmergencyContactForm,
): Record<EmergencyContactField, string> {
  const errors: Record<string, string> = {}
  for (const field of requiredContactFields) {
    errors[field] = validateEmergencyContactField(field, form[field] || '')
  }
  return errors as Record<EmergencyContactField, string>
}
