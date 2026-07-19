<!-- 对比 Agent 页面 —— 左分析 + 右房源列表 -->
<template>
  <div class="compare-page">
    <!-- 加载中 -->
    <div v-if="store.loading" class="loading-wrap">
      <el-skeleton :rows="6" animated />
      <p>正在分析房源数据...</p>
    </div>

    <!-- 错误 -->
    <el-alert
      v-if="store.error"
      :title="store.error"
      type="error"
      show-icon
      closable
      @close="store.error = null"
    />

    <!-- 空状态 -->
    <el-empty v-if="!store.loading && allIds.length === 0 && !store.error" description="请从 Agent 对话中选择房源后进行对比" />

    <!-- 主内容 -->
    <div v-if="!store.loading && allIds.length > 0" class="compare-main">
      <!-- 左：AI 分析 -->
      <div class="compare-left">
        <div class="analysis-card">
          <div class="analysis-content" v-html="renderedReply"></div>
        </div>
        <div class="followup-area">
          <el-input
            v-model="followupText"
            placeholder="追问，如：我更看重通勤... 或者：帮我对比一下安全方面"
            :disabled="store.loading"
            @keyup.enter.exact="onFollowup"
          >
            <template #append>
              <el-button :loading="store.loading" @click="onFollowup">发送</el-button>
            </template>
          </el-input>
          <div class="followup-hints">
            <el-tag
              v-for="h in hints"
              :key="h"
              class="hint-tag"
              @click="followupText = h; onFollowup()"
            >{{ h }}</el-tag>
          </div>
        </div>
      </div>

      <!-- 右：房源勾选列表 -->
      <div class="compare-right">
        <div class="prop-list-header">对比房源（{{ checkedIds.length }} / {{ allIds.length }}）</div>
        <div class="prop-list">
          <div
            v-for="pid in allIds"
            :key="pid"
            class="prop-row"
            :class="{ checked: checkedIds.includes(pid) }"
            @click="toggleCheck(pid)"
          >
            <el-checkbox :model-value="checkedIds.includes(pid)" @click.stop @change="toggleCheck(pid)" />
            <div class="prop-row__img">
              <img v-if="getImage(pid)" :src="getImage(pid)!" />
              <div v-else class="prop-row__placeholder">
                <el-icon :size="20"><PictureFilled /></el-icon>
              </div>
            </div>
            <div class="prop-row__info">
              <div class="prop-row__title">{{ store.propertyData[pid]?.title || '房源 ' + pid }}</div>
              <div class="prop-row__meta">
                ¥{{ fmtPrice(pid) }} · {{ store.propertyData[pid]?.area_sqm || '?' }}㎡ · {{ typeLabel(pid) }}
              </div>
              <div class="prop-row__district">{{ store.propertyData[pid]?.district }}</div>
            </div>
          </div>
        </div>
        <el-button
          type="primary"
          class="update-btn"
          :disabled="checkedIds.length < 2"
          :loading="store.loading"
          @click="refreshCompare"
        >更新对比</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { PictureFilled } from '@element-plus/icons-vue'
import { useCompareStore } from '@/stores/compare'

const route = useRoute()
const store = useCompareStore()
const followupText = ref('')
const checkedIds = ref<number[]>([])

const allIds = computed(() => store.propertyIds)
const hints = ['我更看重通勤', '我更看重价格', '我更看重安全', '综合对比一下', '哪个性价比最高？']

const typeMap: Record<string, string> = { apartment: '公寓', house: '别墅', studio: '单间', shared: '合租' }

function typeLabel(pid: number): string {
  return typeMap[store.propertyData[pid]?.property_type] || store.propertyData[pid]?.property_type || '?'
}

function fmtPrice(pid: number): string {
  const p = store.propertyData[pid]?.price_monthly
  return p ? Number(p).toLocaleString() : '?'
}

function getImage(pid: number): string | null {
  const d = store.propertyData[pid] as any
  if (!d || !d.image_count) return null
  return null // 精简：暂不从 propertyData 取图片 URL
}

function toggleCheck(pid: number) {
  const idx = checkedIds.value.indexOf(pid)
  if (idx >= 0) {
    if (checkedIds.value.length > 2) checkedIds.value.splice(idx, 1)
  } else {
    checkedIds.value.push(pid)
  }
}

const renderedReply = computed(() => {
  const text = store.reply || '暂无分析'
  return text
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
})

async function onFollowup() {
  const msg = followupText.value.trim()
  if (!msg) return
  followupText.value = ''
  // 检测用户是否表达了偏好 → 映射为 priority
  let priority: string | null = null
  if (/通勤|交通|距离|远近|步行|公交/.test(msg)) priority = 'commute'
  else if (/价格|便宜|贵|预算|省钱|性价比/.test(msg)) priority = 'budget'
  else if (/安全|治安|犯罪/.test(msg)) priority = 'safety'
  else if (/空间|面积|大小|宽敞/.test(msg)) priority = 'space'

  await store.sendFollowup(msg, priority as any)
}

async function refreshCompare() {
  if (checkedIds.value.length < 2) return
  await store.sendFollowup('请针对选中的房源重新对比分析', store.priority)
}

onMounted(async () => {
  const idsParam = route.query.ids as string
  if (idsParam) {
    const ids = idsParam.split(',').map(Number).filter(Boolean)
    if (ids.length >= 2) {
      checkedIds.value = [...ids]
      await store.startComparison(ids, 'balanced')
    }
  }
})
</script>

<style scoped>
.compare-page { max-width: 1100px; margin: 0 auto; padding: 16px; }
.loading-wrap { text-align: center; padding: 40px; }
.loading-wrap p { color: #909399; margin-top: 16px; }

.compare-main { display: grid; grid-template-columns: 1fr 300px; gap: 20px; }
@media (max-width: 900px) { .compare-main { grid-template-columns: 1fr; } }

/* ── 左栏 ── */
.compare-left { display: flex; flex-direction: column; gap: 16px; }
.analysis-card { background: #fff; border: 1px solid #e4e7ed; border-radius: 8px; padding: 20px; max-height: 65vh; overflow-y: auto; }
.analysis-content { font-size: 14px; line-height: 1.9; color: #303133; }

.followup-area { background: #fff; border: 1px solid #e4e7ed; border-radius: 8px; padding: 12px; }
.followup-hints { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.hint-tag { cursor: pointer; }
.hint-tag:hover { opacity: 0.8; }

/* ── 右栏 ── */
.compare-right { background: #fff; border: 1px solid #e4e7ed; border-radius: 8px; padding: 12px; display: flex; flex-direction: column; max-height: calc(100vh - 100px); }
.prop-list-header { font-weight: 600; font-size: 14px; margin-bottom: 8px; color: #303133; }
.prop-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
.prop-row { display: flex; align-items: center; gap: 8px; padding: 8px; border-radius: 6px; cursor: pointer; transition: background 0.15s; }
.prop-row:hover { background: #f5f7fa; }
.prop-row.checked { background: #ecf5ff; }
.prop-row__img { width: 48px; height: 36px; border-radius: 4px; overflow: hidden; flex-shrink: 0; background: #f0f2f5; }
.prop-row__img img { width: 100%; height: 100%; object-fit: cover; }
.prop-row__placeholder { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; color: #c0c4cc; }
.prop-row__info { flex: 1; min-width: 0; }
.prop-row__title { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.prop-row__meta { font-size: 12px; color: #606266; }
.prop-row__district { font-size: 11px; color: #909399; }
.update-btn { width: 100%; margin-top: 10px; }
</style>
