<template>
  <div class="image-uploader">
    <div class="upload-header">
      <span class="upload-title">{{ title }}</span>
      <span class="upload-hint">{{ hint }}</span>
    </div>

    <!-- Upload zone -->
    <div
      v-if="uploadedUrls.length < maxFiles"
      class="upload-zone"
      :class="{ dragover: isDragging }"
      @click="triggerFileInput"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="onDrop"
    >
      <input
        ref="fileInput"
        type="file"
        :accept="'image/jpeg,image/png,image/webp'"
        multiple
        style="display:none"
        @change="onFileChange"
      />
      <el-icon :size="32" color="#c0c4cc"><UploadFilled /></el-icon>
      <p>拖拽图片到此处，或 <em>点击上传</em></p>
    </div>

    <!-- Uploading indicator -->
    <div v-if="uploading" class="upload-progress">
      <el-progress :percentage="uploadProgress" :stroke-width="6" />
      <span>上传中...</span>
    </div>

    <!-- Thumbnails -->
    <div v-if="uploadedUrls.length > 0" class="thumb-list">
      <div
        v-for="(url, idx) in uploadedUrls"
        :key="idx"
        class="thumb-item"
        :class="{ failed: failedIdx.has(idx) }"
        draggable="true"
        @dragstart="onDragStart(idx)"
        @dragover.prevent
        @drop="onDropSwap($event, idx)"
      >
        <img :src="url" class="thumb-img" @click="previewUrl = url" />
        <el-button
          class="thumb-delete"
          size="small"
          circle
          type="danger"
          :icon="Delete"
          @click.stop="removeImage(idx)"
        />
        <div v-if="failedIdx.has(idx)" class="thumb-retry">
          <el-button size="small" type="warning" @click="retryUpload(idx)">重试</el-button>
        </div>
      </div>
    </div>

    <!-- Validation -->
    <div v-if="errorMsg" class="upload-error">{{ errorMsg }}</div>

    <!-- Preview dialog -->
    <el-dialog v-model="showPreview" title="图片预览" width="80%" :close-on-click-modal="true">
      <img :src="previewUrl" style="width:100%;max-height:70vh;object-fit:contain" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { UploadFilled, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/services/api'

const props = withDefaults(defineProps<{
  title?: string
  hint?: string
  minFiles?: number
  maxFiles?: number
  uploadUrl?: string
  modelValue?: string[]
}>(), {
  title: '房源图片',
  hint: '',
  minFiles: 0,
  maxFiles: 15,
  uploadUrl: '/upload/temp',
  modelValue: () => [],
})

const emit = defineEmits<{
  (e: 'update:modelValue', urls: string[]): void
}>()

const fileInput = ref<HTMLInputElement>()
const isDragging = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadedUrls = ref<string[]>([...props.modelValue])
const failedIdx = ref<Set<number>>(new Set())
const errorMsg = ref('')
const showPreview = ref(false)
const previewUrl = ref('')
let dragIdx = -1

const isValid = computed(() => {
  const count = uploadedUrls.value.filter((_, i) => !failedIdx.value.has(i)).length
  return count >= props.minFiles
})

watch(() => props.modelValue, (val) => {
  uploadedUrls.value = [...val]
})

watch(uploadedUrls, (val) => {
  emit('update:modelValue', val)
  if (val.length >= props.minFiles) errorMsg.value = ''
}, { deep: true })

function triggerFileInput() {
  fileInput.value?.click()
}

function onFileChange(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (files) uploadFiles(Array.from(files))
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  const files = e.dataTransfer?.files
  if (files) uploadFiles(Array.from(files))
}

async function uploadFiles(files: File[]) {
  const valid: File[] = []
  for (const f of files) {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(f.type)) {
      ElMessage.error(`不支持 ${f.type} 格式`)
      continue
    }
    if (f.size > 5 * 1024 * 1024) {
      ElMessage.error(`${f.name} 超过 5MB`)
      continue
    }
    valid.push(f)
  }
  if (valid.length === 0) return

  const remaining = props.maxFiles - uploadedUrls.value.length
  if (remaining <= 0) {
    ElMessage.warning(`最多上传 ${props.maxFiles} 张`)
    return
  }

  const toUpload = valid.slice(0, remaining)
  uploading.value = true
  uploadProgress.value = 0

  const formData = new FormData()
  toUpload.forEach(f => formData.append('files', f))

  try {
    const res = await api.post(props.uploadUrl, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total) uploadProgress.value = Math.round((e.loaded * 100) / e.total)
      },
    })
    uploadedUrls.value.push(...res.data.urls)
    ElMessage.success(`成功上传 ${res.data.count} 张图片`)
  } catch (e: any) {
    ElMessage.error('上传失败，请重试')
  } finally {
    uploading.value = false
    uploadProgress.value = 0
  }
}

function removeImage(idx: number) {
  uploadedUrls.value.splice(idx, 1)
  failedIdx.value.delete(idx)
}

function retryUpload(idx: number) {
  failedIdx.value.delete(idx)
}

function onDragStart(idx: number) {
  dragIdx = idx
}

function onDropSwap(_e: DragEvent, targetIdx: number) {
  if (dragIdx === -1 || dragIdx === targetIdx) return
  const arr = uploadedUrls.value
  const item = arr[dragIdx]
  arr.splice(dragIdx, 1)
  arr.splice(targetIdx, 0, item)
  uploadedUrls.value = [...arr]
  dragIdx = -1
}

function validate(): boolean {
  if (uploadedUrls.value.length < props.minFiles) {
    errorMsg.value = `请至少上传 ${props.minFiles} 张图片`
    return false
  }
  errorMsg.value = ''
  return true
}

defineExpose({ validate, uploadedUrls, isValid })
</script>

<style scoped>
.image-uploader {
  margin: 16px 0;
}

.upload-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 8px;
}

.upload-title {
  font-size: 15px;
  font-weight: 700;
  color: #303133;
}

.upload-hint {
  font-size: 12px;
  color: #909399;
}

.upload-zone {
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  color: #606266;
  background: #fafafa;
}

.upload-zone:hover,
.upload-zone.dragover {
  border-color: #409eff;
  background: #ecf5ff;
}

.upload-zone em {
  color: #409eff;
  font-style: normal;
}

.upload-progress {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.thumb-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.thumb-item {
  position: relative;
  width: 120px;
  height: 90px;
  border-radius: 6px;
  overflow: hidden;
  border: 2px solid #e4e7ed;
  cursor: grab;
}

.thumb-item.failed {
  border-color: #f56c6c;
}

.thumb-item:active {
  cursor: grabbing;
}

.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  cursor: pointer;
}

.thumb-delete {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 20px !important;
  height: 20px !important;
  padding: 0 !important;
  font-size: 10px !important;
}

.thumb-retry {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0,0,0,0.6);
  text-align: center;
}

.upload-error {
  color: #f56c6c;
  font-size: 13px;
  margin-top: 8px;
}
</style>
