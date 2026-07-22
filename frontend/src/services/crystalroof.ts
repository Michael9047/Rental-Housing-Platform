import api from './api'

/** CrystalRoof 评分响应 */
export interface CrystalRoofScore {
  address: string
  search_url: string        // 始终返回 - CrystalRoof 搜索页 URL
  report_url: string | null // 报告页 URL（解析 postcode 时）
  overall_score: number | null
  subscores: Record<string, number> | null
  postcode: string | null
  fetched: boolean          // 是否从网站实际获取到评分
  source: string
}

export const crystalRoofService = {
  /**
   * 获取地址对应的 CrystalRoof 评分
   * @param address 完整地址（建议包含 UK 城市/邮编）
   * @param country 国家代码（可选，例如 'GB'）
   */
  async getScore(address: string, country?: string): Promise<CrystalRoofScore> {
    return api
      .get('/crystalroof/score', { params: { address, country } })
      .then((r) => r.data)
  },
}
