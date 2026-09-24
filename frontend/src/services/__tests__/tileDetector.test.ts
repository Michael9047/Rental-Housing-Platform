// 地图瓦片提供商选择规则测试
import { describe, expect, it } from 'vitest'

import { getTileProvider } from '@/services/tileDetector'

describe('getTileProvider', () => {
  it.each(['CN', 'cn', 'CHN', 'China', '中国', '中华人民共和国'])(
    '国内国家值 %s 使用高德地图',
    (country) => {
      expect(getTileProvider(country)).toBe('amap')
    },
  )

  it.each(['GB', 'SG', 'US', 'United Kingdom', undefined, null, ''])(
    '海外或缺失国家值 %s 使用 Google 地图',
    (country) => {
      expect(getTileProvider(country)).toBe('google')
    },
  )
})
