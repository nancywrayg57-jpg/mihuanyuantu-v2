<script setup>
import { onBeforeUnmount, ref } from 'vue'
import { Mic, Square, RotateCcw, Send } from 'lucide-vue-next'

const emit = defineEmits(['publish'])

const state = ref('idle') // idle | recording | done
const error = ref('')
const duration = ref(0)
const previewUrl = ref('')
const blobRef = ref(null)

let mediaRecorder = null
let stream = null
let chunks = []
let timer = null
const MAX_SEC = 180

const MIME_CANDIDATES = [
  'audio/mp4',
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg',
]

function pickMime() {
  if (typeof MediaRecorder === 'undefined') return ''
  for (const m of MIME_CANDIDATES) {
    if (MediaRecorder.isTypeSupported(m)) return m
  }
  return ''
}

async function start() {
  error.value = ''
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mime = pickMime()
    mediaRecorder = mime
      ? new MediaRecorder(stream, { mimeType: mime })
      : new MediaRecorder(stream)
    chunks = []
    mediaRecorder.ondataavailable = (e) => {
      if (e.data?.size) chunks.push(e.data)
    }
    mediaRecorder.onstop = () => {
      const type = mediaRecorder.mimeType || 'audio/webm'
      blobRef.value = new Blob(chunks, { type })
      previewUrl.value = URL.createObjectURL(blobRef.value)
      state.value = 'done'
      cleanupStream()
    }
    mediaRecorder.start(250)
    state.value = 'recording'
    duration.value = 0
    timer = setInterval(() => {
      duration.value += 1
      if (duration.value >= MAX_SEC) stop()
    }, 1000)
  } catch (e) {
    error.value = '无法启动麦克风，请确认已授权并使用 HTTPS'
    cleanupStream()
  }
}

function stop() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
  }
}

function reset() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
  blobRef.value = null
  duration.value = 0
  state.value = 'idle'
  error.value = ''
}

function publish() {
  if (!blobRef.value) return
  emit('publish', { blob: blobRef.value, duration: duration.value })
  reset()
}

function cleanupStream() {
  if (stream) {
    stream.getTracks().forEach((t) => t.stop())
    stream = null
  }
}

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  cleanupStream()
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})
</script>

<template>
  <div class="border border-clay bg-rice p-4 space-y-3">
    <div class="flex items-center justify-between">
      <p class="text-mute">语音追忆</p>
      <p v-if="state === 'recording'" class="text-cinnabar recording-dot">
        录音中 {{ duration }}s / {{ MAX_SEC }}s
      </p>
      <p v-else-if="state === 'done'" class="text-celadon">已录制 {{ duration }}s</p>
      <p v-else class="text-mute">待录音</p>
    </div>

    <p v-if="error" class="text-cinnabar text-sm">{{ error }}</p>

    <audio v-if="previewUrl" :src="previewUrl" controls class="w-full" />

    <div class="flex flex-wrap gap-2">
      <button
        v-if="state === 'idle'"
        type="button"
        class="inline-flex items-center gap-2 min-h-tap px-4 bg-celadon text-parchment"
        @click="start"
      >
        <Mic class="w-5 h-5" /> 开始录音
      </button>
      <button
        v-if="state === 'recording'"
        type="button"
        class="inline-flex items-center gap-2 min-h-tap px-4 bg-cinnabar text-parchment"
        @click="stop"
      >
        <Square class="w-5 h-5" /> 停止
      </button>
      <button
        v-if="state === 'done'"
        type="button"
        class="inline-flex items-center gap-2 min-h-tap px-4 border border-clay"
        @click="reset"
      >
        <RotateCcw class="w-5 h-5" /> 重录
      </button>
      <button
        v-if="state === 'done'"
        type="button"
        class="inline-flex items-center gap-2 min-h-tap px-4 bg-cinnabar text-parchment"
        @click="publish"
      >
        <Send class="w-5 h-5" /> 发布
      </button>
    </div>
  </div>
</template>
