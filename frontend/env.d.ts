/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AMAP_KEY?: string
  readonly VITE_AMAP_SECURITY_JS_CODE?: string
  readonly VITE_CONTRACT_TEMPLATE_MANAGEMENT_ENABLED?: string
  /** 本地 Mailpit Web 收件箱地址；不应配置为单封邮件的 /view/{id} 地址。 */
  readonly VITE_MAILPIT_WEB_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

interface Window {
  _AMapSecurityConfig?: {
    securityJsCode: string
  }
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
