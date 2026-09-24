import { beforeEach, describe, expect, it, vi } from 'vitest'

const { getMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
}))

vi.mock('@/services/api', () => ({
  default: { get: getMock },
}))

import { universityService } from '@/services/university'

describe('universityService.search', () => {
  beforeEach(() => {
    getMock.mockReset()
    getMock.mockResolvedValue({ data: [] })
  })

  it('空查询加载热门大学时不发送空 q 参数', async () => {
    await universityService.search('   ', 20)

    expect(getMock).toHaveBeenCalledWith('/universities', {
      params: { limit: 20 },
    })
  })

  it('名称搜索会去除首尾空格', async () => {
    await universityService.search('  NUS  ', 10)

    expect(getMock).toHaveBeenCalledWith('/universities', {
      params: { q: 'NUS', limit: 10 },
    })
  })
})
