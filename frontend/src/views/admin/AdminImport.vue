<template>
  <div class="admin-import">
    <h2>数据导入</h2>

    <!-- Upload -->
    <el-card shadow="never" class="section-card">
      <template #header><span class="card-title">上传文件</span></template>
      <el-upload ref="uploadRef" class="upload-area" drag :auto-upload="false" :limit="1"
                 :on-change="handleFileChange" :on-remove="handleFileRemove"
                 :accept="'.csv,.xlsx,.xls'">
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">
          <p>将 CSV 或 Excel 文件拖放到此处</p>
          <p class="upload-hint">支持 .csv / .xlsx / .xls，最大 10 MB</p>
        </div>
      </el-upload>
    </el-card>

    <!-- Loading -->
    <el-card v-if="previewLoading" shadow="never" class="section-card">
      <div style="text-align:center;padding:40px;color:#909399">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <p style="margin-top:12px">正在解析文件并运行 IQR + 孤立森林检测...</p>
      </div>
    </el-card>

    <!-- ====== PREVIEW TABLE ====== -->
    <el-card v-if="previewRows.length && !previewLoading" shadow="never" class="section-card">
      <template #header>
        <div class="preview-header">
          <span class="card-title">预览检测 — {{ previewRows.length }} 行</span>
          <div>
            <el-button size="small" @click="forceAllAI">全部忽略AI警告</el-button>
            <el-button size="small" @click="resetAllForce">重置</el-button>
          </div>
        </div>
      </template>

      <!-- Legend -->
      <div class="legend">
        <span class="badge badge-err">🔴 验证错误（不录入）</span>
        <span class="badge badge-iqr">🟠 IQR异常</span>
        <span class="badge badge-if">🟣 孤立森林</span>
        <span class="badge badge-ok">✅ 清洁行（自动录入）</span>
        <span class="badge badge-force">✅ 已忽略AI（将录入）</span>
      </div>

      <el-table :data="previewRows" border stripe size="small" max-height="500"
                :row-class-name="previewRowClass">
        <el-table-column prop="row" label="行号" width="55" align="center" />
        <el-table-column label="标题" min-width="140" show-overflow-tooltip>
          <template #default="{ row: r }">
            {{ getTitle(r) }}
          </template>
        </el-table-column>
        <el-table-column label="地址" min-width="170" show-overflow-tooltip>
          <template #default="{ row: r }">
            <span style="font-size:12px;color:#909399">{{ getAddr(r) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="区域" width="80">
          <template #default="{ row: r }">{{ getDist(r) }}</template>
        </el-table-column>
        <el-table-column label="月租" width="80" align="right">
          <template #default="{ row: r }">{{ getPrice(r) }}</template>
        </el-table-column>
        <el-table-column label="检测结果" min-width="280">
          <template #default="{ row: r }">
            <div class="issue-list">
              <template v-if="r.errors?.length">
                <el-tag v-for="(e,i) in r.errors" :key="'e'+i" type="danger" size="small" effect="dark"
                        class="issue-tag" disable-transitions>❌ {{ e.error }}</el-tag>
              </template>
              <template v-if="r.iqr_flagged">
                <el-tag v-for="(w,i) in getAIWarnings(r,'iqr_outlier')" :key="'iqr'+i"
                        type="warning" size="small" effect="dark" class="issue-tag" disable-transitions>
                  🔶 {{ w.error }}</el-tag>
              </template>
              <template v-if="r.iforest_flagged">
                <el-tag v-for="(w,i) in getAIWarnings(r,'iforest_outlier')" :key="'if'+i"
                        size="small" effect="dark" class="issue-tag if-tag" disable-transitions>
                  🔷 {{ w.error }}</el-tag>
              </template>
              <template v-if="isClean(r)">
                <span style="color:#67c23a;font-size:13px">✅ 清洁行，自动录入</span>
              </template>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="忽略AI警告" width="120" align="center">
          <template #default="{ row: r }">
            <template v-if="hasErrors(r)">
              <span style="color:#f56c6c;font-size:12px;font-weight:600">❌ 无法录入</span>
            </template>
            <template v-else-if="hasAIWarnings(r)">
              <el-button :type="ignoreMap[r.row] ? 'success' : 'warning'" size="small"
                         @click="toggleForce(r.row)" plain>
                {{ ignoreMap[r.row] ? '✅ 已忽略AI' : '忽略AI警告' }}
              </el-button>
            </template>
            <template v-else>
              <span style="color:#67c23a;font-size:12px">✅ 自动录入</span>
            </template>
          </template>
        </el-table-column>
      </el-table>

      <!-- Alert -->
      <el-alert type="warning" :closable="false" show-icon class="preview-alert">
        <template #title>
          🔴 <b>验证错误行永远不录入</b>（缺字段/格式错无法修复）。
          🟠🟣 <b>IQR/孤立森林警告行</b>默认不录入，点击「忽略AI警告」可忽略AI检测、正常录入该行。
          ✅ 清洁行自动录入。
        </template>
      </el-alert>

      <!-- Confirm -->
      <div class="actions">
        <el-button type="primary" size="large" :loading="confirming"
                   @click="doConfirm" :disabled="!hasImportable">
          确认导入（{{ importableCount }} 行）
        </el-button>
        <el-button size="large" @click="doReset">取消重新上传</el-button>
      </div>
    </el-card>

    <!-- ====== IMPORT RESULT ====== -->
    <el-card v-if="importResult" shadow="never" class="section-card">
      <template #header><span class="card-title">导入结果</span></template>
      <el-row :gutter="16" class="result-row">
        <el-col :span="6"><el-statistic title="总计" :value="importResult.total_records" /></el-col>
        <el-col :span="6"><el-statistic title="成功" :value="importResult.success_records">
          <template #suffix><el-icon style="color:#67c23a"><CircleCheckFilled /></el-icon></template>
        </el-statistic></el-col>
        <el-col :span="6"><el-statistic title="失败" :value="importResult.failed_records">
          <template #suffix><el-icon v-if="importResult.failed_records>0" style="color:#f56c6c"><CircleCloseFilled /></el-icon></template>
        </el-statistic></el-col>
        <el-col :span="6"><el-statistic v-if="(importResult as any).skipped_records>0" title="跳过" :value="(importResult as any).skipped_records">
          <template #suffix><el-icon style="color:#909399"><RemoveFilled /></el-icon></template>
        </el-statistic></el-col>
      </el-row>

      <div v-if="importResult.rows?.length" class="results-table">
        <h4>逐行详情</h4>
        <el-table :data="importResult.rows" border stripe size="small" max-height="360" :row-class-name="resultRowClass">
          <el-table-column prop="row" label="行号" width="60" align="center" />
          <el-table-column label="标题" min-width="140" show-overflow-tooltip>
            <template #default="{ row: r }">{{ (r.data || {}).title || '—' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="80" align="center">
            <template #default="{ row: r }">
              <span v-if="r.status==='success'" style="font-size:18px">✅</span>
              <span v-else-if="r.status==='skipped'" style="font-size:18px">⏭️</span>
              <span v-else style="font-size:18px">❌</span>
            </template>
          </el-table-column>
          <el-table-column label="详情" min-width="220">
            <template #default="{ row: r }">
              <el-tag v-for="(e,i) in (r.errors||[])" :key="'e'+i" type="danger" size="small" effect="plain" class="err-tag">{{ e.error }}</el-tag>
              <span v-if="r.status==='skipped'" style="color:#909399;font-size:12px">未忽略AI警告，已跳过</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <!-- History (simplified) -->
    <el-card shadow="never" class="section-card" v-if="history.length">
      <template #header><span class="card-title">导入历史</span></template>
      <el-table :data="history" v-loading="historyLoading" border stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="source_name" label="文件名" min-width="180" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row: r }"><el-tag :type="r.status==='completed'?'success':'danger'" size="small">{{ r.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="total_records" label="总计" width="60" />
        <el-table-column prop="success_records" label="成功" width="60" />
        <el-table-column prop="failed_records" label="失败" width="60" />
        <el-table-column prop="created_at" label="时间" width="160">
          <template #default="{ row: r }">{{ new Date(r.created_at).toLocaleString() }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { UploadFilled, CircleCheckFilled, CircleCloseFilled, Loading, RemoveFilled } from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'
import { ElMessage } from 'element-plus'
import { adminService } from '@/services/admin'
import { extractErrorMessage } from '@/services/api'
import type { ImportResult, ImportTask, RowResult } from '@/types/admin'

const selectedFile = ref<File | null>(null)
const previewLoading = ref(false)
const previewRows = ref<RowResult[]>([])
const previewId = ref(0)
const ignoreMap = reactive<Record<number, boolean>>({})
const confirming = ref(false)
const importResult = ref<ImportResult | null>(null)
const history = ref<ImportTask[]>([])
const historyLoading = ref(false)

// ---- helpers ----
function hasErrors(r: any): boolean { return !!(r.errors && r.errors.length) }
function hasAIWarnings(r: any): boolean { return !!(r.iqr_flagged || r.iforest_flagged) }
function isClean(r: any): boolean { return !hasErrors(r) && !hasAIWarnings(r) }
function getTitle(r: any): string { return (r.data || r.data_preview || {}).title || '—' }
function getAddr(r: any): string { return (r.data || r.data_preview || {}).address || '' }
function getDist(r: any): string { return (r.data || r.data_preview || {}).district || '—' }
function getPrice(r: any): string { return (r.data || r.data_preview || {}).price_monthly || '—' }
function getAIWarnings(r: any, type: string): any[] {
  return (r.warnings || []).filter((w: any) => w.type === type)
}

const hasImportable = computed(() => previewRows.value.some(r => !hasErrors(r) && (!hasAIWarnings(r) || ignoreMap[r.row])))
const importableCount = computed(() => previewRows.value.filter(r => !hasErrors(r) && (!hasAIWarnings(r) || ignoreMap[r.row])).length)

// ---- file handling ----
function handleFileRemove() { doReset() }

async function handleFileChange(file: UploadFile) {
  const raw = file.raw
  if (!raw) return
  console.log('[AdminImport] file changed:', raw.name, raw.size)
  selectedFile.value = raw
  importResult.value = null
  previewRows.value = []

  previewLoading.value = true
  try {
    const data: any = await adminService.previewImport(raw)
    console.log('[AdminImport] preview result:', data)
    previewId.value = data.preview_id
    previewRows.value = data.rows
    for (const r of data.rows) ignoreMap[r.row] = false
    ElMessage.success(`预览完成：${data.total_records} 行已解析`)
  } catch (err: any) {
    ElMessage.error(extractErrorMessage(err) || '预览失败')
    selectedFile.value = null
  } finally { previewLoading.value = false }
}

// ---- toggle ----
function toggleForce(rowNum: number) {
  const r: any = previewRows.value.find((x: any) => x.row === rowNum)
  if (!r || hasErrors(r)) return
  ignoreMap[rowNum] = !ignoreMap[rowNum]
}

function forceAllAI() {
  for (const r of previewRows.value) {
    if (hasAIWarnings(r)) ignoreMap[r.row] = true
  }
}

function resetAllForce() {
  for (const r of previewRows.value) {
    if (hasAIWarnings(r)) ignoreMap[r.row] = false
  }
}

// ---- confirm ----
async function doConfirm() {
  if (!previewId.value) return
  const skipRows: number[] = []
  for (const r of previewRows.value) {
    if (hasErrors(r)) { skipRows.push(r.row); continue }
    if (hasAIWarnings(r) && !ignoreMap[r.row]) skipRows.push(r.row)
  }

  confirming.value = true
  try {
    const result: any = await adminService.confirmImport(previewId.value, skipRows)
    importResult.value = result
    ElMessage.success(`导入完成：成功 ${result.success_records} 条，跳过 ${skipRows.length} 条`)
    fetchHistory()
  } catch (err: any) {
    ElMessage.error(extractErrorMessage(err) || '导入失败')
  } finally { confirming.value = false }
}

function doReset() {
  selectedFile.value = null; previewRows.value = []; importResult.value = null; previewId.value = 0
}

// ---- row classes ----
function previewRowClass({ row }: { row: any }) {
  if (hasErrors(row)) return 'row-err'
  if (hasAIWarnings(row) && ignoreMap[row.row]) return 'row-force'
  if (hasAIWarnings(row)) return 'row-ai'
  return ''
}
function resultRowClass({ row }: { row: any }) {
  if (row.status === 'failed') return 'row-err'
  if (row.status === 'skipped') return 'row-force'
  return ''
}

// ---- history ----
async function fetchHistory() {
  historyLoading.value = true
  try { history.value = await adminService.getImportTasks({ skip: 0, limit: 30 }) }
  catch { /* ignore */ } finally { historyLoading.value = false }
}
onMounted(fetchHistory)
</script>

<style scoped>
.admin-import { max-width: 1100px; margin: 0 auto; }
.admin-import h2 { font-size: 22px; color: #303133; margin-bottom: 24px; }
.section-card { margin-bottom: 20px; }
.card-title { font-weight: 600; font-size: 15px; }

.upload-area { width: 100%; }
.upload-icon { font-size: 48px; color: #c0c4cc; margin-bottom: 12px; }
.upload-text p { margin: 4px 0; color: #606266; }
.upload-hint { font-size: 13px; color: #909399; }

.preview-header { display: flex; justify-content: space-between; align-items: center; }

.legend { display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.badge-err { background: #fef0f0; color: #f56c6c; border: 1px solid #fbc4c4; }
.badge-iqr { background: #fdf6ec; color: #e6a23c; border: 1px solid #f5dab1; }
.badge-if { background: #f0e6ff; color: #7c3aed; border: 1px solid #d4bfff; }
.badge-ok { background: #f0f9eb; color: #67c23a; border: 1px solid #c2e7b0; }
.badge-force { background: #ecfdf5; color: #10b981; border: 1px solid #a7f3d0; }

.issue-list { display: flex; flex-wrap: wrap; gap: 3px; align-items: center; }
.issue-tag { white-space: normal; word-break: break-all; line-height: 1.3; height: auto; padding: 2px 6px; max-width: 280px; }
.if-tag { background: #f0e6ff !important; border-color: #d4bfff !important; color: #7c3aed !important; }

.preview-alert { margin-top: 14px; }
.actions { margin-top: 14px; display: flex; gap: 12px; }

.result-row { margin-bottom: 8px; }
.results-table { margin-top: 16px; }
.results-table h4 { font-size: 14px; color: #303133; margin-bottom: 8px; }
.err-tag { white-space: normal; line-height: 1.3; height: auto; padding: 2px 6px; }
</style>

<style>
.el-table .row-err { background-color: #fef0f0 !important; }
.el-table .row-ai { background-color: #fdf6ec !important; }
.el-table .row-force { background-color: #ecfdf5 !important; }
</style>
