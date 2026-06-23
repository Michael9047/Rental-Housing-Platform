// Matches backend: app/models/property.py
export type PropertyType = 'apartment' | 'house' | 'studio' | 'shared'
export type PropertyStatus = 'available' | 'rented' | 'maintenance' | 'offline'

// Matches backend: app/schemas/property.py PropertyRead
export interface Property {
  id: number
  landlord_id: number
  title: string
  description: string
  deposit_amount?: number
  service_fee_rate?: number | null
  address: string
  district: string
  price_monthly: number
  area_sqm: number | null
  bedrooms: number
  bathrooms: number
  property_type: PropertyType
  status: PropertyStatus
  latitude: number | null
  longitude: number | null
  created_at: string
  updated_at: string
  images?: PropertyImage[]
  primary_image_url?: string | null
}

// Matches backend: app/schemas/property.py PropertyCreate
export interface PropertyCreate {
  title: string
  description?: string
  address: string
  district: string
  price_monthly: number
  area_sqm?: number
  bedrooms?: number
  bathrooms?: number
  property_type?: PropertyType
  status?: PropertyStatus
  latitude?: number
  longitude?: number
  landlord_id: number
}

// Matches backend: app/schemas/property.py PropertyUpdate
export interface PropertyUpdate {
  title?: string
  description?: string
  address?: string
  district?: string
  price_monthly?: number
  area_sqm?: number
  bedrooms?: number
  bathrooms?: number
  property_type?: PropertyType
  status?: PropertyStatus
  latitude?: number
  longitude?: number
}

// Matches backend: app/schemas/property.py PropertySearchResult
export interface PropertySearchResult extends Property {
  similarity: number | null
}

// Search parameters matching backend query params
export interface PropertySearchParams {
  q?: string
  district?: string
  price_min?: number
  price_max?: number
  bedrooms?: number
  property_type?: PropertyType
  limit?: number
}


// Property Image
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
