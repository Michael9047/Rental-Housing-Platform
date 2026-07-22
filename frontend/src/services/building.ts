import api from './api'

export interface Building {
  id: number; name: string; address?: string
  contact_phone?: string; contact_email?: string
  description?: string; status: string; created_by: number
  created_at?: string
  latitude?: number | null; longitude?: number | null
  business_id?: string
}

export const buildingService = {
  list(params?: { skip?: number; limit?: number }): Promise<Building[]> {
    return api.get('/buildings', { params }).then(r => r.data)
  },
  create(data: { name: string; address?: string; contact_phone?: string; description?: string }): Promise<Building> {
    return api.post('/buildings', data).then(r => r.data)
  },
  get(id: number): Promise<Building> {
    return api.get(`/buildings/${id}`).then(r => r.data)
  },
  update(id: number, data: Partial<Building>): Promise<Building> {
    return api.patch(`/buildings/${id}`, data).then(r => r.data)
  },
  remove(id: number): Promise<void> {
    return api.delete(`/buildings/${id}`)
  },
}
