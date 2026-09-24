// 统一新建公寓弹窗的基础校验测试。
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import BuildingCreateDialog from '../BuildingCreateDialog.vue'

vi.mock('@/services/building', () => ({ buildingService: { create: vi.fn() } }))
vi.mock('@/services/api', () => ({ toUserFriendly: () => '创建失败' }))

describe('BuildingCreateDialog', () => {
  it('renders the shared address, coordinates and image fields', () => {
    const wrapper = mount(BuildingCreateDialog, {
      props: { modelValue: true },
      global: { stubs: {
        ElDialog: { template: '<div><slot/><slot name="footer"/></div>' },
        ElFormItem: { props: ['label'], template: '<div>{{ label }}<slot/></div>' },
        ElAlert: { props: ['title', 'description'], template: '<div>{{ title }} {{ description }}</div>' },
        ImageUploader: { template: '<div>公寓照片</div>' },
      } },
    })
    expect(wrapper.text()).toContain('公寓名称')
    expect(wrapper.text()).toContain('国家 / 地区')
    expect(wrapper.text()).toContain('官方英文地址')
    expect(wrapper.text()).toContain('地图坐标')
    expect(wrapper.text()).toContain('公寓照片')
  })
})
