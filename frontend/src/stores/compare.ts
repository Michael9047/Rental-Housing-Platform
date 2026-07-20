/** 对比 Agent 状态管理 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { compareService } from '@/services/compare'
import type {
  ComparePriority,
  CompareMessage,
  DimensionScores,
  EnrichedPropertyData,
} from '@/types/compare'

export const useCompareStore = defineStore('compare', () => {
  // ── state ──
  const sessionId = ref<number | null>(null)
  const messages = ref<CompareMessage[]>([])
  const scores = ref<Record<number, DimensionScores>>({})
  const propertyData = ref<Record<number, EnrichedPropertyData>>({})
  const priority = ref<ComparePriority>('balanced')
  const reply = ref('')
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ── computed ──
  const propertyIds = computed(() => Object.keys(propertyData.value).map(Number))
  const dimensionKeys = computed(() => {
    const first = Object.values(scores.value)[0]
    return first ? Object.keys(first.breakdown) : []
  })

  // ── methods ──
  async function startComparison(ids: number[], prio: ComparePriority = 'balanced') {
    loading.value = true
    error.value = null
    try {
      const session = await compareService.createSession({
        property_ids: ids,
        priority: prio,
      })
      sessionId.value = session.id
      messages.value = session.messages
      priority.value = (session.priority as ComparePriority) || 'balanced'
      if (session.result_cache) {
        scores.value = session.result_cache.scores
        propertyData.value = session.result_cache.property_data
        reply.value = session.result_cache.reply
      }
    } catch (e: any) {
      error.value = e?.message || '对比分析失败'
    } finally {
      loading.value = false
    }
  }

  async function sendFollowup(message: string, newPriority?: ComparePriority | null) {
    if (!sessionId.value) return
    loading.value = true
    error.value = null
    try {
      const resp = await compareService.sendMessage(sessionId.value, {
        message,
        priority: newPriority || null,
      })
      scores.value = resp.scores
      propertyData.value = resp.property_data
      reply.value = resp.reply
      if (newPriority) priority.value = newPriority
    } catch (e: any) {
      error.value = e?.message || '追问失败'
    } finally {
      loading.value = false
    }
  }

  function reset() {
    sessionId.value = null
    messages.value = []
    scores.value = {}
    propertyData.value = {}
    priority.value = 'balanced'
    reply.value = ''
    loading.value = false
    error.value = null
  }

  return {
    sessionId,
    messages,
    scores,
    propertyData,
    priority,
    reply,
    loading,
    error,
    propertyIds,
    dimensionKeys,
    startComparison,
    sendFollowup,
    reset,
  }
})
