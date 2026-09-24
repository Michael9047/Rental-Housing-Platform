/** 对比 Agent 状态管理 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { compareService } from '@/services/compare'
import type {
  ComparePriority,
  CompareMessage,
  CompareSessionResponse,
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
  const streamStatus = ref('')
  const loading = ref(false)
  const error = ref<string | null>(null)
  let requestEpoch = 0
  let streamController: AbortController | null = null

  // ── computed ──
  const propertyIds = computed(() => Object.keys(propertyData.value).map(Number))
  const dimensionKeys = computed(() => {
    const first = Object.values(scores.value)[0]
    return first ? Object.keys(first.breakdown) : []
  })

  // ── methods ──
  async function startComparison(ids: number[], prio: ComparePriority = 'balanced') {
    const epoch = ++requestEpoch
    streamController?.abort()
    const controller = new AbortController()
    streamController = controller
    loading.value = true
    error.value = null
    sessionId.value = null
    messages.value = []
    scores.value = {}
    propertyData.value = {}
    priority.value = prio
    reply.value = ''
    streamStatus.value = '正在整理对比数据'
    let finalSession: CompareSessionResponse | null = null
    try {
      await compareService.createSessionStream(
        { property_ids: ids, priority: prio },
        {
          onToken(token) {
            if (epoch === requestEpoch) reply.value += token
          },
          onMeta(meta) {
            if (epoch !== requestEpoch) return
            if (meta.event === 'status' && meta.message) streamStatus.value = meta.message
            if (meta.event === 'result' && meta.session) {
              finalSession = meta.session
              streamStatus.value = '正在完成对比'
            }
          },
        },
        controller.signal,
      )
      if (epoch !== requestEpoch) return
      const session = finalSession as CompareSessionResponse | null
      if (!session) throw new Error('流式对比缺少最终结果')
      sessionId.value = session.id
      messages.value = session.messages
      priority.value = (session.priority as ComparePriority) || 'balanced'
      if (session.result_cache) {
        scores.value = session.result_cache.scores
        propertyData.value = session.result_cache.property_data
        reply.value = session.result_cache.reply
      }
    } catch (e: any) {
      if (epoch === requestEpoch && e?.name !== 'AbortError') {
        error.value = e?.message || '对比分析失败'
      }
    } finally {
      if (epoch === requestEpoch) {
        loading.value = false
        streamStatus.value = ''
      }
      if (streamController === controller) streamController = null
    }
  }

  async function sendFollowup(message: string, newPriority?: ComparePriority | null) {
    if (!sessionId.value) return
    const activeSessionId = sessionId.value
    const epoch = ++requestEpoch
    loading.value = true
    error.value = null
    try {
      const resp = await compareService.sendMessage(activeSessionId, {
        message,
        priority: newPriority || null,
      })
      if (epoch !== requestEpoch || sessionId.value !== activeSessionId) return
      scores.value = resp.scores
      propertyData.value = resp.property_data
      reply.value = resp.reply
      if (newPriority) priority.value = newPriority
    } catch (e: any) {
      if (epoch === requestEpoch) error.value = e?.message || '追问失败'
    } finally {
      if (epoch === requestEpoch) loading.value = false
    }
  }

  function reset() {
    requestEpoch += 1
    streamController?.abort()
    streamController = null
    sessionId.value = null
    messages.value = []
    scores.value = {}
    propertyData.value = {}
    priority.value = 'balanced'
    reply.value = ''
    streamStatus.value = ''
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
    streamStatus,
    loading,
    error,
    propertyIds,
    dimensionKeys,
    startComparison,
    sendFollowup,
    reset,
  }
})
