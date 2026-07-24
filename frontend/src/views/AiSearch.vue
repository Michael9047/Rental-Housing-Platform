<template>
  <div class="ai-search-page">
    <!-- ═══ 对话区 ═══ -->
    <div class="chat-area">
      <div v-if="messages.length === 0" class="welcome">
        <h1>AI 智能找房</h1>
        <p>用自然语言描述你的需求，AI 帮你找房</p>
        <div class="example-tags">
          <el-tag v-for="ex in examples" :key="ex" class="example-tag" effect="plain" @click="send(ex)">{{ ex }}</el-tag>
        </div>
      </div>

      <div v-for="(msg, i) in messages" :key="i" class="msg-wrapper">
        <!-- 用户消息 -->
        <div class="msg-user">{{ msg.user }}</div>
        <!-- AI 回复 -->
        <div v-if="msg.reply" class="msg-ai">
          <div class="ai-label">🤖 AI 分析</div>
          <pre class="ai-text">{{ msg.reply }}</pre>
        </div>
        <!-- 推荐房源卡片 -->
        <div v-if="msg.recommendations?.length" class="recs-row">
          <PropertyCard
            v-for="r in msg.recommendations.slice(0, 6)"
            :key="r.property_id"
            :property="r.property"
            :show-similarity="true"
            class="rec-card"
          />
        </div>
      </div>

      <div v-if="loading" class="loading-msg">🤔 正在分析...</div>
    </div>

    <!-- ═══ 输入区 ═══ -->
    <div class="input-bar">
      <el-input
        v-model="input"
        size="large"
        placeholder="例如：NUS附近20000以内studio"
        class="query-input"
        clearable
        :disabled="loading"
        @keyup.enter="send()"
      >
        <template #suffix>
          <el-button type="primary" size="large" :loading="loading" :disabled="!input.trim()" @click="send()">
            <el-icon><Promotion /></el-icon>
          </el-button>
        </template>
      </el-input>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Promotion } from '@element-plus/icons-vue'
import { agentService } from '@/services/agent'
import PropertyCard from '@/components/PropertyCard.vue'
import type { AgentMessageResponse } from '@/types/agent'

const route = useRoute()

interface ChatMessage {
  user: string
  reply?: string
  recommendations?: AgentMessageResponse['recommendations']
}

const input = ref('')
const loading = ref(false)
const sessionId = ref<number | null>(null)
const messages = ref<ChatMessage[]>([])

const examples = [
  'NUS附近20000以内studio',
  'UCL周边1500镑以内带独卫',
  '金文泰2w以内',
]

onMounted(async () => {
  try {
    const s = await agentService.createSession()
    sessionId.value = s.session_id
  } catch { /* 会话创建失败仍可使用 */ }
  // 从首页搜索框跳转过来 → 自动发送
  const urlQuery = route.query.q as string
  if (urlQuery?.trim()) {
    send(urlQuery.trim())
  }
})

async function send(text?: string) {
  const msg = (text || input.value).trim()
  if (!msg || loading.value) return
  if (!sessionId.value) {
    try { const s = await agentService.createSession(); sessionId.value = s.session_id } catch { return }
  }

  input.value = ''
  loading.value = true
  messages.value.push({ user: msg, reply: '' })
  const last = messages.value[messages.value.length - 1]

  try {
    // 用 fetch 直接调流式端点
    const token = localStorage.getItem('access_token') || ''
    const resp = await fetch(
      `/api/v1/agent/sessions/${sessionId.value}/messages/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ message: msg }),
      }
    )
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.detail || `HTTP ${resp.status}`)
    }

    const reader = resp.body?.getReader()
    if (!reader) throw new Error('No response stream')
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') continue
          try {
            const parsed = JSON.parse(data)
            if (parsed.token) {
              last.reply = (last.reply || '') + parsed.token
            }
            if (parsed.meta?.recommendations) {
              last.recommendations = parsed.meta.recommendations
            }
          } catch {}
        }
      }
    }
  } catch (e: any) {
    last.reply = e.message || '请求失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.ai-search-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 110px);
  position: relative;
}
.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px 16px 100px;
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}
.welcome {
  text-align: center;
  padding: 80px 0;
}
.welcome h1 { font-size: 28px; margin-bottom: 8px; }
.welcome p { color: #909399; margin-bottom: 24px; }
.example-tags { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
.example-tag { cursor: pointer; }
.msg-wrapper { margin-bottom: 24px; }
.msg-user {
  background: #ecf5ff;
  border-radius: 12px 12px 4px 12px;
  padding: 10px 16px;
  margin-bottom: 12px;
  display: inline-block;
  max-width: 80%;
}
.msg-ai {
  background: #f5f7fa;
  border-radius: 4px 12px 12px 12px;
  padding: 14px 18px;
  margin-bottom: 12px;
}
.ai-label { font-weight: 600; font-size: 13px; color: #409eff; margin-bottom: 8px; }
.ai-text {
  white-space: pre-wrap;
  font: 14px/1.7 system-ui, sans-serif;
  color: #303133;
  margin: 0;
}
.recs-row {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 8px;
}
.rec-card { min-width: 260px; max-width: 260px; flex-shrink: 0; }
.loading-msg { text-align: center; color: #909399; padding: 16px; }
.input-bar {
  position: sticky;
  bottom: 0;
  padding: 12px 16px 20px;
  background: #fff;
  border-top: 1px solid #ebeef5;
  margin-top: auto;
}
.query-input :deep(.el-input__wrapper) { border-radius: 12px; }
</style>
