<template>
  <div class="page-container">
    <h2>合同模板管理</h2>

    <el-row :gutter="16" style="margin-top:16px">
      <!-- 左侧：我的公寓 -->
      <el-col :span="6">
        <el-card shadow="never">
          <template #header><span>🏢 我的公寓</span></template>
          <div v-if="buildings.length === 0" style="text-align:center;padding:20px;color:#909399">暂无公寓</div>
          <div v-for="b in buildings" :key="b.id"
               :class="['bld-item', { active: selectedBld?.id === b.id }]"
               @click="selectBuilding(b)">
            <div class="bld-name">{{ b.name_cn || b.name }}</div>
            <div class="bld-city">{{ b.city || '' }}</div>
            <el-tag size="small" v-if="getTplCount(b.id)">{{ getTplCount(b.id) }} 模板</el-tag>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：模板列表 + PDF预览 -->
      <el-col :span="18">
        <el-card v-if="!selectedBld" shadow="never" style="text-align:center;padding:60px;color:#909399">
          ← 选择左侧公寓查看合同模板
        </el-card>

        <template v-else>
          <!-- 模板列表 -->
          <el-card shadow="never" style="margin-bottom:16px">
            <template #header>
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span>📄 {{ selectedBld.name_cn || selectedBld.name }} — 合同模板</span>
                <el-button type="primary" size="small" @click="showUpload = true">+ 上传模板</el-button>
              </div>
            </template>
            <div v-if="bldTemplates.length === 0" style="text-align:center;padding:20px;color:#909399">
              暂无模板，请上传
            </div>
            <div v-for="tpl in bldTemplates" :key="tpl.id"
                 :class="['tpl-row', { active: activeTpl?.id === tpl.id }]"
                 @click="selectTemplate(tpl)">
              <span class="tpl-name">{{ tpl.name }}</span>
              <el-tag size="small">{{ Object.keys(tpl.field_positions || {}).length }} 字段</el-tag>
              <span style="font-size:12px;color:#909399">{{ tpl.created_at?.slice(0,10) }}</span>
              <el-button size="small" text type="danger" @click.stop="deleteTemplate(tpl)">删除</el-button>
            </div>
          </el-card>

          <!-- PDF 预览 + 挖空 -->
          <el-card v-if="activeTpl" shadow="never">
            <template #header>
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span>{{ activeTpl.name }}</span>
                <div style="display:flex;gap:8px">
                  <el-button :type="digMode ? 'warning' : 'default'" size="small" @click="digMode = !digMode">
                    🔲 {{ digMode ? '退出挖空' : '挖空' }}
                  </el-button>
                  <el-button type="primary" size="small" :loading="saving" @click="saveFields">保存坐标</el-button>
                </div>
              </div>
            </template>
            <div v-if="digMode" style="margin-bottom:8px;padding:8px;background:#fff3cd;border-radius:6px;font-size:13px">
              💡 选择字段后在 PDF 上点击目标位置
              <el-select v-model="selectedField" placeholder="选择字段" size="small" style="width:160px;margin:0 8px">
                <el-option v-for="f in fieldOptions" :key="f.key" :label="f.label" :value="f.key" />
              </el-select>
              <el-tag v-for="(_, key) in activeTpl.field_positions" :key="key" size="small" closable style="margin:0 2px" @close="removeField(key as string)">
                {{ fieldOptions.find(f=>f.key===key)?.label || key }}
              </el-tag>
            </div>
            <div ref="pdfContainer" style="border:1px solid #dcdfe6;min-height:600px;position:relative;overflow:auto;background:#f5f5f5"
                 @mousedown="onMouseDown" @mousemove="onMouseMove" @mouseup="onMouseUp" @mouseleave="onMouseUp">
              <iframe v-if="pdfUrl" :src="pdfUrl" width="100%" height="800" :style="{border:'none',pointerEvents:digMode?'none':'auto'}" />
              <!-- 已保存的字段标记 -->
              <div v-for="(pos, key) in activeTpl.field_positions" :key="key" class="field-marker"
                   :style="{left:pos.x+'px',top:pos.y+'px',width:(pos.w||80)+'px',height:(pos.h||20)+'px'}">
                {{ fieldOptions.find(f=>f.key===key)?.label || key }}
              </div>
              <!-- 拖动框选中的临时矩形 -->
              <div v-if="dragRect" class="drag-rect"
                   :style="{left:dragRect.x+'px',top:dragRect.y+'px',width:dragRect.w+'px',height:dragRect.h+'px'}" />
            </div>
          </el-card>
        </template>
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

const buildings = ref<any[]>([])
const selectedBld = ref<any>(null)
const templates = ref<any[]>([])
const activeTpl = ref<any>(null)
const digMode = ref(false)
const selectedField = ref('')
// 框选状态
const dragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })
const dragRect = ref<{ x: number; y: number; w: number; h: number } | null>(null)
const showUpload = ref(false)
const uploading = ref(false)
const saving = ref(false)
const fileInput = ref<HTMLInputElement>()

