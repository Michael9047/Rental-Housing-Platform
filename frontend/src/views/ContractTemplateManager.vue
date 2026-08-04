<template>
  <div class="page-container">
    <h2>合同模板管理</h2>

    <el-row :gutter="16" style="margin-top:16px">
      <!-- 左侧：模板列表 -->
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>📄 我的模板</span>
              <el-button type="primary" size="small" @click="showUpload = true">+ 上传模板</el-button>
            </div>
          </template>

          <div v-if="templates.length === 0" style="text-align:center;padding:40px;color:#909399">
            暂无模板，请上传 PDF 合同模板
          </div>

          <div v-for="tpl in templates" :key="tpl.id"
               :class="['tpl-item', { active: activeTpl?.id === tpl.id }]"
               @click="selectTemplate(tpl)">
            <div class="tpl-name">{{ tpl.name }}</div>
            <div class="tpl-meta">
              {{ Object.keys(tpl.field_positions || {}).length }} 个字段
              · {{ tpl.created_at?.slice(0, 10) }}
            </div>
            <div class="tpl-actions" @click.stop>
              <el-button size="small" text type="danger" @click="deleteTemplate(tpl)">删除</el-button>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：PDF预览 + 挖空 -->
      <el-col :span="16">
        <el-card v-if="!activeTpl" shadow="never" style="text-align:center;padding:60px;color:#909399">
          ← 选择左侧模板开始编辑
        </el-card>

        <el-card v-else shadow="never">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>{{ activeTpl.name }}</span>
              <div style="display:flex;gap:8px">
                <el-button :type="digMode ? 'warning' : 'default'" size="small" @click="digMode = !digMode">
                  🔲 {{ digMode ? '退出挖空' : '挖空' }}
                </el-button>
                <el-button type="primary" size="small" @click="saveFields" :loading="saving">保存坐标</el-button>
              </div>
            </div>
          </template>

          <div v-if="digMode" style="margin-bottom:8px;padding:8px;background:#fff3cd;border-radius:6px;font-size:13px">
            💡 挖空模式：先在右侧选择要标注的字段，再在左侧 PDF 上点击目标位置
            <el-select v-model="selectedField" placeholder="选择字段" size="small" style="width:180px;margin-left:8px">
              <el-option v-for="f in fieldOptions" :key="f.key" :label="f.label" :value="f.key" />
            </el-select>
            <el-tag v-if="activeTpl.field_positions" size="small" style="margin-left:8px" v-for="(pos, key) in activeTpl.field_positions" :key="key" closable @close="removeField(key as string)">
              {{ fieldOptions.find(f=>f.key===key)?.label || key }}
            </el-tag>
          </div>

          <div style="display:flex;gap:8px">
            <div ref="pdfContainer" style="flex:1;border:1px solid #dcdfe6;min-height:600px;position:relative;overflow:auto;background:#f5f5f5"
                 @click="onPdfClick">
              <iframe v-if="pdfUrl" :src="pdfUrl" width="100%" height="800" style="border:none" />
              <p v-else style="text-align:center;padding:40px;color:#909399">PDF 预览加载中...</p>
              <!-- 已标记字段层 -->
              <div v-for="(pos, key) in activeTpl.field_positions"
                   :key="key" class="field-marker"
                   :style="{left:pos.x+'px',top:pos.y+'px'}">
                {{ fieldOptions.find(f=>f.key===key)?.label || key }}
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 上传弹窗 -->
    <el-dialog v-model="showUpload" title="上传合同模板" width="400px">
      <el-form :model="uploadForm" label-width="80px">
        <el-form-item label="模板名称" required>
          <el-input v-model="uploadForm.name" placeholder="如：标准租房合同V1" />
        </el-form-item>
        <el-form-item label="PDF文件" required>
          <input ref="fileInput" type="file" accept=".pdf" style="display:none" @change="onFileSelected" />
          <el-button @click="($refs.fileInput as any)?.click()">选择文件</el-button>
          <span v-if="uploadForm.file" style="margin-left:8px">{{ (uploadForm.file as File).name }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUpload = false">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!uploadForm.name||!uploadForm.file" @click="doUpload">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/services/api'

const templates = ref<any[]>([])
const activeTpl = ref<any>(null)
const digMode = ref(false)
const selectedField = ref('')
const showUpload = ref(false)
const uploading = ref(false)
const saving = ref(false)
const fileInput = ref<HTMLInputElement>()
const pdfUrl = computed(() => {
  if (!activeTpl.value) return ''
  return `/api/v1/contracts/templates/${activeTpl.value.id}/file`
})
const uploadForm = ref({ name: '', file: null as File | null })

const fieldOptions = [
  { key: 'tenant_name', label: '租客姓名' },
  { key: 'tenant_phone', label: '租客电话' },
  { key: 'tenant_email', label: '租客邮箱' },
  { key: 'tenant_school', label: '租客学校' },
  { key: 'tenant_passport', label: '护照号' },
  { key: 'property_name', label: '公寓名' },
  { key: 'unit_type_name', label: '户型名' },
  { key: 'room_number', label: '房间号' },
  { key: 'monthly_rent', label: '月租金' },
  { key: 'deposit_amount', label: '押金' },
  { key: 'lease_start', label: '租期起始' },
  { key: 'lease_end', label: '租期结束' },
  { key: 'sign_date', label: '签署日期' },
]

onMounted(() => loadTemplates())

async function loadTemplates() {
  try {
    const r = await api.get('/contracts/templates')
    templates.value = r.data.items || []
  } catch { /* */ }
}

function selectTemplate(tpl: any) {
  activeTpl.value = { ...tpl, field_positions: { ...tpl.field_positions } }
  digMode.value = false
  selectedField.value = ''
}

function removeField(key: string) {
  if (!activeTpl.value?.field_positions) return
  delete activeTpl.value.field_positions[key]
}

function onPdfClick(e: MouseEvent) {
  if (!digMode.value || !selectedField.value || !activeTpl.value) return
  const container = e.currentTarget as HTMLElement
  const rect = container.getBoundingClientRect()
  const x = Math.round(e.clientX - rect.left + container.scrollLeft)
  const y = Math.round(e.clientY - rect.top + container.scrollTop)
  if (!activeTpl.value.field_positions) activeTpl.value.field_positions = {}
  activeTpl.value.field_positions[selectedField.value] = { page: 1, x, y, font_size: 12 }
  ElMessage.success(`已标记「${fieldOptions.find(f=>f.key===selectedField.value)?.label}」坐标 (${x}, ${y})`)
}

function onFileSelected(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) uploadForm.value.file = file
}

