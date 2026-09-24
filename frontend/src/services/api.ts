import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,  // 60s，导入/上传等耗时操作需要较长超时
  headers: {
    'Content-Type': 'application/json',
  },
  paramsSerializer: {
    indexes: null,  // 数组参数用 ?a=1&a=2 而非 ?a[]=1&a[]=2（FastAPI 兼容）
  },
})

/** 生成简短的 UUID v4（零依赖） */
function generateRequestId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

// Request interceptor: attach Authorization header + X-Request-ID
api.interceptors.request.use(
  (config) => {
    // 生成并注入 request-ID（镜像后端 RequestLoggingMiddleware）
    const requestId = generateRequestId()
    config.headers['X-Request-ID'] = requestId
    // 存入全局变量供 logger 引用
    ;(window as any).__currentRequestId = requestId

    // 登录/注册/刷新 token 等公开接口不附加旧 token
    const path = config.url || ''
    const isPublic = path.includes('/auth/login') || path.includes('/auth/register')
      || path.includes('/auth/refresh') || path.includes('/auth/phone')
      || path.includes('/auth/send-sms') || path.includes('/auth/verify-sms')
    if (!isPublic) {
      const token = localStorage.getItem('access_token') || localStorage.getItem('guest_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }
    return config
  },
  (error) => Promise.reject(error),
)

// Helper: extract error message from backend's {error:{message:"..."}} format
// or standard {detail:"..."} format (both are used in this project)
export function extractErrorMessage(error: any): string | null {
  const data = error.response?.data

  // Backend format: { error: { message: "..." } }
  const msg = data?.error?.message
  if (msg && typeof msg === 'string') return msg

  // Standard FastAPI format: { detail: "..." }
  const detail = data?.detail
  if (detail && typeof detail === 'string') return detail

  // FastAPI validation errors (array format)
  if (Array.isArray(detail) && detail.length > 0) {
    const locs = detail.map((d: any) => {
      const field = (d.loc || []).filter((l: string) => l !== 'body' && l !== 'path' && l !== 'query').join('.')
      return field ? `${field}: ${d.msg}` : d.msg
    }).filter(Boolean)
    if (locs.length > 0) return locs.join('; ')
  }

  // Raw validation error list (non-array detail, e.g. direct list)
  if (Array.isArray(data) && data.length > 0 && data[0].msg) {
    const locs = data.map((d: any) => {
      const field = (d.loc || []).filter((l: string) => l !== 'body' && l !== 'path' && l !== 'query').join('.')
      return field ? `${field}: ${d.msg}` : d.msg
    }).filter(Boolean)
    if (locs.length > 0) return locs.join('; ')
  }

  // Plain string response
  if (typeof data === 'string' && data) return data

  return null
}

// ── 生产环境：按 HTTP 状态码映射为用户可读的提示语 ──
/** 状态码 → 用户友好的错误提示（不暴露后端技术细节） */
const FRIENDLY_ERRORS: Record<number, string> = {
  400: '提交的信息有误，请检查后重试',
  401: '登录已过期，请重新登录',
  403: '没有权限执行此操作',
  404: '未找到请求的资源',
  422: '输入信息格式有误，请检查后重试',
  429: '操作太频繁，请稍后再试',
  500: '服务器内部错误，请稍后重试',
}

/** 生产环境下将后端错误原文转为用户友好提示。
 *  外部文件可通过 import { toUserFriendly } from '@/services/api' 使用。 */
export function toUserFriendly(error: any): string {
  const status = error.response?.status
  // 优先用状态码映射
  if (status && FRIENDLY_ERRORS[status]) return FRIENDLY_ERRORS[status]

  const raw = extractErrorMessage(error)
  if (!raw) return '操作失败，请稍后重试'

  // 短消息（≤20字）通常是后端已经写好的用户提示，可以直接用
  if (raw.length <= 20) return raw

  // 长消息是技术细节，截断并加通用后缀
  // 开发环境：只放行短用户提示（≤60字），排除明显是技术报错的消息
  if (import.meta.env.DEV && raw.length <= 60 && !raw.includes('Traceback') && !raw.includes('Exception')) return raw
  return raw.slice(0, 20) + '…'
}

// 错误弹窗去重：相同消息 2 秒内只弹一次
let lastToastMessage = ''
let lastToastTime = 0

function showErrorToast(message: string) {
  const now = Date.now()
  if (message === lastToastMessage && now - lastToastTime < 2000) return
  lastToastMessage = message
  lastToastTime = now
  ElMessage.error(message)
}

// 5xx 聚合：短时间内多个 5xx 合并为一条
let serverErrorCount = 0
let serverErrorTimer: ReturnType<typeof setTimeout> | null = null

function showServerErrorToast(serverMsg: string | null, requestId: string) {
  serverErrorCount++
  if (serverErrorTimer) clearTimeout(serverErrorTimer)
  // 延迟 1.5 秒聚合，期间出现的 5xx 都计入同一条
  serverErrorTimer = setTimeout(() => {
    const idSuffix = requestId ? ` (ID: ${requestId.slice(0, 8)})` : ''
    if (serverErrorCount > 1) {
      ElMessage.error(`服务器错误，影响了 ${serverErrorCount} 个请求${idSuffix}`)
    } else if (serverMsg) {
      ElMessage.error(`${serverMsg}${idSuffix}`)
    } else {
      ElMessage.error(`服务器错误，请稍后重试${idSuffix}`)
    }
    serverErrorCount = 0
    serverErrorTimer = null
  }, 1500)
}

// Response interceptor: handle 401, network errors, show errors
api.interceptors.response.use(
  (response) => {
    // 提取后端 X-Request-ID 存入全局变量
    const backendRequestId = response.headers['x-request-id']
    if (backendRequestId) {
      ;(window as any).__currentRequestId = backendRequestId
    }
    return response
  },
  (error) => {
    const isLoginPage = window.location.pathname === '/login'
    const hadToken = !!localStorage.getItem('access_token')
    const isDev = import.meta.env.DEV

    // 技术细节写入 console（开发时可见，生产走 logger → 文件）
    if (!isDev) {
      console.error('[API Error]', error.response?.status, toUserFriendly(error), extractErrorMessage(error))
    }

    if (error.response?.status === 401) {
      // 仅在用户之前已登录（有过 token）的情况下才跳转登录页
      if (!isLoginPage && hadToken) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        window.location.href = '/login'
        return Promise.reject(error)
      }
      // 未登录 / 已在登录页的 401：去重弹窗（调用方标记 _handled 时跳过）
      if (!error.config?._handled) {
        showErrorToast(toUserFriendly(error))
      }
      return Promise.reject(error)
    }
    // 网络错误 / 服务器不可达（error.response 为 undefined）
    if (!error.response) {
      if (error.config?._handled) return Promise.reject(error)
      if (error.code === 'ECONNABORTED') {
        showErrorToast('请求超时，请检查网络连接后重试')
      } else {
        showErrorToast('网络连接失败，请检查网络后重试')
      }
      return Promise.reject(error)
    }
    // 调用方标记 _handled 时跳过全局错误弹窗
    if (error.config?._handled) return Promise.reject(error)
    // 404 不弹全局错误——由调用方自行处理（如草稿不存在属正常流程）
    if (error.response?.status === 404) {
      return Promise.reject(error)
    }
    // 5xx 错误：聚合弹窗避免刷屏（后端挂了时多个请求同时失败只弹一条）
    if (error.response?.status >= 500) {
      const requestId = error.config?.headers?.['X-Request-ID'] || 'unknown'
      showServerErrorToast(toUserFriendly(error), requestId)
      return Promise.reject(error)
    }
    const message = toUserFriendly(error)
    if (message) showErrorToast(message)
    return Promise.reject(error)
  },
)

export default api
