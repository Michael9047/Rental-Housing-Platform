// 最近搜索推荐降级链测试。
import {
  RECENT_HOUSING_SEARCH_KEY,
  buildRecommendationQueries,
  loadRecentHousingSearch,
  saveRecentHousingSearch,
} from '@/utils/recentHousingSearch'

describe('recentHousingSearch', () => {
  beforeEach(() => localStorage.clear())

  it('保存并恢复学校位置上下文', () => {
    saveRecentHousingSearch({
      kind: 'school', schoolId: 7, schoolName: 'UCL',
      latitude: 51.5246, longitude: -0.134, city: 'London', country: 'GB',
    })

    expect(loadRecentHousingSearch()).toMatchObject({
      kind: 'school', schoolId: 7, schoolName: 'UCL', city: 'London', country: 'GB',
    })
  })

  it('学校搜索依次降级到城市和默认推荐', () => {
    const queries = buildRecommendationQueries({
      kind: 'school', latitude: 51.5, longitude: -0.1,
      radiusKm: 5, city: 'London', country: 'GB', savedAt: 1,
    })

    expect(queries).toEqual([
      { near_lat: 51.5, near_lng: -0.1, near_distance_km: 5, limit: 18 },
      { city: 'London', country: 'GB', limit: 18 },
      { limit: 18 },
    ])
  })

  it('区域搜索依次降级到城市和默认推荐', () => {
    expect(buildRecommendationQueries({
      kind: 'district', district: 'Camden', city: 'London', country: 'GB', savedAt: 1,
    })).toEqual([
      { district: 'Camden', country: 'GB', limit: 18 },
      { city: 'London', country: 'GB', limit: 18 },
      { limit: 18 },
    ])
  })

  it('忽略损坏的本地记录', () => {
    localStorage.setItem(RECENT_HOUSING_SEARCH_KEY, '{bad json')
    expect(loadRecentHousingSearch()).toBeNull()
  })
})
