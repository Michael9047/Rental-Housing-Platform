// 统一前端日志模块：结构化输出、敏感数据脱敏、环境自适应
// 镜像 backend/app/core/logging.py 的设计模式
//
// 生产环境上报策略：
//   error 级别 → console.error（终端可见）+ sendBeacon → POST /api/v1/frontend-errors（写入 error.log）
//   非 error 级别 → 生产环境静默丢弃（避免噪音）

/** 需要脱敏的字段名（不区分大小写） */
const SENSITIVE_FIELDS = new Set([
  'password', 'passwd', 'pwd',
  'phone', 'mobile', 'telephone',
  'email', 'mail',
  'token', 'access_token', 'refresh_token', 'authorization',
  'cookie', 'secret', 'api_key', 'apikey',
  'id_card', 'id_number', 'credit_card',
])

/** 需要脱敏的值正则 */
const SENSITIVE_PATTERNS: RegExp[] = [
  // 中国大陆手机号
  /1[3-9]\d{9}/g,
  // Email
  /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
]

/** 脱敏递归深度上限 */
const MAX_MASK_DEPTH = 5

/**
 * 递归脱敏对象中的敏感信息（镜像 backend mask_sensitive）
 */
function maskSensitive(data: unknown, depth: number = 0): unknown {
  if (depth > MAX_MASK_DEPTH) return data
  if (data === null || data === undefined) return data
  if (typeof data === 'string') {
    let masked = data
    for (const pattern of SENSITIVE_PATTERNS) {
      masked = masked.replace(pattern, (match) => {
        if (match.includes('@')) {
          // Email: 保留首尾字符
          const [local, domain] = match.split('@')
          return `${local.slice(0, 1)}***@${domain}`
        }
        // 手机号: 保留前3后4
        return `${match.slice(0, 3)}****${match.slice(7)}`
      })
    }
    return masked
  }
  if (Array.isArray(data)) {
    return data.map(item => maskSensitive(item, depth + 1))
  }
  if (typeof data === 'object') {
    const masked: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
      const isSensitive = SENSITIVE_FIELDS.has(key.toLowerCase())
      if (isSensitive && typeof value === 'string' && value) {
        masked[key] = '***'
      } else if (isSensitive && value !== null && value !== undefined) {
        masked[key] = '***'
      } else {
        masked[key] = maskSensitive(value, depth + 1)
      }
    }
    return masked
  }
  return data
}

/** 生成简单的 UUID v4（零依赖） */
function generateId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

/** 判断是否为应过滤的噪声错误 */
function isNoise(msg: string): boolean {
  return msg.includes('ResizeObserver') || msg.includes('Script error')
}

/**
 * 获取当前全局 request-ID（由 api.ts 请求拦截器设置）
 */
function getRequestId(): string | undefined {
  return (window as any).__currentRequestId
}

// ── 生产环境错误上报（sendBeacon 批量发送）──

/** 待上报的错误缓冲区 */
let _errorBuffer: Record<string, unknown>[] = []

/** 后端上报地址（同源，不写死域名） */
const _REPORT_URL = '/api/v1/frontend-errors'

/** 缓冲区满 10 条自动冲刷 */
const _BUFFER_MAX = 10

/** 冲刷中标记，避免并发发送 */
let _flushing = false

/** 页面卸载时发送剩余错误 */
let _unloadHooked = false

/** 上报基础 URL 白名单（只允许 /api/ 开头，防恶意利用） */
function _isValidReportUrl(url: string): boolean {
  return url.startsWith('/api/')
}

/**
 * 冲刷错误缓冲区 → POST 到后端。
 * 优先用 sendBeacon（页面卸载时也可靠），降级用 fetch。
 */
