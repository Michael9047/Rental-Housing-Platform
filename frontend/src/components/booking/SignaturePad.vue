<!-- 使用 Pointer Events 的高分屏手写签名画布。 -->
<template>
  <div class="signature-pad">
    <canvas
      ref="canvasRef" aria-label="租客手写签名区域" tabindex="0"
      @pointerdown="pointerDown" @pointermove="pointerMove" @pointerup="pointerUp" @pointercancel="pointerCancel"
    />
    <span v-if="!strokes.length" class="signature-placeholder">请在此处签名 / Sign here</span>
    <div class="signature-tools"><el-button size="small" :disabled="!strokes.length" @click="undo">撤销上一笔</el-button><el-button size="small" :disabled="!strokes.length" @click="clear">清除签名</el-button></div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

export interface SignaturePoint { x: number; y: number; pressure: number }
const emit = defineEmits<{ change: [strokes: SignaturePoint[][]] }>()
const canvasRef = ref<HTMLCanvasElement | null>(null); const strokes = ref<SignaturePoint[][]>([]); let active: SignaturePoint[] | null = null; let resizeObserver: ResizeObserver | null = null

function setupCanvas() {
  const canvas = canvasRef.value; if (!canvas) return
  const rect = canvas.getBoundingClientRect(); const ratio = window.devicePixelRatio || 1
  canvas.width = Math.max(1, Math.round(rect.width * ratio)); canvas.height = Math.max(1, Math.round(rect.height * ratio))
  const context = canvas.getContext('2d'); if (!context) return
  context.setTransform(ratio, 0, 0, ratio, 0, 0); context.lineCap = 'round'; context.lineJoin = 'round'; context.strokeStyle = '#111'; context.lineWidth = 2.2
  redraw()
}
function point(event: PointerEvent): SignaturePoint { const rect = canvasRef.value!.getBoundingClientRect(); return { x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)), y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)), pressure: event.pressure || 0.5 } }
function drawSegment(left: SignaturePoint, right: SignaturePoint) { const canvas = canvasRef.value; const context = canvas?.getContext('2d'); if (!canvas || !context) return; const rect = canvas.getBoundingClientRect(); context.beginPath(); context.moveTo(left.x * rect.width, left.y * rect.height); context.lineTo(right.x * rect.width, right.y * rect.height); context.stroke() }
function redraw() { const canvas = canvasRef.value; const context = canvas?.getContext('2d'); if (!canvas || !context) return; const rect = canvas.getBoundingClientRect(); context.clearRect(0, 0, rect.width, rect.height); strokes.value.forEach((stroke) => stroke.slice(1).forEach((item, index) => drawSegment(stroke[index], item))) }
function pointerDown(event: PointerEvent) { if (event.button !== 0 && event.pointerType === 'mouse') return; event.preventDefault(); canvasRef.value?.setPointerCapture(event.pointerId); active = [point(event)]; strokes.value.push(active) }
function pointerMove(event: PointerEvent) { if (!active) return; event.preventDefault(); const next = point(event); drawSegment(active[active.length - 1], next); active.push(next) }
function snapshot() { return strokes.value.map((stroke) => stroke.map((item) => ({ ...item }))) }
function finish(event: PointerEvent) { if (!active) return; event.preventDefault(); if (canvasRef.value?.hasPointerCapture(event.pointerId)) canvasRef.value.releasePointerCapture(event.pointerId); active = null; emit('change', snapshot()) }
function pointerUp(event: PointerEvent) { finish(event) } function pointerCancel(event: PointerEvent) { finish(event) }
function clear() { strokes.value = []; active = null; redraw(); emit('change', []) }
function undo() { strokes.value.pop(); redraw(); emit('change', snapshot()) }
onMounted(async () => { await nextTick(); setupCanvas(); resizeObserver = new ResizeObserver(setupCanvas); if (canvasRef.value) resizeObserver.observe(canvasRef.value) })
onBeforeUnmount(() => resizeObserver?.disconnect())
defineExpose({ clear, undo })
</script>

<style scoped>
.signature-pad{position:relative}.signature-pad canvas{display:block;width:100%;height:220px;border:2px solid #495057;border-radius:8px;background:#fff;touch-action:none;cursor:crosshair}.signature-placeholder{position:absolute;left:0;right:0;top:92px;text-align:center;color:#9aa0a6;pointer-events:none}.signature-tools{display:flex;justify-content:flex-end;gap:8px;margin-top:10px}@media(max-width:600px){.signature-pad canvas{height:190px}}
</style>
