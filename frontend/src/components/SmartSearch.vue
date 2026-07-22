<template>
  <div ref="wrapperRef" class="smart-search-wrapper">
    <div class="smart-search-bar">
      <el-input
        ref="inputRef"
        v-model="query"
        size="large"
        :placeholder="placeholder"
        :prefix-icon="Search"
        class="smart-search-input"
        @focus="showSuggestions = true"
        @input="onInput"
        @keydown.enter="handleEnter"
        @keydown.escape="showSuggestions = false"
      />
      <button
        v-if="showVoice"
        class="voice-btn"
        :class="{ listening: listening }"
        @click="toggleVoice"
        title="语音输入"
      >
        <el-icon :size="20"><Microphone /></el-icon>
      </button>
      <el-button type="primary" @click="handleSearch" class="search-btn">
        搜索
      </el-button>
    </div>

    <!-- 搜索建议下拉面板 -->
    <transition name="slide-down">
      <div v-if="showSuggestions" class="suggestions-panel">
        <!-- 无输入时：显示热门内容 -->
        <template v-if="!query.trim()">
          <div v-if="popularCities.length > 0" class="suggestion-section">
            <div class="section-title">热门城市</div>
            <div class="suggestion-grid">
              <div
                v-for="city in popularCities.slice(0, 8)"
                :key="city.query.district + city.query.country"
                class="suggestion-item city-item"
                @click="selectCity(city)"
              >
                <el-icon><Location /></el-icon>
                <span class="item-name">{{ city.name }}</span>
                <span class="item-count">{{ city.count }}套</span>
              </div>
            </div>
          </div>

          <div v-if="popularSchools.length > 0" class="suggestion-section">
            <div class="section-title">热门学校</div>
            <div class="suggestion-grid">
              <div
                v-for="school in popularSchools.slice(0, 8)"
                :key="school.id"
                class="suggestion-item school-item"
                @click="selectSchool(school)"
              >
                <el-icon><School /></el-icon>
                <span class="item-name">{{ formatSchoolName(school) }}</span>
                <span class="item-count">{{ school.count }}套</span>
              </div>
            </div>
          </div>
        </template>

        <!-- 有输入时：显示匹配结果 -->
        <template v-else>
          <div v-if="loading" class="suggestion-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>搜索中...</span>
          </div>

          <template v-else>
            <div v-if="matchingCities.length > 0" class="suggestion-section">
              <div class="section-title">匹配城市/区域</div>
              <div class="suggestion-list">
                <div
                  v-for="city in matchingCities"
                  :key="city.query.district + city.query.country"
                  class="suggestion-item city-item"
                  @click="selectCity(city)"
                >
                  <el-icon><Location /></el-icon>
                  <span class="item-name">{{ city.name }}</span>
                  <span class="item-count">{{ city.count }}套</span>
                </div>
              </div>
            </div>

            <div v-if="matchingSchools.length > 0" class="suggestion-section">
              <div class="section-title">匹配学校</div>
              <div class="suggestion-list">
                <div
                  v-for="school in matchingSchools"
                  :key="school.id"
                  class="suggestion-item school-item"
                  @click="selectSchool(school)"
                >
                  <el-icon><School /></el-icon>
                  <span class="item-name">{{ formatSchoolName(school) }}</span>
                  <span class="item-count">{{ school.count }}套</span>
                </div>
              </div>
            </div>

            <div v-if="matchingProperties.length > 0" class="suggestion-section">
              <div class="section-title">匹配房源</div>
              <div class="suggestion-list">
                <div
                  v-for="prop in matchingProperties"
                  :key="prop.id"
                  class="suggestion-item property-item"
                  @click="selectProperty(prop)"
                >
                  <el-icon><House /></el-icon>
                  <span class="item-name">{{ prop.title }}</span>
                  <span class="item-price" v-if="prop.price_monthly">¥{{ prop.price_monthly }}/月</span>
                </div>
              </div>
            </div>

            <div
              v-if="!loading && matchingCities.length === 0 && matchingSchools.length === 0 && matchingProperties.length === 0"
              class="suggestion-empty"
            >
              <el-empty description="未找到匹配结果" :image-size="60" />
            </div>
          </template>
        </template>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search, Location, House, Microphone, Loading } from '@element-plus/icons-vue'
