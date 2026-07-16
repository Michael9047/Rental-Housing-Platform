<template>
  <div class="ai-search-page">
    <!-- ====== 阶段一：输入 ====== -->
    <div v-if="phase === 'input'" class="phase-input">
      <div class="hero-section">
        <h1 class="hero-title">AI 智能找房</h1>
        <p class="hero-sub">用自然语言描述你的需求，AI 帮你精准匹配</p>
        <div class="input-wrapper">
          <el-input
            v-model="rawQuery"
            size="large"
            placeholder="试试说：苏州工业园区附近两居室，预算3000-5000，近地铁"
            class="query-input"
            clearable
            @keyup.enter="handleParse"
          >
            <template #suffix>
              <el-button
                type="primary"
                size="large"
                :loading="parsing"
                :disabled="!rawQuery.trim()"
                @click="handleParse"
                class="send-btn"
              >
                <el-icon><Search /></el-icon>
                开始
              </el-button>
            </template>
          </el-input>
        </div>
        <div class="example-tags">
          <span class="example-label">试试：</span>
          <el-tag
            v-for="ex in examples"
            :key="ex"
            class="example-tag"
            effect="plain"
            @click="rawQuery = ex; handleParse()"
          >{{ ex }}</el-tag>
        </div>
      </div>
    </div>

    <!-- ====== 阶段二：补全表单 ====== -->
    <div v-if="phase === 'form'" class="phase-form">
      <div class="form-card">
        <div class="summary-bar">
          <el-icon :size="20" color="#409eff"><InfoFilled /></el-icon>
          <span>{{ completeness.summary }}</span>
        </div>

        <div v-if="missingFields.length > 0" class="missing-form">
          <h3 class="form-title">请补充以下信息，让搜索结果更精准</h3>
          <el-form :model="formData" label-width="100px" label-position="top" class="fill-form">
            <el-row :gutter="20">
              <el-col
                v-for="mf in missingFields"
                :key="mf.field"
                :span="mf.field === 'district' ? 12 : 8"
              >
                <el-form-item :label="mf.label">
                  <el-select
                    v-if="mf.field === 'district'"
                    v-model="formData.district"
                    placeholder="选择城市"
                    clearable
                    filterable
                    allow-create
                    default-first-option
                  >
                    <el-option label="苏州" value="苏州" />
                    <el-option label="北京" value="北京" />
                    <el-option label="上海" value="上海" />
                    <el-option label="广州" value="广州" />
                    <el-option label="深圳" value="深圳" />
                    <el-option label="杭州" value="杭州" />
                    <el-option label="南京" value="南京" />
                    <el-option label="成都" value="成都" />
                    <el-option label="武汉" value="武汉" />
                  </el-select>
                  <div v-else-if="mf.field === 'price_max'" class="price-range">
                    <el-input-number
                      v-model="formData.price_min"
                      :min="0"
                      :max="50000"
                      :step="500"
                      placeholder="最低"
                      controls-position="right"
                      style="width: 48%"
                    />
                    <span class="price-sep">-</span>
                    <el-input-number
                      v-model="formData.price_max"
                      :min="0"
                      :max="50000"
                      :step="500"
                      placeholder="最高"
                      controls-position="right"
                      style="width: 48%"
                    />
                  </div>
                  <el-select
                    v-else-if="mf.field === 'bedrooms'"
                    v-model="formData.bedrooms"
                    placeholder="选择户型"
                    clearable
                  >
                    <el-option label="1室" :value="1" />
                    <el-option label="2室" :value="2" />
                    <el-option label="3室" :value="3" />
                    <el-option label="4室+" :value="4" />
                  </el-select>
                  <el-select
                    v-else-if="mf.field === 'property_type'"
                    v-model="formData.property_type"
                    placeholder="选择类型"
                    clearable
                  >
                    <el-option label="公寓" value="apartment" />
                    <el-option label="别墅" value="house" />
                    <el-option label="单间" value="studio" />
                    <el-option label="合租" value="shared" />
                  </el-select>
                  <el-input v-else v-model="formData[mf.field]" :placeholder="mf.hint" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </div>

        <div v-if="filledFields.length > 0" class="parsed-fields">
          <span class="parsed-label">已识别：</span>
          <el-tag v-for="ff in filledFields" :key="ff.field" size="small" type="info" effect="plain">
            {{ ff.label }}：{{ ff.value }}
          </el-tag>
        </div>

        <div class="form-actions">
          <el-button @click="resetToInput" text>返回修改</el-button>
          <el-button type="primary" size="large" :loading="searching" @click="handleSearch">
            <el-icon><Search /></el-icon>
            开始检索
          </el-button>
        </div>
      </div>
    </div>

    <!-- ====== 阶段三：结果 ====== -->
    <div v-if="phase === 'results'" class="phase-results">
      <div class="ai-summary">
        <div class="summary-header">
          <span class="summary-icon">AI</span>
          <span class="summary-label">AI 房源推荐</span>
        </div>
        <p class="summary-text">{{ aiSummary }}</p>
      </div>

      <div class="results-section" v-if="searchResults.length > 0">
        <div class="results-header">
          <h3>全部匹配房源（{{ totalCount }} 套）</h3>
          <span class="results-hint">left-right slide</span>
        </div>
        <el-scrollbar class="horizontal-scroll" always>
          <div class="scroll-inner">
            <div
              v-for="item in searchResults"
              :key="item.id"
              class="scroll-card-wrapper"
            >
              <PropertyCard
                :property="item"
                :show-similarity="true"
                class="mini-card"
              />
            </div>
          </div>
        </el-scrollbar>
      </div>

      <div v-else class="empty-results">
        <el-empty description="no matched properties">
          <el-button type="primary" @click="goToTraditionalSearch">
            search traditionally
          </el-button>
        </el-empty>
      </div>

      <div class="bottom-actions" v-if="searchResults.length > 0">
        <el-button size="large" @click="resetToInput" text>重新搜索</el-button>
        <el-button type="primary" size="large" @click="goToTraditionalSearch">
          <el-icon><Connection /></el-icon>
          在传统搜索中继续筛选
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { Search, InfoFilled, Connection } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { aiSearchService } from '@/services/aiSearch'
import PropertyCard from '@/components/PropertyCard.vue'
import type {
  ParsedSearchParams,
  CompletenessReport,
  MissingField,
  AiSearchRequest,
} from '@/services/aiSearch'
import type { PropertySearchResult } from '@/types/property'