const bldTemplates = computed(() => templates.value.filter(t => t.institute_id === selectedBld.value?.id))
const pdfUrl = computed(() => activeTpl.value ? `/api/v1/contracts/templates/${activeTpl.value.id}/file` : '')

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

onMounted(async () => {
  await loadBuildings()
  await loadTemplates()
})

function getTplCount(bldId: number) { return templates.value.filter(t => t.institute_id === bldId).length }

async function loadBuildings() {
  try { const r = await api.get('/buildings', { params: { limit: 200 } }); buildings.value = Array.isArray(r.data) ? r.data : (r.data.items || []) } catch { /* */ }
}
async function loadTemplates() {
  try { const r = await api.get('/contracts/templates'); templates.value = r.data.items || [] } catch { /* */ }
}

function selectBuilding(b: any) { selectedBld.value = b; activeTpl.value = null; digMode.value = false }
function selectTemplate(tpl: any) { activeTpl.value = { ...tpl, field_positions: { ...tpl.field_positions } }; digMode.value = false; selectedField.value = '' }
function removeField(key: string) { if (activeTpl.value?.field_positions) delete activeTpl.value.field_positions[key] }

function getCoords(e: MouseEvent) {
  const container = (e.currentTarget as HTMLElement) || (e.target as HTMLElement)
  const r = container.getBoundingClientRect()
  return { x: Math.round(e.clientX - r.left + container.scrollLeft), y: Math.round(e.clientY - r.top + container.scrollTop) }
}
function onMouseDown(e: MouseEvent) {
  if (!digMode.value || !selectedField.value || !activeTpl.value) return
  dragging.value = true
  dragStart.value = getCoords(e)
  dragRect.value = null
}
function onMouseMove(e: MouseEvent) {
  if (!dragging.value) return
  const p = getCoords(e)
  dragRect.value = {
    x: Math.min(dragStart.value.x, p.x),
    y: Math.min(dragStart.value.y, p.y),
    w: Math.abs(p.x - dragStart.value.x),
    h: Math.abs(p.y - dragStart.value.y),
  }
}
function onMouseUp(_e: MouseEvent) {
  if (!dragging.value || !selectedField.value || !activeTpl.value) { dragging.value = false; return }
  dragging.value = false
  if (dragRect.value && dragRect.value.w > 5 && dragRect.value.h > 5) {
    if (!activeTpl.value.field_positions) activeTpl.value.field_positions = {}
    const label = fieldOptions.find(f => f.key === selectedField.value)?.label || selectedField.value
    activeTpl.value.field_positions[selectedField.value] = {
      page: 1,
      x: dragRect.value.x, y: dragRect.value.y,
      w: dragRect.value.w, h: dragRect.value.h,
      font_size: Math.max(10, Math.round(dragRect.value.h * 0.6)),
    }
    ElMessage.success(`已框选「${label}」`)
  }
  dragRect.value = null
}

function onFileSelected(e: Event) { const file = (e.target as HTMLInputElement).files?.[0]; if (file) uploadForm.value.file = file }

async function doUpload() {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('name', uploadForm.value.name)
    fd.append('institute_id', String(selectedBld.value.id))
    fd.append('file', uploadForm.value.file!)
    await api.post('/contracts/templates', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success('模板上传成功')
    showUpload.value = false
    uploadForm.value = { name: '', file: null }
    loadTemplates()
  } catch { ElMessage.error('上传失败') }
  finally { uploading.value = false }
}

async function saveFields() {
  if (!activeTpl.value) return; saving.value = true
  try {
    await api.put(`/contracts/templates/${activeTpl.value.id}`, { field_positions: activeTpl.value.field_positions })
    ElMessage.success('坐标已保存')
  } catch { ElMessage.error('保存失败') }
  finally { saving.value = false }
}

async function deleteTemplate(tpl: any) {
  try { await ElMessageBox.confirm('确定删除该模板？', '确认删除', { type: 'warning' }) } catch { return }
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
.bld-item { padding: 10px 14px; border-bottom: 1px solid #ebeef5; cursor: pointer; border-radius: 4px }
.bld-item:hover { background: #f5f7fa }
.bld-item.active { background: var(--primary-light); border-left: 3px solid var(--primary) }
.bld-name { font-weight: 600 }
.bld-city { font-size: 12px; color: #909399 }
.tpl-row { padding: 10px 14px; border-bottom: 1px solid #ebeef5; cursor: pointer; display: flex; align-items: center; gap: 12px; border-radius: 4px }
.tpl-row:hover { background: #f5f7fa }
.tpl-row.active { background: var(--primary-light) }
.tpl-name { font-weight: 600; flex: 1 }
.field-marker { position: absolute; background: rgba(233,69,96,0.7); color: white; padding: 2px 6px; border-radius: 2px; font-size: 11px; pointer-events: none; white-space: nowrap; z-index: 10; border: 2px dashed rgba(255,255,255,0.7); display: flex; align-items: center; justify-content: center; overflow: hidden }
.drag-rect { position: absolute; border: 2px dashed #e94560; background: rgba(233,69,96,0.15); pointer-events: none; z-index: 20 }
</style>