import { School } from '@element-plus/icons-vue'
import api from '@/services/api'

interface SuggestionCity {
  type: 'city'
  name: string
  country: string
  count: number
  query: { district: string; country: string }
}

interface SuggestionSchool {
  type: 'school'
  id: number
  name: string
  name_cn?: string | null
  abbreviation?: string | null
  address: string | null
  count: number
  query: { school_id: number }
}

interface SuggestionProperty {
  type: 'property'
  id: number
  title: string
  district: string
  price_monthly: number | null
  query: { property_id: number }
}

const props = withDefaults(
  defineProps<{
    placeholder?: string
    showVoice?: boolean
  }>(),
  {
    placeholder: '搜索城市、学校或房源...',
    showVoice: false,
  }
)

const emit = defineEmits<{
  (e: 'search', query: string): void
}>()

const router = useRouter()
const inputRef = ref()
const wrapperRef = ref<HTMLElement | null>(null)
const query = ref('')
const showSuggestions = ref(false)
const loading = ref(false)
const listening = ref(false)

const popularCities = ref<SuggestionCity[]>([])
const popularSchools = ref<SuggestionSchool[]>([])
const matchingCities = ref<SuggestionCity[]>([])
const matchingSchools = ref<SuggestionSchool[]>([])
const matchingProperties = ref<SuggestionProperty[]>([])

let debounceTimer: ReturnType<typeof setTimeout> | null = null

/** 格式化学校显示名称：优先中文名，有缩写时附加括号 */
function formatSchoolName(school: SuggestionSchool | { name: string; name_cn?: string | null; abbreviation?: string | null }): string {
  if (school.name_cn) {
    return school.abbreviation ? `${school.name_cn} (${school.abbreviation})` : school.name_cn
  }
  return school.abbreviation ? `${school.name} (${school.abbreviation})` : school.name
}

// 获取搜索建议
async function fetchSuggestions(searchQuery?: string) {
  loading.value = true
  try {
    const params = searchQuery ? { q: searchQuery, limit: 10 } : { limit: 10 }
    const resp = await api.get('/search/suggestions', { params })
    const data = resp.data

    if (searchQuery) {
      matchingCities.value = data.matching_cities || []
      matchingSchools.value = data.matching_schools || []
      matchingProperties.value = data.matching_properties || []
    } else {
      popularCities.value = data.popular_cities || []
      popularSchools.value = data.popular_schools || []
    }
  } catch (err) {
    console.error('获取搜索建议失败:', err)
  } finally {
    loading.value = false
  }
}

// 输入处理（防抖）
function onInput() {
  if (debounceTimer) clearTimeout(debounceTimer)

  debounceTimer = setTimeout(() => {
    const q = query.value.trim()
    if (q) {
      fetchSuggestions(q)
    } else {
      fetchSuggestions()
    }
  }, 300)
}

// 选择城市
function selectCity(city: SuggestionCity) {
  showSuggestions.value = false
  query.value = ''
  router.push({
    path: '/search',
    query: {
      district: city.query.district,
      country: city.query.country,
    },
  })
}

// 选择学校
function selectSchool(school: SuggestionSchool) {
  showSuggestions.value = false
  query.value = ''
  router.push({
    path: '/search',
    query: {
      school_id: String(school.id),
    },
  })
}

// 选择房源
function selectProperty(prop: SuggestionProperty) {
  showSuggestions.value = false
  query.value = ''
  router.push(`/property/${prop.id}`)
}

// 回车搜索：有唯一匹配建议时自动选中，否则按原始文本搜索
function handleEnter() {
  const q = query.value.trim()
  if (!q) return
  showSuggestions.value = false

  // 有输入时，优先使用已加载的建议列表中的精确匹配
  const totalMatches = matchingSchools.value.length + matchingCities.value.length + matchingProperties.value.length

  if (totalMatches === 1) {
    // 唯一匹配：自动选中
    if (matchingSchools.value.length === 1) {
      selectSchool(matchingSchools.value[0])
      return
    }
    if (matchingCities.value.length === 1) {
      selectCity(matchingCities.value[0])
      return
    }
    if (matchingProperties.value.length === 1) {
      selectProperty(matchingProperties.value[0])
      return
    }
  }

  // 没有建议或多种建议 → 按原始文本搜索
  emit('search', q)
}