const router = useRouter()

type Phase = 'input' | 'form' | 'results'
const phase = ref<Phase>('input')
const rawQuery = ref('')
const parsing = ref(false)
const searching = ref(false)

const parsedParams = ref<ParsedSearchParams>({
  district: null,
  price_min: null,
  price_max: null,
  bedrooms: null,
  property_type: null,
  keywords: null,
})
const completeness = ref<CompletenessReport>({
  is_complete: false,
  missing_fields: [],
  summary: '',
})

const aiSummary = ref('')
const searchResults = ref<PropertySearchResult[]>([])
const totalCount = ref(0)

const formData = reactive<Record<string, any>>({
  district: null,
  price_min: null,
  price_max: null,
  bedrooms: null,
  property_type: null,
})

const examples = [
  '苏州工业园区，两居室，3000-5000元',
  '近地铁，安静小区，预算 2000 左右',
  '上海浦东，一室一厅，4000以内',
]

const missingFields = computed<MissingField[]>(() => {
  return completeness.value.missing_fields || []
})

const filledFields = computed(() => {
  const p = parsedParams.value
  const fields: { field: string; label: string; value: string }[] = []
  if (p.district) fields.push({ field: 'district', label: '区域', value: p.district })
  if (p.price_min != null || p.price_max != null) {
    const min = p.price_min ? '￥' + p.price_min : ''
    const max = p.price_max ? '￥' + p.price_max : ''
    fields.push({ field: 'price', label: '预算', value: min + (min && max ? '-' : '') + max })
  }
  if (p.bedrooms != null) fields.push({ field: 'bedrooms', label: '户型', value: p.bedrooms + '室' })
  if (p.property_type) {
    const typeMap: Record<string, string> = { apartment: '公寓', house: '别墅', studio: '单间', shared: '合租' }
    fields.push({ field: 'property_type', label: '类型', value: typeMap[p.property_type] || p.property_type })
  }
  return fields
})

async function handleParse() {
  if (!rawQuery.value.trim() || parsing.value) return
  parsing.value = true
  try {
    const res = await aiSearchService.parse(rawQuery.value.trim())
    parsedParams.value = res.params
    completeness.value = res.completeness
    formData.district = res.params.district || null
    formData.price_min = res.params.price_min
    formData.price_max = res.params.price_max
    formData.bedrooms = res.params.bedrooms
    formData.property_type = res.params.property_type || null
    if (res.completeness.is_complete) {
      await handleSearch()
    } else {
      phase.value = 'form'
    }
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || 'parse failed'
    ElMessage.error(msg)
  } finally {
    parsing.value = false
  }
}

