import api from './api'

export interface FavoriteItem {
  id: number
  user_id: number
  property_id: number
  created_at: string
}

export const favoriteService = {
  /** 获取当前用户收藏列表，可选按 property_id 筛选 */
  list(propertyId?: number): Promise<FavoriteItem[]> {
    return api.get('/favorites', { params: propertyId ? { property_id: propertyId } : {} }).then((r) => r.data)
  },

  /** 检查是否已收藏指定房源 */
  async isFavorited(propertyId: number): Promise<boolean> {
    const list = await this.list(propertyId)
    return list.length > 0
  },

  /** 新增收藏 */
  add(propertyId: number): Promise<FavoriteItem> {
    return api.post('/favorites', { property_id: propertyId }).then((r) => r.data)
  },

  /** 取消收藏 */
  remove(propertyId: number): Promise<void> {
    return api.delete(`/favorites/${propertyId}`)
  },
}
