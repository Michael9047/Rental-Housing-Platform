<template>
  <div class="chat-page">
    <!-- Left: Session List -->
    <div class="chat-sidebar">
      <div class="sidebar-header">
        <h3>AI 助手</h3>
        <el-button type="primary" :icon="Plus" size="small" circle @click="newSession" />
      </div>
      <div class="session-list">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: activeSessionId === s.id }"
          @click="switchSession(s)"
        >
          <div class="session-info">
            <span class="session-title">{{ s.title || '新对话' }}</span>
            <span class="session-time">{{ formatTime(s.updated_at) }}</span>
          </div>
          <el-button
            :icon="Delete"
            size="small"
            text
            type="danger"
            @click.stop="deleteSessionHandler(s.id)"
          />
        </div>
        <el-empty v-if="sessions.length === 0" description="暂无对话" :image-size="60" />
      </div>
    </div>

    <!-- Right: Chat Area -->
    <div class="chat-main">
      <!-- Header -->
      <div class="chat-header">
        <span class="chat-title">{{ activeSession?.title || '新对话' }}</span>
        <span v-if="activeSession" class="chat-status">
          <el-tag :type="activeSession.status === 'active' ? 'success' : 'info'" size="small">
            {{ activeSession.status === 'active' ? '进行中' : '已关闭' }}
          </el-tag>
        </span>
      </div>

      <!-- Messages -->
      <div class="chat-messages" ref="messagesContainer">
        <div v-if="messages.length === 0 && !streaming" class="chat-welcome">
          <el-icon :size="48"><ChatDotRound /></el-icon>
          <h3>欢迎使用 AI 租房助手</h3>
          <p>你可以问我关于房源的问题，比如：</p>
          <div class="suggestions">
            <el-tag
              v-for="q in suggestedQuestions"
              :key="q"
              class="suggestion-tag"
              @click="sendMessage(q)"
            >
              {{ q }}
            </el-tag>
          </div>
        </div>

        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message-row"
          :class="msg.role"
        >
          <div class="message-avatar">
            <el-avatar v-if="msg.role === 'assistant'" :icon="Cpu" :size="32" />
            <el-avatar v-else-if="msg.role === 'user'" :icon="UserFilled" :size="32" />
          </div>
          <div class="message-body">
            <div class="message-content" v-html="renderContent(msg.content)" />
            <!-- Property cards in assistant messages -->
            <div
              v-if="msg.role === 'assistant' && msg.metadata?.matched_properties?.length"
              class="matched-properties"
            >
              <div class="properties-label">📋 匹配房源</div>
              <div class="property-cards">
                <div
                  v-for="prop in msg.metadata.matched_properties"
                  :key="prop.id"
                  class="property-mini-card"
                  @click="goToProperty(prop.id)"
                >
                  <div class="prop-title">{{ prop.title }}</div>
                  <div class="prop-meta">
                    <span>📍 {{ prop.district }}</span>
                    <span class="prop-price">¥{{ prop.price_monthly }}/月</span>
                  </div>
                  <div class="prop-meta">
                    <span>{{ prop.bedrooms }}室{{ prop.bathrooms }}卫</span>
                    <span v-if="prop.area_sqm">{{ prop.area_sqm }}㎡</span>
                    <span v-if="prop.similarity !== null" class="prop-sim">
                      相似度 {{ (prop.similarity * 100).toFixed(0) }}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Streaming content -->
        <div v-if="streaming" class="message-row assistant">
          <div class="message-avatar">
            <el-avatar :icon="Cpu" :size="32" />
          </div>
          <div class="message-body">
            <div class="message-content" v-html="renderContent(streamContent)" />
            <span class="typing-cursor">|</span>
          </div>
        </div>

        <div ref="scrollAnchor" />
      </div>

      <!-- Input -->
      <div class="chat-input">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          placeholder="输入你的问题，比如：帮我找一个月租3000以内的两室一厅..."
          :disabled="streaming"
          @keydown.enter.exact.prevent="sendMessage(inputText)"
        />
        <el-button
          type="primary"
          :icon="Promotion"
          :loading="streaming"
          :disabled="!inputText.trim() || streaming"
          @click="sendMessage(inputText)"
        >
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Cpu, UserFilled, ChatDotRound, Promotion } from '@element-plus/icons-vue'
import { chatService } from '@/services/chat'
import type { ChatSession, ChatMessage, SSEEvent, MatchedProperty } from '@/types/chat'

const router = useRouter()

// State
const sessions = ref<ChatSession[]>([])
const activeSessionId = ref<number | null>(null)
const activeSession = ref<ChatSession | null>(null)
const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const streaming = ref(false)
const streamContent = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const scrollAnchor = ref<HTMLElement | null>(null)

const suggestedQuestions = [
  '帮我找一个月租3000以内的两室一厅',
  '姑苏区有什么好房源推荐？',
  '附近有地铁的房子有哪些？',
  '适合学生合租的房源',
]

// ── Session management ────────────────────────────────────────────

async function loadSessions() {
  try {
    sessions.value = await chatService.listSessions()
  } catch {
    // ignore
  }
}

async function newSession() {
  try {
    const s = await chatService.createSession()
    sessions.value.unshift(s)
    switchSession(s)
  } catch {
    ElMessage.error('创建对话失败')
  }
}

async function switchSession(s: ChatSession) {
  activeSessionId.value = s.id
  activeSession.value = s
  messages.value = []
  streamContent.value = ''
  streaming.value = false

  try {
    messages.value = await chatService.getMessages(s.id)
    await scrollToBottom()
  } catch {
    ElMessage.error('加载消息失败')
  }
}

