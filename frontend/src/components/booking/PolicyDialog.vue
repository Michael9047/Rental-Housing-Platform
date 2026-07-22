<!-- 信息确认页协议正文弹窗，不改变协议内容或同意状态。 -->
<template>
  <el-dialog
    v-model="visible"
    class="policy-dialog"
    width="min(860px, calc(100vw - 32px))"
    top="8vh"
    append-to-body
    lock-scroll
    :close-on-press-escape="true"
    :close-on-click-modal="true"
    :destroy-on-close="false"
    role="dialog"
    aria-modal="true"
    :aria-labelledby="titleId"
    @opened="focusContent"
    @closed="emit('closed')"
  >
    <template #header>
      <div :id="titleId" class="dialog-heading">
        <strong>{{ document?.title || '协议正文' }}</strong>
        <span v-if="document">版本 {{ document.version }}</span>
      </div>
    </template>

    <div ref="contentRef" class="policy-content" tabindex="0">
      <pre>{{ document?.content || '' }}</pre>
    </div>

    <template #footer>
      <el-button type="primary" @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import type { PolicyDocument } from '@/services/policy'

const props = defineProps<{ modelValue: boolean; document: PolicyDocument | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; closed: [] }>()
const contentRef = ref<HTMLElement | null>(null)
const titleId = computed(() => `policy-dialog-title-${props.document?.key || 'document'}`)
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

async function focusContent() {
  await nextTick()
  contentRef.value?.focus()
}

function handleEscape(event: KeyboardEvent) {
  if (event.key === 'Escape' && visible.value) visible.value = false
}
onMounted(() => window.addEventListener('keydown', handleEscape))
onBeforeUnmount(() => window.removeEventListener('keydown', handleEscape))
</script>

<style>
.policy-dialog { margin-bottom: 0; max-height: 84vh; display: flex; flex-direction: column; overflow: hidden; }
.policy-dialog .el-dialog__header { flex: 0 0 auto; margin: 0; padding: 20px 24px 16px; border-bottom: 1px solid var(--border-light); }
.policy-dialog .el-dialog__body { flex: 1 1 auto; min-height: 0; padding: 0; overflow: hidden; }
.policy-dialog .el-dialog__footer { flex: 0 0 auto; padding: 14px 24px; border-top: 1px solid var(--border-light); }
.dialog-heading { display: flex; align-items: baseline; gap: 12px; padding-right: 32px; }
.dialog-heading strong { font-size: 19px; }
.dialog-heading span { color: var(--text-muted); font-size: 13px; }
.policy-content { height: min(62vh, 620px); padding: 24px 28px; box-sizing: border-box; overflow-y: auto; outline-offset: -3px; overscroll-behavior: contain; }
.policy-content pre { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.8; color: var(--text-primary); }
@media (max-width: 600px) {
  .policy-dialog { width: calc(100vw - 16px) !important; max-height: 94vh; margin-top: 3vh; }
  .policy-content { height: calc(94vh - 132px); padding: 18px 16px; }
  .dialog-heading { display: grid; gap: 4px; }
}
</style>