// 点击搜索按钮
function handleSearch() {
  handleEnter()
}

// 语音输入
let recognition: any = null
function toggleVoice() {
  const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  if (!SpeechRecognition) {
    ElMessage.warning('您的浏览器不支持语音输入')
    return
  }
  if (listening.value) {
    recognition?.stop()
    listening.value = false
    return
  }
  recognition = new SpeechRecognition()
  recognition.lang = 'zh-CN'
  recognition.interimResults = false
  recognition.maxAlternatives = 1
  listening.value = true
  recognition.start()
  recognition.onresult = (event: any) => {
    const transcript = event.results[0][0].transcript
    query.value = transcript
    listening.value = false
    recognition = null
    onInput()
  }
  recognition.onerror = () => {
    listening.value = false
    recognition = null
    ElMessage.info('语音识别未成功，请手动输入')
  }
  recognition.onend = () => {
    listening.value = false
    recognition = null
  }
}

// 点击外部关闭（使用 ref 而非 querySelector，避免多实例冲突）
function handleClickOutside(event: MouseEvent) {
  if (wrapperRef.value && !wrapperRef.value.contains(event.target as Node)) {
    showSuggestions.value = false
  }
}

onMounted(() => {
  fetchSuggestions()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  if (debounceTimer) clearTimeout(debounceTimer)
})
</script>

<style scoped>
.smart-search-wrapper {
  position: relative;
  width: 100%;
}

.smart-search-bar {
  display: flex;
  align-items: stretch;
  border-radius: 28px;
  border: 2px solid var(--primary);
  background: var(--bg-white);
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(255, 107, 53, 0.14);
  transition: box-shadow 0.25s;
}

.smart-search-bar:focus-within {
  box-shadow: 0 4px 24px rgba(255, 107, 53, 0.22);
}

.smart-search-input {
  flex: 1;
}

.smart-search-input :deep(.el-input__wrapper) {
  border-radius: 0 !important;
  height: 52px;
  font-size: 15px;
  box-shadow: none !important;
  border: none !important;
  background: transparent !important;
}

.voice-btn {
  flex-shrink: 0;
  width: 48px;
  background: transparent;
  border: none;
  color: #b0b3bb;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  padding: 0;
  outline: none;
}

.voice-btn:hover {
  color: var(--primary);
}

.voice-btn.listening {
  color: var(--primary);
  background: var(--primary-light);
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.search-btn {
  flex-shrink: 0;
  height: auto;
  font-size: 16px;
  font-weight: 600;
  padding: 0 28px !important;
  border-radius: 0 !important;
  background: var(--primary) !important;
  border-color: var(--primary) !important;
  color: #fff !important;
}

.search-btn:hover {
  background: var(--primary-dark) !important;
  border-color: var(--primary-dark) !important;
}

/* 建议面板 */
.suggestions-panel {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  background: var(--bg-white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-lg);
  max-height: 500px;
  overflow-y: auto;
  z-index: 1000;
  padding: 16px;
}

.suggestion-section {
  margin-bottom: 20px;
}

.suggestion-section:last-child {
  margin-bottom: 0;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 10px;
  padding-left: 4px;
}

.suggestion-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
}

.suggestion-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--bg-white);
}

.suggestion-item:hover {
  background: var(--primary-light);
  transform: translateX(4px);
}

.suggestion-item .el-icon {
  color: var(--primary);
  flex-shrink: 0;
}

.item-name {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-count {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.item-price {
  font-size: 13px;
  color: var(--danger);
  font-weight: 600;
  flex-shrink: 0;
}

.suggestion-loading,
.suggestion-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px;
  color: var(--text-muted);
  gap: 8px;
}

.suggestion-loading .el-icon {
  font-size: 24px;
  color: var(--primary);
}

/* 过渡动画 */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
