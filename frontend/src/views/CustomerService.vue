<template>
  <div class="cs-page">
    <!-- 左侧：会话列表 -->
    <div class="cs-sidebar">
      <div class="sidebar-header">
        <h3>💬 客服中心</h3>
        <el-button size="small" text type="primary" @click="handleNewSession">
          <el-icon><Plus /></el-icon>
          新咨询
        </el-button>
      </div>
      <div class="session-list">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === activeSessionId }"
          @click="switchSession(s.id)"
        >
          <span class="session-title">{{ s.title || '客服咨询' }}</span>
          <span class="session-time">{{ formatTime(s.created_at) }}</span>
        </div>
        <el-empty v-if="sessions.length === 0" description="暂无咨询记录" :image-size="48" />
      </div>
    </div>

    <!-- 右侧：对话区 -->
    <div class="cs-main">
      <!-- 头部 -->
      <div class="chat-header">
        <div class="header-info">
          <el-avatar :size="36" icon="Headset" />
          <div>
            <span class="agent-name">AI 租房助手</span>
            <span class="agent-status">在线 · 秒回</span>
          </div>
        </div>
        <span class="header-hint">AI 智能客服，随时为您解答租房问题</span>
      </div>

      <!-- 消息列表 -->
      <div class="chat-body" ref="chatBodyRef">
        <div v-if="loadingHistory" class="chat-loading">
          <el-icon class="is-loading"><Loading /></el-icon>
          加载历史消息...
        </div>
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          class="message-row"
          :class="msg.role === 'user' ? 'msg-user' : 'msg-assistant'"
        >
          <el-avatar v-if="msg.role === 'assistant'" :size="32" icon="Headset" class="msg-avatar" />
          <div class="msg-bubble" :class="msg.role">
            <div class="msg-content">{{ msg.content }}</div>
            <div class="msg-time">{{ msg.created_at ? formatTime(msg.created_at) : '' }}</div>
          </div>
          <el-avatar v-if="msg.role === 'user'" :size="32" :icon="UserFilled" class="msg-avatar" />
        </div>
        <!-- 流式回复 -->
        <div v-if="streaming" class="message-row msg-assistant">
          <el-avatar :size="32" icon="Headset" class="msg-avatar" />
          <div class="msg-bubble assistant">
            <div class="msg-content">{{ streamingText }}<span class="cursor-blink">|</span></div>
          </div>
        </div>
        <div ref="chatBottomRef" />
      </div>

      <!-- 输入区 -->
      <div class="chat-footer">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          placeholder="输入您的问题，例如：如何预约看房？押金怎么退？..."
          :disabled="sending || streaming"
          resize="none"
          @keyup.enter.exact="handleSend"
        />
        <el-button
          type="primary"
          :loading="sending"
          :disabled="!inputText.trim() || streaming"
          @click="handleSend"
          class="send-btn"
        >
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Headset, Loading, UserFilled } from '@element-plus/icons-vue'
import { chatService } from '@/services/chat'
import api from '@/services/api'
import type { ChatSession, ChatMessage } from '@/types/chat'

// ── 状态 ──
const sessions = ref<ChatSession[]>([])
const activeSessionId = ref<number | null>(null)
const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const sending = ref(false)
const streaming = ref(false)
const streamingText = ref('')
const loadingHistory = ref(false)

const chatBodyRef = ref<HTMLElement | null>(null)
const chatBottomRef = ref<HTMLElement | null>(null)

