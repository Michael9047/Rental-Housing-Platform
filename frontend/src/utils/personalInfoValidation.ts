/** 个人信息表单验证工具。 */

export type PersonalInfoField =
  | 'chinese_name'
  | 'given_name_pinyin'
  | 'surname_pinyin'
  | 'birth_date'
  | 'gender'
  | 'phone'
  | 'phone_country_code'
  | 'email'
  | 'nationality'
  | 'school_name'
  | 'enrollment_grade'
  | 'major_english'
  | 'region'
  | 'address_detail'
  | 'postal_code'
  | 'address_line'

export interface PersonalInfoForm {
  chinese_name: string
  given_name_pinyin: string
  surname_pinyin: string
  birth_date: string
  gender: string
  phone: string
  phone_country_code: string
  email: string
  nationality: string
  school_name: string
  enrollment_grade: string
  major_english: string
  region: string
  address_detail: string
  postal_code: string
  address_line: string
  [key: string]: string
}

/** 必填字段列表 */
export const requiredFields: PersonalInfoField[] = [
  'chinese_name', 'given_name_pinyin', 'surname_pinyin',
  'birth_date', 'gender', 'phone', 'email', 'nationality',
  'school_name', 'enrollment_grade',
]

/** 将拼音输入标准化为大写。 */
export function normalizePinyin(value: string): string {
  return value.toUpperCase().replace(/[^A-Z \-']/g, '')
}

/** 校验单个字段。 */
export function validatePersonalInfoField(
  field: PersonalInfoField,
  value: string,
): string {
  if (!value || !value.trim()) {
    if (requiredFields.includes(field)) return '此项为必填'
    return ''
  }
  switch (field) {
    case 'chinese_name':
      return value.trim().length >= 2 ? '' : '姓名至少2个字符'
    case 'given_name_pinyin':
    case 'surname_pinyin':
      return /^[A-Z \-']+$/.test(value) ? '' : '仅支持英文大写字母、空格和连字符'
    case 'birth_date': {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return '日期格式无效'
      const birth = new Date(value)
      const now = new Date()
      const age = now.getFullYear() - birth.getFullYear()
      if (age < 18) return '申请人须年满18周岁'
      if (age > 100) return '年龄不能超过100周岁'
      return ''
    }
    case 'gender':
      return ['male', 'female', 'other'].includes(value) ? '' : '请选择性别'
    case 'phone':
      return /^\d{5,15}$/.test(value) ? '' : '手机号格式不正确'
    case 'email':
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? '' : '邮箱格式不正确'
    case 'nationality':
      return value.trim() ? '' : '请选择国籍/地区'
    default:
      return ''
  }
}

/** 校验整个表单，返回字段→错误消息的映射。 */
export function validatePersonalInfo(
  form: PersonalInfoForm,
): Record<PersonalInfoField, string> {
  const errors: Record<string, string> = {}
  for (const field of requiredFields) {
    errors[field] = validatePersonalInfoField(field, form[field] || '')
  }
  return errors as Record<PersonalInfoField, string>
}
