import api from './api'
import type { ReviewCreate, ReviewPublic, ReviewRead, ReviewAggregation } from '@/types/review'

export const reviewService = {
  /** 创建评价 */
  create(data: ReviewCreate): Promise<ReviewRead> {
    return api.post('/reviews', data).then((r) => r.data)
  },

  /** 房源评价列表（公开） */
  listByProperty(propertyId: number, skip = 0, limit = 50): Promise<ReviewPublic[]> {
    return api.get(`/reviews/property/${propertyId}`, { params: { skip, limit } }).then((r) => r.data)
  },

  /** 房源评价统计 */
  propertyStats(propertyId: number): Promise<ReviewAggregation> {
    return api.get(`/reviews/property/${propertyId}/stats`).then((r) => r.data)
  },

  /** 个人房东评价列表（公开） */
  listByLandlord(landlordId: number, skip = 0, limit = 50): Promise<ReviewPublic[]> {
    return api.get(`/reviews/landlord/${landlordId}`, { params: { skip, limit } }).then((r) => r.data)
  },

  /** 个人房东评价统计 */
  landlordStats(landlordId: number): Promise<ReviewAggregation> {
    return api.get(`/reviews/landlord/${landlordId}/stats`).then((r) => r.data)
  },

  /** 我的评价历史 */
  myReviews(skip = 0, limit = 50): Promise<ReviewRead[]> {
    return api.get('/reviews/my', { params: { skip, limit } }).then((r) => r.data)
  },
}
