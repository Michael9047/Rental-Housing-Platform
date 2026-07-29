/** 结构化地址类型，供 AddressSelector 和个人信息/紧急联系人表单使用。 */

export interface StructuredAddress {
  country_code: string
  country_name: string
  level1_code: string
  level1_name: string
  city_code: string
  city_name: string
  district_code: string
  district_name: string
  region: string
  address_line: string
  address_detail: string
  postal_code: string
  phone_country_code: string
}

/** 表单中用于 AddressSelector 绑定的最小地址字段子集。 */
export type AddressFormLike = Partial<StructuredAddress> & Record<string, any>

/** 从 StructuredAddress 各字段拼接完整 region 字符串。 */
export function buildRegion(address: Partial<StructuredAddress>): string {
  const parts: string[] = []
  if (address.country_name) parts.push(address.country_name)
  if (address.level1_name) parts.push(address.level1_name)
  if (address.city_name) parts.push(address.city_name)
  if (address.district_name) parts.push(address.district_name)
  return parts.join(' ')
}

/** 从旧版地址字段（region / address_detail 等）迁移到新版 structured address。 */
export function restoreLegacyAddress(form: Record<string, any>): void {
  // 确保 phone_country_code 存在
  if (!form.phone_country_code) form.phone_country_code = '+86'
  // 如果旧版有 region 但新字段缺失，不做破坏性迁移
  if (form.region && !form.country_code) {
    form.country_code = 'CN'
    form.country_name = '中国大陆'
  }
  // 如果旧版有 address_detail 但没有 address_line
  if (form.address_detail && !form.address_line) {
    form.address_line = form.address_detail
  }
}
