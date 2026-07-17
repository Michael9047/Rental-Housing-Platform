// Matches backend: app/models/property.py
export type PropertyType = 'apartment' | 'house' | 'studio' | 'shared'
export type PropertyStatus = 'available' | 'pending_review' | 'rented' | 'maintenance' | 'offline'
export type RentType = 'monthly' | 'quarterly' | 'yearly'
export type DepositType = 'one_month' | 'one_three' | 'two_month' | 'three_month' | 'half_month' | 'free' | 'custom'

export interface Property {
  id: number
  landlord_id: number
  institute_id?: number | null
  institute_name?: string | null
  title: string
  description: string
  deposit_amount?: number
  service_fee_rate?: number | null
  min_lease_months: number
  max_lease_months?: number | null
  rent_type: RentType
  room_number?: string | null
  floor?: number | null
  address: string
  district: string
  country?: string
  price_monthly: number
  area_sqm: number | null
  bedrooms: number
  bathrooms: number
  property_type: PropertyType
  status: PropertyStatus
  latitude: number | null
  longitude: number | null
  amenities?: string[] | null
  available_from?: string | null
  min_stay_months?: number
  deposit_type?: DepositType | null
  version: number
  deleted_at?: string | null
  created_at: string
  updated_at: string
  images?: PropertyImage[]
  primary_image_url?: string | null
  similarity?: number | null
}

export interface PropertyCreate {
  title: string
  description?: string
  address: string
  district: string
  country?: string
  price_monthly: number
  area_sqm?: number
  bedrooms?: number
  bathrooms?: number
  property_type?: PropertyType
  status?: PropertyStatus
  latitude?: number
  longitude?: number
  landlord_id: number
  institute_id: number
  deposit_amount?: number
  service_fee_rate?: number
  room_number?: string
  floor?: number
  amenities?: string[]
  available_from?: string
  min_stay_months?: number
  deposit_type?: DepositType
  image_urls?: string[]
}

export interface PropertyUpdate {
  title?: string
  description?: string
  address?: string
  district?: string
  country?: string
  price_monthly?: number
  area_sqm?: number
  bedrooms?: number
  bathrooms?: number
  property_type?: PropertyType
  status?: PropertyStatus
  latitude?: number
  longitude?: number
  deposit_amount?: number
  service_fee_rate?: number
  room_number?: string
  floor?: number
  institute_id?: number
  amenities?: string[]
  available_from?: string
  min_stay_months?: number
  deposit_type?: DepositType
  version?: number
}

export interface PropertySearchResult extends Property {
  similarity: number | null
}

export interface PropertySearchParams {
  q?: string
  country?: string
  district?: string
  overseas_area?: string
  price_min?: number
  price_max?: number
  bedrooms?: number
  property_type?: PropertyType
  limit?: number
}

export interface PropertyListResponse {
  items: Property[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface PropertyImage {
  id: number
  property_id: number
  filename: string
  original_name: string
  mime_type: string
  file_size: number
  sort_order: number
  is_primary: boolean
  created_at: string
}
