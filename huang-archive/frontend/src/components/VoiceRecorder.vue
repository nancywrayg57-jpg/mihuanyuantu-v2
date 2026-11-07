<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { Mic, Square, RotateCcw, Send, Pause, Play } from 'lucide-vue-next'
import { formatDuration } from '../lib/mediaPrepare'

const emit = defineEmits(['publish'])

const state = ref('idle') // idle | recording | paused | done
const error = ref('')
const duration = ref(0)
const previewUrl = ref('')
const blobRef = ref(null)
const level = ref(0)

let mediaRecorder = null
let stream = null
let chunks = []
let timer = null
let audioCtx = null
let analyser = null
let raf = 0
const MAX_SEC = 180

const MIME_CANDIDATES = [
  'audio/mp4',
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg',
]

const timeLabel = computed(() => formatDuration(duration.value))

function pickMime() {
  if (typeof MediaRecorder === 'undefined') return ''
  for (const m of MIME_CANDIDATES) {
    if (MediaRecorder.isTypeSupported(m)) return m
  }
  return ''
}

function monitorLevel() {
  if (!analyser) return
  const data = new Uint8Array(analyser.frequencyBinCount)
  const tick = () => {
    analyser.getByteFrequencyData(data)
    let sum = 0
    for (let i = 0; i < data.length; i++) sum += data[i]
    level.value = Math.min(100, Math.round((sum / data.length / 255) * 140))
    raf = requestAnimationFrame(tick)
  }
  raf = requestAnimationFrame(tick)
}

async function start() {
  error.value = ''
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)()
      const src = audioCtx.createMediaStreamSource(stream)
      analyser = audioCtx.createAnalyser()
      analyser.fftSize = 256
      src.connect(analyser)
      monitorLevel()
    } catch (_) {}

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
      if (state.value !== 'recording') return
      duration.value += 1
      if (duration.value >= MAX_SEC) stop()
    }, 1000)
  } catch (e) {
    error.value = '无法启动麦克风，请确认已授权并使用 HTTPS；微信内请用系统浏览器打开'
    cleanupStream()
  }
}

function pause() {
  if (!mediaRecorder || mediaRecorder.state !== 'recording') return
  try {
    mediaRecorder.pause()
    state.value = 'paused'
  } catch {
    error.value = '当前浏览器不支持暂停录音'
  }
}

function resume() {
  if (!mediaRecorder || mediaRecorder.state !== 'paused') return
  try {
    mediaRecorder.resume()
    state.value = 'recording'
  } catch {
    error.value = '恢复录音失败'
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
  level.value = 0
  state.value = 'idle'
  error.value = ''
}

function publish() {
  if (!blobRef.value) return
  emit('publish', { blob: blobRef.value, duration: duration.value })
  reset()
}

function cleanupStream() {
  if (raf) cancelAnimationFrame(raf)
  raf = 0
  if (audioCtx) {
    try { audioCtx.close() } catch (_) {}
    audioCtx = null
    analyser = null
  }
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
  <div class="border border-clay bg-rice p-4 space-y-3" data-testid="voice-recorder">
    <div class="flex items-center justify-between gap-2">
      <p class="text-mute">语音追忆（最长 {{ MAX_SEC }} 秒）</p>
      <p v-if="state === 'recording'" class="text-cinnabar recording-dot" data-testid="voice-recording">
        录音中 {{ timeLabel }}
      </p>
      <p v-else-if="state === 'paused'" class="text-mute">已暂停 {{ timeLabel }}</p>
      <p v-else-if="state === 'done'" class="text-celadon">已录制 {{ timeLabel }}</p>
      <p v-else class="text-mute">待录音</p>
    </div>

    <div
      v-if="state === 'recording' || state === 'paused'"
      class="h-2 bg-clay overflow-hidden"
      data-testid="voice-level"
      aria-hidden="true"
    >
      <div class="h-full bg-cinnabar transition-all" :style="{ width: level + '%' }" />
    </div>

    <p v-if="error" class="text-cinnabar text-sm">{{ error }}</p>

    <audio v-if="previewUrl" :src="previewUrl" controls class="w-full" data-testid="voice-preview" />

    <div class="flex flex-wrap gap-2">
      <button
        v-if="state === 'idle'"
        type="button"
        class="inline-flex items-center gap-2 min-h-tap px-4 bg-celadon text-parchment"
        data-testid="voice-start"
        @click="start"
      >
        <Mic class="w-5 h-5" /> 开始录音
      </button>
      <button
        v-if="state === 'recording'"
        type="button"
        class="inline-flex items-center gap-2 min-h-tap px-4 border border-clay"
        data-testid="voice-pause"
        @click="pause"
      >
        <Pause class="w-5 h-5" /> 暂停
      </button>
      <button
        v-if="state === 'paused'"
        type="button"
        class="inline-flex items-center gap-2 min-h-tap px-4 border border-clay"
        data-testid="voice-resume"
        @click="resume"
      >
        <Play class="w-5 h-5" /> 继续
      </button>
      <button
        v-if="state === 'recording' || state === 'paused'"
        type="button"
        class="inline-flex items-center gap-2 min-h-tap px-4 bg-cinnabar text-parchment"
        data-testid="voice-stop"
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
        data-testid="voice-publish"
        @click="publish"
      >
        <Send class="w-5 h-5" /> 发布
      </button>
    </div>
  </div>
</template>
