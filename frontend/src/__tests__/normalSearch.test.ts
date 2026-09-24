// 普通搜索导航参数测试：搜索框文字必须原样保留，且每次提交都是独立事件。
import { describe, expect, it } from 'vitest'
import { normalSearchQuery } from '@/utils/normalSearch'

describe('normalSearchQuery', () => {
  it('原样保留用户输入的搜索文字', () => {
    const query = normalSearchQuery({ city: 'London' }, '  UCL 附近  ')

    expect(query.city).toBe('London')
    expect(query.q).toBe('  UCL 附近  ')
  })

  it('相同搜索文字重复提交也会生成不同事件', () => {
    const first = normalSearchQuery({ q: '伦敦' }, '伦敦')
    const second = normalSearchQuery({ q: '伦敦' }, '伦敦')

    expect(first.search_id).not.toBe(second.search_id)
  })
})
