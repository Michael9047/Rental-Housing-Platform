import api from './api'
import type {
  Property,
  PropertyCreate,
  PropertyUpdate,
  PropertySearchResult,
  PropertySearchParams,
} from '@/types/property'

export const propertyService = {
  list(params?: { skip?: number; limit?: number; district?: string; status?: string }): Promise<Property[]> {
    return api.get('/properties', { params }).then((r) => r.data)
  },

  search(params: PropertySearchParams): Promise<PropertySearchResult[]> {
    return api.get('/properties/search', { params }).then((r) => r.data)
  },

  getById(id: number): Promise<Property> {
    return api.get(/properties/).then((r) => r.data)
  },

  create(data: PropertyCreate): Promise<Property> {
    return api.post('/properties', data).then((r) => r.data)
  },

  update(id: number, data: PropertyUpdate): Promise<Property> {
    return api.patch(/properties/, data).then((r) => r.data)
  },

  delete(id: number): Promise<void> {
    return api.delete(/properties/)
  },
}