// ── 工具 ──
function formatTime(t: string) {
  if (!t) return ''
  const d = new Date(t)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  if (isToday) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function scrollToBottom() {
  nextTick(() => {
    chatBottomRef.value?.scrollIntoView({ behavior: 'smooth' })
  })
}

// ── 会话管理 ──
async function loadSessions() {
  try {
    sessions.value = await chatService.listSessions()
  } catch {
    sessions.value = []
  }
}

async function ensureSession() {
  if (activeSessionId.value) return
  // 尝试找已有会话
  if (sessions.value.length > 0) {
    activeSessionId.value = sessions.value[0].id
    return
  }
  // 创建新会话
  try {
    const s = await chatService.createSession('客服咨询')
    sessions.value.unshift(s)
    activeSessionId.value = s.id
  } catch (e: any) {
    ElMessage.error('创建会话失败')
  }
}

async function handleNewSession() {
  try {
    const s = await chatService.createSession('客服咨询')
    sessions.value.unshift(s)
    activeSessionId.value = s.id
    messages.value = []
  } catch {
    ElMessage.error('创建会话失败')
  }
}

async function switchSession(id: number) {
  if (id === activeSessionId.value) return
  activeSessionId.value = id
}

// ── 消息 ──
async function loadHistory() {
  if (!activeSessionId.value) return
  loadingHistory.value = true
  try {
    messages.value = await chatService.getMessages(activeSessionId.value)
    scrollToBottom()
  } catch {
    messages.value = []
  } finally {
    loadingHistory.value = false
  }
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || sending.value || streaming.value) return
  if (!activeSessionId.value) {
    ElMessage.warning('会话未就绪')
    return
  }
  inputText.value = ''
  sending.value = true

  // 添加用户消息到列表
  const userMsg: ChatMessage = {
    id: Date.now(),
    session_id: activeSessionId.value,
    role: 'user',
    content: text,
    created_at: new Date().toISOString(),
  } as ChatMessage
  messages.value.push(userMsg)
  scrollToBottom()

  // 开始 SSE 流式接收
  streaming.value = true
  streamingText.value = ''

  const token = localStorage.getItem('access_token')
  try {
    const response = await fetch(`/api/v1/chat/sessions/${activeSessionId.value}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
      },
      body: JSON.stringify({ content: text }),
    })

    if (!response.ok) throw new Error('请求失败')

    const reader = response.body?.getReader()
    if (!reader) throw new Error('无法读取响应流')

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
          const data = line.slice(6).trim()
          if (data === '[DONE]') continue
          try {
            const parsed = JSON.parse(data)
            if (parsed.content) {
              streamingText.value += parsed.content
            }
          } catch {
            // 纯文本 token
            streamingText.value += data
          }
        }
      }
    }
  } catch (e: any) {
    ElMessage.error('消息发送失败：' + (e.message || '网络异常'))
    streamingText.value = ''
  }

  // 流结束 → 将流式内容写入消息列表
  if (streamingText.value) {
    const assistantMsg: ChatMessage = {
      id: Date.now() + 1,
      session_id: activeSessionId.value,
      role: 'assistant',
      content: streamingText.value,
      created_at: new Date().toISOString(),
    } as ChatMessage
    messages.value.push(assistantMsg)
  }
  streaming.value = false
  streamingText.value = ''
  sending.value = false
  scrollToBottom()
}

// ── 生命周期 ──
onMounted(async () => {
  await loadSessions()
  await ensureSession()
  await loadHistory()
  scrollToBottom()
})

watch(activeSessionId, async (newId) => {
  if (newId) await loadHistory()
})
</script>

<style scoped>
.cs-page {
  display: flex;
  height: calc(100vh - 64px - 48px);
  margin: -24px;
  background: var(--bg);
}

/* ====== 左侧会话列表 ====== */
.cs-sidebar {
  width: 260px;
  background: var(--bg-white);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--border-light);
}

.sidebar-header h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-primary);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.15s;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.session-item:hover {
  background: #f5f7fa;
}

.session-item.active {
  background: #ecf5ff;
}

.session-title {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-time {
  font-size: 12px;
  color: var(--text-muted);
}

/* ====== 右侧对话区 ====== */
.cs-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
  background: var(--bg-white);
  padding: 12px 20px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.agent-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.agent-status {
  font-size: 12px;
  color: var(--success);
  display: block;
}

.header-hint {
  font-size: 13px;
  color: var(--text-muted);
}

/* ====== 消息区 ====== */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  background: #fafbfc;
}

.chat-loading {
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  padding: 20px;
}

.message-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 20px;
}

.msg-user {
  flex-direction: row-reverse;
}

.msg-avatar {
  flex-shrink: 0;
}

.msg-bubble {
  max-width: 65%;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.msg-bubble.user {
  background: linear-gradient(135deg, #409eff, #337ecc);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.msg-bubble.assistant {
  background: var(--bg-white);
  color: var(--text-primary);
  border: 1px solid var(--border-light);
  border-bottom-left-radius: 4px;
}

.msg-bubble.user .msg-time {
  color: rgba(255, 255, 255, 0.7);
}

.msg-bubble.assistant .msg-time {
  color: var(--text-muted);
}

.msg-time {
  font-size: 11px;
  margin-top: 4px;
}

.cursor-blink {
  animation: blink 0.8s infinite;
  color: var(--primary);
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* ====== 输入区 ====== */
.chat-footer {
  background: var(--bg-white);
  padding: 16px 20px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 12px;
  align-items: flex-end;
  flex-shrink: 0;
}

.chat-footer :deep(.el-textarea__inner) {
  border-radius: 12px;
}

.send-btn {
  border-radius: 8px;
  flex-shrink: 0;
}

/* ====== 响应式 ====== */
@media (max-width: 768px) {
  .cs-sidebar {
    display: none;
  }
  .msg-bubble {
    max-width: 85%;
  }
}
</style>