function _flushErrors(): void {
  if (_errorBuffer.length === 0 || _flushing) return
  _flushing = true

  const payload = _errorBuffer.splice(0)
  const body = JSON.stringify(payload)

  if (!_isValidReportUrl(_REPORT_URL)) {
    _flushing = false
    return
  }

  if (navigator.sendBeacon) {
    const blob = new Blob([body], { type: 'application/json' })
    navigator.sendBeacon(_REPORT_URL, blob)
  } else {
    // 降级：fetch with keepalive（不支持 IE11）
    fetch(_REPORT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
    }).catch(() => { /* 上报失败不影响业务 */ })
  }

  _flushing = false
}

/**
 * 将一条错误放入上报缓冲区。
 * 达到阈值时自动冲刷；页面卸载时冲刷剩余。
 */
function _reportError(entry: Record<string, unknown>): void {
  _errorBuffer.push(entry)

  // 首次调用时注册 beforeunload 钩子
  if (!_unloadHooked && typeof window !== 'undefined') {
    _unloadHooked = true
    window.addEventListener('beforeunload', () => _flushErrors())
  }

  // 缓冲区满了就发
  if (_errorBuffer.length >= _BUFFER_MAX) {
    _flushErrors()
  }
}

/** 日志级别 */
type LogLevel = 'error' | 'warn' | 'info' | 'debug'

/** Logger 实例接口 */
export interface Logger {
  error(msg: string, meta?: Record<string, unknown>, err?: unknown): void
  warn(msg: string, meta?: Record<string, unknown>): void
  info(msg: string, meta?: Record<string, unknown>): void
  debug(msg: string, meta?: Record<string, unknown>): void
}

/**
 * 创建日志记录器（镜像 backend logging.getLogger("app.xxx")）
 *
 * @param tag - 模块标签，如 'PropertyDetail'、'api'
 * @returns { error, warn, info, debug } 四个日志方法
 *
 * @example
 * const log = createLogger('PropertyDetail')
 * log.error('加载房源失败', { propertyId: id }, err)
 * log.debug('搜索参数', { query, filters })
 */
export function createLogger(tag: string): Logger {
  function log(level: LogLevel, message: string, meta?: Record<string, unknown>, err?: unknown): void {
    // 生产环境：只输出 error 级别
    if (import.meta.env.PROD && level !== 'error') return

    // 噪声过滤
    if (isNoise(message)) return
    if (err instanceof Error && isNoise(err.message)) return

    const timestamp = new Date().toISOString()
    const requestId = getRequestId()
    const errorObj = err instanceof Error
      ? { name: err.name, message: err.message, stack: err.stack }
      : err !== undefined ? String(err) : undefined

    const entry = {
      timestamp,
      level,
      tag,
      message,
      url: typeof window !== 'undefined' ? window.location.href : undefined,
      ...(meta && Object.keys(meta).length > 0 && { meta: maskSensitive(meta) }),
      ...(errorObj && { error: errorObj }),
      ...(requestId && { requestId }),
    }

    // 开发环境：彩色分组输出
    if (import.meta.env.DEV) {
      const styles: Record<LogLevel, string> = {
        error: 'color:#e74c3c;font-weight:bold',
        warn: 'color:#e67e22;font-weight:bold',
        info: 'color:#3498db',
        debug: 'color:#95a5a6',
      }
      const prefix = `[${tag}]`
      const consoleFn = level === 'error' ? console.error
        : level === 'warn' ? console.warn
        : level === 'info' ? console.info
        : console.debug

      consoleFn(`%c${prefix} %c${message}`, styles[level], 'color:inherit', { ...entry, meta: maskSensitive(meta) })
      return
    }

    // 生产环境：console + 后端上报
    if (level === 'error') {
      _reportError(entry)
    }
    console.error(JSON.stringify(entry))
  }

  return {
    error: (msg, meta, err) => log('error', msg, meta, err),
    warn: (msg, meta) => log('warn', msg, meta),
    info: (msg, meta) => log('info', msg, meta),
    debug: (msg, meta) => log('debug', msg, meta),
  }
}
