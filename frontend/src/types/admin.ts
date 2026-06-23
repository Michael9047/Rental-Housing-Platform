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
  error_log: { row: number; error: string }[] | null
  updated_at: string
}

export interface ImportResult {
  id: number
  source_name: string
  source_type: string
  status: string
  total_records: number
  success_records: number
  failed_records: number
  error_log?: { row: number; error: string }[] | null
  created_at?: string
  updated_at?: string
}
