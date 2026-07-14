import api from './api'

/** ScoreMyStreet 评分响应 */
export interface ScoreMyStreetScore {
  postcode: string | null
  report_url: string
  search_url: string
  overall_score: number | null
  safety_score: number | null
  schools_score: number | null
  amenities_score: number | null
  transport_score: number | null
  connectivity_score: number | null
  area_name: string | null
  crime_count: number | null
  crime_rate: string | null
  crime_types: Record<string, number> | null
  postcode_district: string | null
  date_processed: string | null
  fetched: boolean
  source: string
  schools_count: number | null
  schools_info: string | null
  supermarkets_count: number | null
  parks_count: number | null
  gyms_count: number | null
  ev_charging_count: number | null
  nearest_station: string | null
  nearest_station_distance: number | null
  stations_count: number | null
  full_fibre_coverage: string | null
  ultrafast_coverage: string | null
  superfast_coverage: string | null
}

export const scoreMyStreetService = {
  /**
   * 获取地址对应的 ScoreMyStreet 评分
   * @param address 完整地址（应包含 UK 邮编）
   * @param country 国家代码（可选，例如 'GB'）
   */
  async getScore(address: string, country?: string): Promise<ScoreMyStreetScore> {
    return api
      .get('/scoremystreet/score', { params: { address, country } })
      .then((r) => r.data)
  },
}
