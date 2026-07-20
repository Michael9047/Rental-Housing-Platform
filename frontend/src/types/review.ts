/** 评价系统类型定义 */
export type ReviewStatus = 'pending' | 'approved' | 'rejected'

export interface ReviewPublic {
  id: number
  property_id: number
  landlord_id: number

  property_rating: number
  property_comment: string | null
  property_images: string[] | null

  landlord_rating: number | null
  landlord_comment: string | null
  landlord_images: string[] | null

  created_at: string
  tenant_name: string | null
  property_title: string | null
}

export interface ReviewRead extends ReviewPublic {
  tenant_id: number
  booking_id: number | null
  status: ReviewStatus
  updated_at: string
}

export interface ReviewCreate {
  booking_id: number
  property_rating: number
  property_comment?: string
  property_images?: string[]

  landlord_rating?: number | null
  landlord_comment?: string
  landlord_images?: string[]
}

export interface ReviewAggregation {
  property_id?: number | null
  landlord_id?: number | null
  avg_property_rating: number | null
  avg_landlord_rating: number | null
  total_reviews: number
}
