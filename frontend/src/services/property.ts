import api from './api'
import type {
  Property,
  PropertyCreate,
  PropertyUpdate,
  PropertySearchResult,
  PropertySearchParams,
  PropertyListResponse,
  PropertyImage,
} from '@/types/property'

export interface PropertyPOI {
  content: string
  poi_data: Record<string, { name: string; distance: string }[]>
  generated_at: string
}

export interface GeocodeResult {
  address: string
  latitude: number
  longitude: number
  formatted_address?: string | null
  level?: string | null
  province?: string | null
  city?: string | null
  district?: string | null
}

export const propertyService = {
  list(params?: { page?: number; page_size?: number; district?: string; status?: string; landlord_id?: number; keyword?: string; property_type?: string; price_min?: number; price_max?: number }): Promise<PropertyListResponse> {
    return api.get('/properties', { params }).then((r) => r.data)
  },

  listRecycleBin(params?: { page?: number; page_size?: number; landlord_id?: number }): Promise<PropertyListResponse> {
    return api.get('/properties/recycle-bin', { params }).then((r) => r.data)
  },

  restore(id: number | string): Promise<Property> {
    return api.post(`/properties/${id}/restore`).then((r) => r.data)
  },

  batchUpdateStatus(ids: number[], status: string): Promise<{ success: number; failed: number; errors?: any[] }> {
    return api.post('/properties/batch/status', { ids, status }).then((r) => r.data)
  },

  batchDelete(ids: number[]): Promise<{ success: number; failed: number }> {
    return api.post('/properties/batch/delete', { ids }).then((r) => r.data)
  },

  hardDelete(id: number | string): Promise<void> {
    return api.delete(`/properties/${id}/hard`)
  },

  batchRestore(ids: number[]): Promise<{ success: number; failed: number }> {
    return api.post('/properties/batch/restore', { ids }).then((r) => r.data)
  },

  batchHardDelete(ids: number[]): Promise<{ success: number; failed: number }> {
    return api.post('/properties/batch/hard-delete', { ids }).then((r) => r.data)
  },

  search(params: PropertySearchParams): Promise<PropertySearchResult[]> {
    return api.get('/properties/search', { params: { ...params, _t: Date.now() } }).then((r) => r.data)
  },

  getById(id: number | string): Promise<Property> {
    return api.get(`/properties/${id}`).then((r) => r.data)
  },

  create(data: PropertyCreate): Promise<Property> {
    return api.post('/properties', data).then((r) => r.data)
  },

  update(id: number | string, data: PropertyUpdate): Promise<Property> {
    return api.patch(`/properties/${id}`, data).then((r) => r.data)
  },

  geocodeAddress(address: string, city?: string): Promise<GeocodeResult> {
    return api.post('/geo/geocode', { address, city }).then((r) => ({
      ...r.data,
      latitude: Number(r.data.latitude),
      longitude: Number(r.data.longitude),
    }))
  },

  delete(id: number | string): Promise<void> {
    return api.delete(`/properties/${id}`)
  },

  // Image management
  listImages(propertyId: number | string): Promise<PropertyImage[]> {
    return api.get(`/properties/${propertyId}/images`).then((r) => r.data)
  },

  uploadImages(propertyId: number | string, files: File[]): Promise<PropertyImage[]> {
    const formData = new FormData()
    files.forEach((f) => formData.append('files', f))
    return api.post(`/properties/${propertyId}/images`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },

  deleteImage(propertyId: number | string, imageId: number | string): Promise<void> {
    return api.delete(`/properties/${propertyId}/images/${imageId}`)
  },

  setPrimaryImage(propertyId: number | string, imageId: number | string): Promise<PropertyImage> {
    return api.patch(`/properties/${propertyId}/images/${imageId}/primary`).then((r) => r.data)
  },

  // POI
  getPropertyPOI(propertyId: number | string): Promise<PropertyPOI | null> {
    return api.get(`/pois/${propertyId}`).then((r) => r.data).catch(() => null)
  },

  // ---- ML ----
  /** 智能租金预估 */
  estimateRent(params: {
    area_sqm?: number
    bedrooms?: number
    bathrooms?: number
    district?: string
    property_type?: string
    deposit_amount?: number
    service_fee_rate?: number
  }): Promise<import('@/types/admin').RentEstimate> {
    return api.get('/ml/rent-estimate', { params }).then((r) => r.data)
  },
}