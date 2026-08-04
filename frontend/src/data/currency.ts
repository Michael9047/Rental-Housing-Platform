const countryCurrencyMap: Record<string, string> = {
  CN: 'CNY',
  China: 'CNY',
  Singapore: 'SGD',
  SG: 'SGD',
  UK: 'GBP',
  GB: 'GBP',
  'United Kingdom': 'GBP',
  US: 'USD',
  USA: 'USD',
  'United States': 'USD',
  Australia: 'AUD',
  AU: 'AUD',
  Canada: 'CAD',
  CA: 'CAD',
  HongKong: 'HKD',
  'Hong Kong': 'HKD',
  HK: 'HKD',
  Japan: 'JPY',
  JP: 'JPY',
  Korea: 'KRW',
  KR: 'KRW',
}

export function countryToCurrency(country?: string | null): string {
  if (!country) return 'CNY'
  return countryCurrencyMap[country] || countryCurrencyMap[country.trim()] || 'CNY'
}

export function formatPrice(amount?: number | string | null, currency = 'CNY', country?: string | null): string {
  const value = Number(amount || 0)
  const code = currency || countryToCurrency(country)
  try {
    return new Intl.NumberFormat('zh-CN', {
      style: 'currency',
      currency: code,
      maximumFractionDigits: Number.isInteger(value) ? 0 : 2,
    }).format(value)
  } catch {
    return `${code} ${value.toLocaleString('zh-CN')}`
  }
}

export function formatPriceWithDual(priceCNY?: number | string | null, country?: string | null): string {
  const value = Number(priceCNY || 0)
  const code = countryToCurrency(country)
  if (code === 'CNY') return formatPrice(value, 'CNY')
  return `${formatPrice(value, 'CNY')} / ${formatPrice(value, code)}`
}
