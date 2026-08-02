/** 地址选择器国家/地区列表 */
export interface CountryOption {
  code: string
  name: string
}

export const addressCountries: CountryOption[] = [
  { code: 'CN', name: '中国大陆' },
  { code: 'US', name: '美国' },
  { code: 'GB', name: '英国' },
  { code: 'AU', name: '澳大利亚' },
  { code: 'CA', name: '加拿大' },
  { code: 'SG', name: '新加坡' },
  { code: 'JP', name: '日本' },
  { code: 'KR', name: '韩国' },
  { code: 'HK', name: '中国香港' },
  { code: 'MO', name: '中国澳门' },
  { code: 'TW', name: '中国台湾' },
  { code: 'FR', name: '法国' },
  { code: 'DE', name: '德国' },
  { code: 'NZ', name: '新西兰' },
]
