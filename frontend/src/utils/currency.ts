// 房源币种展示工具：优先使用后端 currency，缺失时按国家/地区推断。
const CURRENCY_ALIASES: Record<string, string> = {
  RMB: 'CNY',
  '¥': 'CNY',
  '￥': 'CNY',
  'S$': 'SGD',
  '£': 'GBP',
  '$': 'USD',
  'HK$': 'HKD',
  'A$': 'AUD',
}

const COUNTRY_CURRENCIES: Record<string, string> = {
  SG: 'SGD',
  SINGAPORE: 'SGD',
  新加坡: 'SGD',
  GB: 'GBP',
  UK: 'GBP',
  'UNITED KINGDOM': 'GBP',
  英国: 'GBP',
  US: 'USD',
  USA: 'USD',
  'UNITED STATES': 'USD',
  美国: 'USD',
  HK: 'HKD',
  'HONG KONG': 'HKD',
  中国香港: 'HKD',
  CN: 'CNY',
  CHINA: 'CNY',
  中国: 'CNY',
  中国大陆: 'CNY',
  AU: 'AUD',
  AUSTRALIA: 'AUD',
  澳大利亚: 'AUD',
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  CNY: '¥',
  GBP: '£',
  SGD: 'S$',
  USD: '$',
  HKD: 'HK$',
  JPY: 'JP¥',
  KRW: '₩',
  AUD: 'A$',
}

export function resolveCurrency(currency?: string | null, country?: string | null): string {
  const explicit = String(currency || '').trim().toUpperCase()
  if (explicit) return CURRENCY_ALIASES[explicit] || explicit

  const market = String(country || '').trim().toUpperCase()
  return COUNTRY_CURRENCIES[market] || 'CNY'
}

export function getCurrencySymbol(currency?: string | null, country?: string | null): string {
  const code = resolveCurrency(currency, country)
  return CURRENCY_SYMBOLS[code] || `${code} `
}

export function formatPropertyPrice(
  price: number | string | null | undefined,
  currency?: string | null,
  country?: string | null,
): string {
  const amount = Number(price)
  const formatted = Number.isFinite(amount)
    ? amount.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
    : '待确认'
  return `${getCurrencySymbol(currency, country)}${formatted}`
}