async function deleteSessionHandler(id: number) {
  try {
    await ElMessageBox.confirm('确定要删除这个对话吗？', '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await chatService.deleteSession(id)
    sessions.value = sessions.value.filter((s) => s.id !== id)
    if (activeSessionId.value === id) {
      activeSessionId.value = null
      activeSession.value = null
      messages.value = []
    }
  } catch {
    // cancelled
  }
}

// ── Messaging ─────────────────────────────────────────────────────

async function sendMessage(text: string) {
  const content = text.trim()
  if (!content || streaming.value) return

  inputText.value = ''

  // Create session if none active
  if (!activeSessionId.value) {
    try {
      const s = await chatService.createSession(content.slice(0, 100))
      sessions.value.unshift(s)
      activeSessionId.value = s.id
      activeSession.value = s
    } catch {
      ElMessage.error('创建对话失败')
      return
    }
  }

  // Add user message to UI
  const tempUserMsg: ChatMessage = {
    id: Date.now(),
    session_id: activeSessionId.value!,
    role: 'user',
    content,
    created_at: new Date().toISOString(),
  }
  messages.value.push(tempUserMsg)
  await scrollToBottom()

  // Start streaming
  streaming.value = true
  streamContent.value = ''

  const token = localStorage.getItem('access_token')
  const url = `/api/v1/chat/sessions/${activeSessionId.value}/messages`

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ content }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('No reader')

    const decoder = new TextDecoder()
    let buffer = ''
    let matchedProps: MatchedProperty[] = []

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') continue

        try {
          const event: SSEEvent = JSON.parse(data)
          if (event.type === 'matched') {
            matchedProps = event.properties || []
          } else if (event.type === 'content') {
            streamContent.value += event.content || ''
            await scrollToBottom()
          } else if (event.type === 'error') {
            ElMessage.error(event.error || '回复出错')
          }
        } catch {
          // skip parse errors
        }
      }
    }

    // Save assistant message
    const assistantMsg: ChatMessage = {
      id: Date.now() + 1,
      session_id: activeSessionId.value!,
      role: 'assistant',
      content: streamContent.value,
      metadata: matchedProps.length ? { matched_properties: matchedProps } : undefined,
      created_at: new Date().toISOString(),
    }
    messages.value.push(assistantMsg)

    // Update session title from first message
    if (activeSession.value && !activeSession.value.title) {
      activeSession.value.title = content.slice(0, 100)
      const idx = sessions.value.findIndex((s) => s.id === activeSessionId.value)
      if (idx >= 0) sessions.value[idx].title = content.slice(0, 100)
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '发送失败'
    ElMessage.error(msg)
  } finally {
    streaming.value = false
    streamContent.value = ''
    await scrollToBottom()
  }
}

// ── Helpers ───────────────────────────────────────────────────────

function renderContent(text: string): string {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return d.toLocaleDateString('zh-CN')
}

async function scrollToBottom() {
  await nextTick()
  scrollAnchor.value?.scrollIntoView({ behavior: 'smooth' })
}

function goToProperty(id: number) {
  router.push(`/property/${id}`)
}

onMounted(loadSessions)
</script>

<style scoped>
.chat-page {
  display: flex;
  height: calc(100vh - 108px);
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

/* ── Sidebar ────────────────────────────────────────────────── */

.chat-sidebar {
  width: 260px;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  background: #fafafa;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 4px;
}

.session-item:hover {
  background: #e8f0fe;
}

.session-item.active {
  background: #d4e4fc;
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  display: block;
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-time {
  font-size: 11px;
  color: #909399;
}

/* ── Main Chat Area ─────────────────────────────────────────── */

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
}

.chat-title {
  font-size: 15px;
  font-weight: 600;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Messages ───────────────────────────────────────────────── */

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f5f7fa;
}

.chat-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
  text-align: center;
}

.chat-welcome h3 {
  margin: 12px 0 4px;
  color: #606266;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
  justify-content: center;
}

.suggestion-tag {
  cursor: pointer;
}

.suggestion-tag:hover {
  background: #409eff;
  color: #fff;
  border-color: #409eff;
}

.message-row {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.message-row.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.message-body {
  max-width: 75%;
}

.message-row.user .message-content {
  background: #409eff;
  color: #fff;
  border-radius: 12px 12px 4px 12px;
}

.message-row.assistant .message-content {
  background: #fff;
  color: #303133;
  border-radius: 12px 12px 12px 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.message-content {
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.message-content :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 13px;
}

.message-row.user .message-content :deep(code) {
  background: rgba(255, 255, 255, 0.2);
}

.typing-cursor {
  animation: blink 1s infinite;
  color: #409eff;
  font-weight: bold;
  margin-left: 2px;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* ── Property Cards ─────────────────────────────────────────── */

.matched-properties {
  margin-top: 8px;
}

.properties-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
  padding-left: 14px;
}

.property-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 14px 8px;
}

.property-mini-card {
  background: #f0f5ff;
  border: 1px solid #d4e4fc;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.15s;
  min-width: 180px;
  flex: 1;
  max-width: 240px;
}

.property-mini-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
}

.prop-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.prop-meta {
  font-size: 12px;
  color: #606266;
  display: flex;
  gap: 12px;
}

.prop-price {
  color: #f56c6c;
  font-weight: 600;
}

.prop-sim {
  color: #409eff;
  font-size: 11px;
}

/* ── Input ──────────────────────────────────────────────────── */

.chat-input {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #e4e7ed;
  background: #fff;
  align-items: flex-end;
}

.chat-input :deep(.el-textarea__inner) {
  resize: none;
}
</style>
