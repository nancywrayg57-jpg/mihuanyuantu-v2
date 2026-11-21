<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { ZoomIn, ZoomOut } from 'lucide-vue-next'

const props = defineProps({ src: { type: String, default: '' } })
const emit = defineEmits(['ready'])

const canvasRef = ref(null)
const zoom = ref(1)
const VIEW = 480
const img = new Image()
img.crossOrigin = 'anonymous'
let sx = 0
let sy = 0
let dragging = false
let lastX = 0
let lastY = 0

function cropSize() {
  if (!img.naturalWidth) return 0
  const base = Math.min(img.naturalWidth, img.naturalHeight)
  const z = Math.max(1, Math.min(4, zoom.value))
  return Math.max(32, Math.floor(base / z))
}

function clamp() {
  const size = cropSize()
  if (!size) return
  sx = Math.max(0, Math.min(sx, img.naturalWidth - size))
  sy = Math.max(0, Math.min(sy, img.naturalHeight - size))
}

function draw() {
  const canvas = canvasRef.value
  if (!canvas || !img.naturalWidth) return
  const ctx = canvas.getContext('2d')
  const size = cropSize()
  clamp()
  canvas.width = VIEW
  canvas.height = VIEW
  ctx.fillStyle = '#111'
  ctx.fillRect(0, 0, VIEW, VIEW)
  ctx.drawImage(img, sx, sy, size, size, 0, 0, VIEW, VIEW)
  // guide
  ctx.strokeStyle = 'rgba(255,255,255,0.45)'
  ctx.lineWidth = 1
  ctx.strokeRect(1, 1, VIEW - 2, VIEW - 2)
  emit('ready', canvas)
}

function onDown(e) {
  dragging = true
  lastX = e.clientX
  lastY = e.clientY
  canvasRef.value?.setPointerCapture?.(e.pointerId)
}

function onMove(e) {
  if (!dragging || !img.naturalWidth) return
  const size = cropSize()
  const scale = size / VIEW
  sx -= (e.clientX - lastX) * scale
  sy -= (e.clientY - lastY) * scale
  lastX = e.clientX
  lastY = e.clientY
  draw()
}

function onUp() {
  dragging = false
}

function zoomBy(delta) {
  if (!img.naturalWidth) return
  const prevSize = cropSize()
  const cx = sx + prevSize / 2
  const cy = sy + prevSize / 2
  const next = Math.round((zoom.value + delta) * 10) / 10
  zoom.value = Math.max(1, Math.min(4, next))
  const newSize = cropSize()
  sx = cx - newSize / 2
  sy = cy - newSize / 2
  draw()
}

function zoomIn() {
  zoomBy(0.25)
}

function zoomOut() {
  zoomBy(-0.25)
}

/** Export cropped square JPEG blob (server-ready). */
async function exportBlob(quality = 0.92) {
  if (!img.naturalWidth) return null
  const size = cropSize()
  clamp()
  const out = document.createElement('canvas')
  const dim = Math.min(1200, Math.max(size, 480))
  out.width = dim
  out.height = dim
  const ctx = out.getContext('2d')
  ctx.fillStyle = '#111'
  ctx.fillRect(0, 0, dim, dim)
  ctx.drawImage(img, sx, sy, size, size, 0, 0, dim, dim)
  return new Promise((resolve) => out.toBlob((b) => resolve(b), 'image/jpeg', quality))
}

watch(
  () => props.src,
  (src) => {
    if (!src) return
    zoom.value = 1
    img.onload = () => {
      const size = cropSize()
      sx = (img.naturalWidth - size) / 2
      sy = (img.naturalHeight - size) / 2
      draw()
    }
    img.onerror = () => emit('ready', null)
    img.src = src
  },
  { immediate: true },
)

onMounted(() => window.addEventListener('pointerup', onUp))
onUnmounted(() => window.removeEventListener('pointerup', onUp))

defineExpose({ exportBlob, zoomIn, zoomOut, zoom })
</script>

<template>
  <div class="space-y-2" data-testid="crop-stage">
    <canvas
      ref="canvasRef"
      class="w-full max-w-[480px] mx-auto border border-clay cursor-grab touch-none block"
      data-testid="crop-canvas"
      @pointerdown="onDown"
      @pointermove="onMove"
      @pointerup="onUp"
      @pointerleave="onUp"
      @wheel.prevent="(e) => (e.deltaY < 0 ? zoomIn() : zoomOut())"
    />
    <div class="flex items-center justify-center gap-2">
      <button
        type="button"
        class="min-h-tap px-3 border border-clay inline-flex items-center gap-1"
        data-testid="crop-zoom-out"
        :disabled="zoom <= 1"
        @click="zoomOut"
      >
        <ZoomOut class="w-4 h-4" /> 缩小
      </button>
      <span class="text-mute text-sm tabular-nums" data-testid="crop-zoom-label">{{ zoom.toFixed(1) }}×</span>
      <button
        type="button"
        class="min-h-tap px-3 border border-clay inline-flex items-center gap-1"
        data-testid="crop-zoom-in"
        :disabled="zoom >= 4"
        @click="zoomIn"
      >
        <ZoomIn class="w-4 h-4" /> 放大
      </button>
    </div>
  </div>
</template>
