/** 区域数据 — 兼容占位 */

export interface Country { code: string; name: string }
export interface City { code: string; name: string; country_code: string }
export interface Province { code: string; name: string; country_code: string }
export interface District { code: string; name: string; city_code: string }

export function getCountries(_countryCode?: string): Country[] {
  return [
    { code: 'CN', name: '中国' }, { code: 'SG', name: '新加坡' },
    { code: 'GB', name: '英国' }, { code: 'US', name: '美国' },
    { code: 'AU', name: '澳大利亚' }, { code: 'CA', name: '加拿大' },
  ]
}

export function getCities(countryCode?: string, _provinceCode?: string): City[] {
  if (countryCode === 'CN') return [{ code: 'sz', name: '苏州', country_code: 'CN' }]
  return []
}

export function getProvinces(_countryCode?: string, _cityCode?: string): Province[] { return [] }
export function getDistricts(_cityCode?: string, _provinceCode?: string): District[] { return [] }
export function hasProvinces(_countryCode?: string): boolean { return false }
