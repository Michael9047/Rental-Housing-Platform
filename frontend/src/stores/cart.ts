// 候选清单（购物车）store —— 全站唯一数据源
// 导航角标、房源卡片「+」、候选清单页、推荐管家抽屉共享同一份状态
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { agentService } from '@/services/agent'
import type { CartItem } from '@/types/agent'

export const useCartStore = defineStore('cart', () => {
  const items = ref<CartItem[]>([])
  const loaded = ref(false)

  const count = computed(() => items.value.length)

  function has(propertyId: number): boolean {
    return items.value.some((it) => it.property_id === propertyId)
  }

  /** 拉取当前用户购物车（登录后调用；失败静默） */
  async function fetch(): Promise<void> {
    try {
      const cart = await agentService.getCart()
      items.value = cart.items
      loaded.value = true
    } catch {
      // 未登录或接口异常时忽略，交由拦截器统一提示
    }
  }

  /** 加入候选清单（幂等：已在清单内则跳过） */
  async function add(propertyId: number, reason?: string): Promise<boolean> {
    if (has(propertyId)) return false
    const item = await agentService.addCartItem(propertyId, reason)
    if (!has(item.property_id)) items.value.push(item)
    return true
  }

  /** 从候选清单移除 */
  async function remove(propertyId: number): Promise<void> {
    await agentService.removeCartItem(propertyId)
    items.value = items.value.filter((it) => it.property_id !== propertyId)
  }

  /** 退出登录等场景清空本地状态 */
  function clear(): void {
    items.value = []
    loaded.value = false
  }

  return { items, loaded, count, has, fetch, add, remove, clear }
})
