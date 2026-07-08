// Matches backend: app/models/property.py
export type PropertyType = 'apartment' | 'house' | 'studio' | 'shared'
export type PropertyStatus = 'available' | 'rented' | 'maintenance' | 'offline'
export type RentType = 'monthly' | 'quarterly' | 'yearly'

// Matches backend: app/schemas/property.py PropertyRead
export interface Property {
  id: number
  landlord_id: number
  title: string
  description: string
  deposit_amount?: number
  service_fee_rate?: number | null
  min_lease_months: number
  max_lease_months?: number | null
  rent_type: RentType
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
  created_at: string
  updated_at: string
  images?: PropertyImage[]
  primary_image_url?: string | null
  similarity?: number | null
}

// Matches backend: app/schemas/property.py PropertyCreate
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
}

// Matches backend: app/schemas/property.py PropertySearchResult
export interface PropertySearchResult extends Property {
  similarity: number | null
}

// Search parameters matching backend query params (GET /properties/search)
// Note: country/overseas_area are frontend-only filters; backend maps them to district
export interface PropertySearchParams {
  q?: string              // Natural language query → backend pgvector search
  country?: string         // ⚠️ Frontend filter; mapped to district before sending
  district?: string        // Backend-supported
  overseas_area?: string   // ⚠️ Frontend filter; mapped to district before sending
  price_min?: number       // Backend-supported
  price_max?: number       // Backend-supported
  bedrooms?: number        // Backend-supported
  property_type?: PropertyType  // Backend-supported
  limit?: number           // Backend-supported (1-100)
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