async function handleSearch() {
  if (searching.value) return
  searching.value = true
  try {
    const params: AiSearchRequest = {
      query: rawQuery.value.trim(),
      district: formData.district || parsedParams.value.district || undefined,
      price_min: formData.price_min ?? parsedParams.value.price_min ?? undefined,
      price_max: formData.price_max ?? parsedParams.value.price_max ?? undefined,
      bedrooms: formData.bedrooms ?? parsedParams.value.bedrooms ?? undefined,
      property_type: formData.property_type || parsedParams.value.property_type || undefined,
      keywords: parsedParams.value.keywords || undefined,
      limit: 30,
    }
    const res = await aiSearchService.search(params)
    aiSummary.value = res.summary
    searchResults.value = res.results
    totalCount.value = res.total_count
    phase.value = 'results'
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || 'search failed'
    ElMessage.error(msg)
  } finally {
    searching.value = false
  }
}

function resetToInput() {
  phase.value = 'input'
  rawQuery.value = ''
  searchResults.value = []
  aiSummary.value = ''
}

function goToTraditionalSearch() {
  const p = parsedParams.value
  const query: Record<string, string> = {}
  if (rawQuery.value) query.q = rawQuery.value
  if (p.district || formData.district) query.district = (p.district || formData.district) as string
  if (p.price_min != null || formData.price_min != null) query.price_min = String(p.price_min ?? formData.price_min ?? '')
  if (p.price_max != null || formData.price_max != null) query.price_max = String(p.price_max ?? formData.price_max ?? '')
  router.push({ name: 'search', query })
}
</script>

<style scoped>
.ai-search-page {
  margin: 0 auto;
  padding: 24px 0 48px;
}

/* ====== input phase ====== */
.hero-section {
  text-align: center;
  padding: 80px 24px 60px;
}

.hero-title {
  font-size: 36px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
  background: linear-gradient(135deg, #409eff, #67c23a);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-sub {
  font-size: 16px;
  color: var(--text-secondary);
  margin-bottom: 40px;
}

.input-wrapper {
  max-width: 700px;
  margin: 0 auto;
}

.query-input :deep(.el-input__wrapper) {
  border-radius: 28px !important;
  padding-right: 6px !important;
  box-shadow: 0 4px 20px rgba(64, 158, 255, 0.12) !important;
}

.send-btn {
  border-radius: 22px !important;
  margin-right: 2px;
}

.example-tags {
  margin-top: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.example-label {
  font-size: 13px;
  color: var(--text-muted);
}

.example-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.example-tag:hover {
  border-color: var(--primary);
  color: var(--primary);
}

/* ====== form phase ====== */
.phase-form {
  max-width: 800px;
  margin: 40px auto;
  padding: 0 24px;
}

.form-card {
  background: var(--bg-white);
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.06);
}

.summary-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  background: linear-gradient(135deg, #ecf5ff, #f0f9eb);
  border-radius: 12px;
  font-size: 15px;
  color: var(--text-primary);
  margin-bottom: 28px;
}

.missing-form {
  margin-bottom: 24px;
}

.form-title {
  font-size: 16px;
  color: var(--text-primary);
  margin-bottom: 20px;
  font-weight: 600;
}

.fill-form {
  margin-bottom: 8px;
}

.price-range {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.price-sep {
  color: var(--text-muted);
  flex-shrink: 0;
}

.parsed-fields {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 24px;
}

.parsed-label {
  font-size: 13px;
  color: var(--text-muted);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px solid var(--border-light);
}

/* ====== results phase ====== */
.phase-results {
  padding: 0 24px;
}

.ai-summary {
  background: linear-gradient(135deg, #f0f9eb 0%, #ecf5ff 100%);
  border-radius: 16px;
  padding: 28px 32px;
  margin-bottom: 36px;
  border: 1px solid #e1f3d8;
}

.summary-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}

.summary-icon {
  font-size: 24px;
}

.summary-label {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.summary-text {
  font-size: 15px;
  line-height: 1.8;
  color: var(--text-regular);
  margin: 0;
  white-space: pre-line;
}

.results-section {
  margin-bottom: 36px;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.results-header h3 {
  font-size: 18px;
  color: var(--text-primary);
  margin: 0;
}

.results-hint {
  font-size: 13px;
  color: var(--text-muted);
}

.horizontal-scroll {
  width: 100%;
}

.scroll-inner {
  display: flex;
  gap: 16px;
  padding-bottom: 8px;
}

.scroll-card-wrapper {
  flex-shrink: 0;
  width: 320px;
}

.mini-card {
  height: 100%;
}

.empty-results {
  padding: 60px 0;
}

.bottom-actions {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 32px 0 48px;
}

/* ====== responsive ====== */
@media (max-width: 768px) {
  .hero-title {
    font-size: 26px;
  }
  .hero-section {
    padding: 40px 16px 30px;
  }
  .form-card {
    padding: 20px;
  }
  .scroll-card-wrapper {
    width: 280px;
  }
}
</style>
