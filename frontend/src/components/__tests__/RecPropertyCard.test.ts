// AI 推荐房源卡周边 POI 展示回归测试。
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'
import RecPropertyCard from '@/components/RecPropertyCard.vue'
import type { AgentRecommendation } from '@/types/agent'

function recommendation(): AgentRecommendation {
  return {
    property_id: 546,
    rank: 1,
    match_reason: '符合当前条件',
    pros: [],
    cons: [],
    property: {
      id: 546,
      unit_type_id: 546,
      name: '测试户型',
      institute_name: '测试公寓',
      base_rent: 2500,
      currency: 'CNY',
      has_vacancy: true,
      available_count: 1,
      total_count: 1,
      landlord_id: 0,
      title: '测试户型',
      bedrooms: 1,
      bathrooms: 1,
      status: 'available',
      images: [],
      image_urls: [],
    },
    poi_distances: {
      metro: 69,
      bus: 120,
      market: 280,
      food: 430,
      hospital: 1200,
      gym: 590,
    },
  }
}

describe('RecPropertyCard 周边信息', () => {
  it('以真实公寓名称为主标题、户型名称为副标题', () => {
    const wrapper = mount(RecPropertyCard, {
      props: {
        rec: recommendation(),
        selected: false,
        inCart: false,
      },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.get('.title-group h3').text()).toBe('测试公寓')
    expect(wrapper.get('.unit-type-name').text()).toBe('测试户型')
  })

  it('公寓名称缺失时保持为空，不生成任何替代名称', () => {
    const rec = recommendation()
    rec.property.institute_name = ''
    rec.property.district = '工业园区'
    const wrapper = mount(RecPropertyCard, {
      props: { rec, selected: false, inCart: false },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.get('.title-group h3').text()).toBe('')
    expect(wrapper.get('.title-group').text()).not.toContain('工业园区公寓')
  })

  it('显示后端当前返回的 POI 键和距离', () => {
    const wrapper = mount(RecPropertyCard, {
      props: {
        rec: recommendation(),
        selected: false,
        inCart: false,
      },
      global: { plugins: [ElementPlus] },
    })

    const nearby = wrapper.get('.nearby-row').text()
    expect(nearby).toContain('地铁 69m')
    expect(nearby).toContain('公交 120m')
    expect(nearby).toContain('超市 280m')
    expect(nearby).toContain('餐饮 430m')
    expect(nearby).not.toContain('数据待补充')
  })
})