async function doUpload() {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('name', uploadForm.value.name)
    fd.append('file', uploadForm.value.file!)
    await api.post('/contracts/templates', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success('模板上传成功')
    showUpload.value = false
    uploadForm.value = { name: '', file: null }
    loadTemplates()
  } catch {
    ElMessage.error('上传失败')
  } finally { uploading.value = false }
}

async function saveFields() {
  if (!activeTpl.value) return
  saving.value = true
  try {
    await api.put(`/contracts/templates/${activeTpl.value.id}`, {
      field_positions: activeTpl.value.field_positions,
    })
    ElMessage.success('坐标已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally { saving.value = false }
}

async function deleteTemplate(tpl: any) {
  try {
    await ElMessageBox.confirm('确定删除该模板？删除后不可恢复。', '确认删除', { type: 'warning' })
  } catch { return }
  try {
    await api.delete(`/contracts/templates/${tpl.id}`)
    ElMessage.success('已删除')
    if (activeTpl.value?.id === tpl.id) activeTpl.value = null
    loadTemplates()
  } catch { ElMessage.error('删除失败') }
}
</script>

<style scoped>
.page-container { max-width: 1400px; margin: 0 auto; padding: 24px }
.tpl-item { padding: 12px 16px; border-bottom: 1px solid #ebeef5; cursor: pointer; border-radius: 6px; display: flex; align-items: center; gap: 12px }
.tpl-item:hover { background: #f5f7fa }
.tpl-item.active { background: var(--primary-light); border-left: 3px solid var(--primary) }
.tpl-name { font-weight: 600; flex: 1 }
.tpl-meta { font-size: 12px; color: #909399 }
.field-marker { position: absolute; background: rgba(233,69,96,0.8); color: white; padding: 1px 6px; border-radius: 3px; font-size: 11px; pointer-events: none; white-space: nowrap; z-index: 10 }
</style>
