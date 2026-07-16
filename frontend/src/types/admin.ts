export interface AdminStats {
  total_users: number
  total_properties: number
  total_bookings: number
  pending_bookings: number
  properties_by_district: { district: string; count: number }[]
}

export interface EmbeddingStats {
  total: number
  completed: number
  failed: number
  pending: number
}

export interface AuditLog {
  id: number
  user_id: number | null
  action: string
  resource_type: string | null
  resource_id: number | null
  details: Record<string, unknown> | null
  ip_address: string | null
  created_at: string
}

export interface ImportTask {
  id: number
  admin_id: number
  source_name: string
  source_type: string
  status: string
  total_records: number
  success_records: number
  failed_records: number
  created_at: string
}

export interface ImportTaskDetail extends ImportTask {
  error_log: { row: number; error: string; type?: string }[] | null
  updated_at: string
}

export interface ImportError {
  row: number
  error: string
  type?: 'duplicate' | 'missing_field' | 'format_error' | 'unknown'
}

export interface ImportResult {
  id: number
  source_name: string
  source_type: string
  status: string
  total_records: number
  success_records: number
  failed_records: number
  error_log?: ImportError[] | null
  created_at?: string
  updated_at?: string
}

/** 列映射结果 */
export interface ColumnMapping {
  matched: Record<string, string>       // {原始列名: 标准字段名}
  unmatched: string[]                    // 无法匹配的列名
  confidence: Record<string, string>     // {原始列名: "exact"|"fuzzy"}
}

/** Phase 1 上传预览响应 */
export interface ImportPreview {
  task_id: number
  file_name: string
  column_mapping: ColumnMapping
  headers: string[]
  preview_rows: Record<string, string>[]
  total_rows: number
  valid_rows: number
  incomplete_rows: number
  outlier_rows: number[]
  outlier_warnings: ImportWarning[]
  missing_required: string[]
}

/** 异常警告 */
export interface ImportWarning {
  row: number
  field: string
  value: string | number
  reason: string
  severity: 'high' | 'medium'
}

/** 租金预估结果 */
export interface RentEstimate {
  predicted: number
  lower_bound: number
  upper_bound: number
  feature_importance: Record<string, number>
  model_metrics?: {
    mae: number | null
    mape: number | null
  }
}

/** 批量租金预估结果 */
export interface BatchRentEstimate {
  predictions: number[]
  warnings: {
    row: number
    actual: number
    predicted: number
    deviation_pct: number
  }[]
  warning_count: number
}

/** LLM 解析结果 */
export interface ParsedProperty {
  title?: string
  address?: string
  district?: string
  price_monthly?: number
  deposit_amount?: number
  service_fee_rate?: number
  bedrooms?: number
  bathrooms?: number
  area_sqm?: number
  property_type?: string
  description?: string
  amenities?: string[]
  building_name?: string
  room_number?: string
  floor?: number
  orientation?: string
  unrecognized?: string[]
  confidence?: string
}
