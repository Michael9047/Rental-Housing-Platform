// 前端错误类型定义：结构化错误分类、应用错误类、工具函数

/** 错误分类枚举（镜像后端三层异常处理器） */
export enum ErrorCategory {
  /** 网络不可达、超时 */
  NETWORK = 'network',
  /** 401 未授权、token 过期 */
  AUTH = 'auth',
  /** 422 表单验证失败 */
  VALIDATION = 'validation',
  /** 404 资源不存在 */
  NOT_FOUND = 'not_found',
  /** 500 服务器内部错误 */
  SERVER = 'server',
  /** 无法归类 */
  UNKNOWN = 'unknown',
}

/** 结构化错误对象（镜像后端 JsonFormatter 输出字段） */
export interface StructuredError {
  /** 错误唯一标识（uuid4） */
  id: string
  /** 发生时间（ISO 8601） */
  timestamp: string
  /** 错误分类 */
  category: ErrorCategory
  /** 用户可读的错误消息 */
  message: string
  /** 原始错误对象 */
  originalError?: unknown
  /** 后端 request-ID（用于跨服务关联） */
  requestId?: string
  /** HTTP 状态码 */
  statusCode?: number
  /** 请求 URL */
  url?: string
}

/** 从 HTTP 状态码推断错误分类 */
export function categorizeByStatus(status: number): ErrorCategory {
  if (status === 0 || status === undefined) return ErrorCategory.NETWORK
  if (status === 401) return ErrorCategory.AUTH
  if (status === 404) return ErrorCategory.NOT_FOUND
  if (status === 422) return ErrorCategory.VALIDATION
  if (status >= 400 && status < 500) return ErrorCategory.UNKNOWN
  if (status >= 500) return ErrorCategory.SERVER
  return ErrorCategory.UNKNOWN
}

/** 生成简短的 UUID v4（零依赖） */
export function generateErrorId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

/** 从 Axios 错误对象构建 StructuredError */
export function buildStructuredError(err: any): StructuredError {
  const statusCode = err?.response?.status || 0
  const message = (err?.response?.data?.error?.message
    || err?.response?.data?.detail
    || err?.message
    || '未知错误') as string

  return {
    id: generateErrorId(),
    timestamp: new Date().toISOString(),
    category: categorizeByStatus(statusCode),
    message,
    originalError: err,
    requestId: err?.config?.headers?.['X-Request-ID'] || undefined,
    statusCode: statusCode || undefined,
    url: err?.config?.url || undefined,
  }
}

/** 应用自定义错误类，支持分类标记 */
export class AppError extends Error {
  category: ErrorCategory
  requestId?: string

  constructor(message: string, category: ErrorCategory = ErrorCategory.UNKNOWN, requestId?: string) {
    super(message)
    this.name = 'AppError'
    this.category = category
    this.requestId = requestId
  }
}
