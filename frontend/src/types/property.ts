// Matches backend: app/models/property.py
export type PropertyType = 'apartment' | 'house' | 'studio' | 'shared'
export type PropertyStatus = 'available' | 'rented' | 'maintenance' | 'offline'

// Matches backend: app/schemas/property.py PropertyRead
export interface Property {
  id: number
  landlord_id: number
  title: string
  description: string | null
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
