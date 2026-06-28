import api from './api'
import type { Booking, BookingCreate } from '@/types/booking'

export const bookingService = {
  create(data: BookingCreate): Promise<Booking> {
    return api.post('/bookings', data).then((r) => r.data)
  },

  list(): Promise<Booking[]> {
    return api.get('/bookings').then((r) => r.data)
  },

  getById(id: number): Promise<Booking> {
    return api.get(`/bookings/${id}`).then((r) => r.data)
  },

  updateStatus(id: number, status: 'approved' | 'rejected' | 'completed'): Promise<Booking> {
    return api.patch(`/bookings/${id}/status`, { status }).then((r) => r.data)
  },

  cancel(id: number): Promise<Booking> {
    return api.patch(`/bookings/${id}/cancel`).then((r) => r.data)
  },
}
