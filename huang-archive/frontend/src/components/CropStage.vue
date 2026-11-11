<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({ src: { type: String, default: '' } })
const emit = defineEmits(['ready'])

const canvasRef = ref(null)
const img = new Image()
img.crossOrigin = 'anonymous'
let sx = 0
let sy = 0
let dragging = false
let lastX = 0
let lastY = 0

function draw() {
  const canvas = canvasRef.value
  if (!canvas || !img.naturalWidth) return
  const ctx = canvas.getContext('2d')
  const size = Math.min(img.naturalWidth, img.naturalHeight)
  sx = Math.max(0, Math.min(sx, img.naturalWidth - size))
  sy = Math.max(0, Math.min(sy, img.naturalHeight - size))
  canvas.width = 480
  canvas.height = 480
  ctx.fillStyle = '#111'
  ctx.fillRect(0, 0, 480, 480)
  ctx.drawImage(img, sx, sy, size, size, 0, 0, 480, 480)
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
  const size = Math.min(img.naturalWidth, img.naturalHeight)
  const scale = size / 480
  sx -= (e.clientX - lastX) * scale
  sy -= (e.clientY - lastY) * scale
  lastX = e.clientX
  lastY = e.clientY
  draw()
}

function onUp() {
  dragging = false
}

watch(
  () => props.src,
  (src) => {
    if (!src) return
    img.onload = () => {
      const size = Math.min(img.naturalWidth, img.naturalHeight)
      sx = (img.naturalWidth - size) / 2
      sy = (img.naturalHeight - size) / 2
      draw()
    }
    img.src = src
  },
  { immediate: true },
)

onMounted(() => window.addEventListener('pointerup', onUp))
onUnmounted(() => window.removeEventListener('pointerup', onUp))
</script>

<template>
  <canvas
    ref="canvasRef"
    class="w-full max-w-[480px] mx-auto border border-clay cursor-grab touch-none"
    data-testid="crop-canvas"
    @pointerdown="onDown"
    @pointermove="onMove"
    @pointerup="onUp"
    @pointerleave="onUp"
  />
</template>
