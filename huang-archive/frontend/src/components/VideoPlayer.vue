<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Download, PictureInPicture2, Minimize2 } from 'lucide-vue-next'
import pb from '../lib/pb'
import { isWeChat, resolvePlayUrl } from '../lib/videoPlayback'
import { useMiniPlayerStore } from '../stores/miniPlayer'

const props = defineProps({
  archive: { type: Object, required: true },
})

const mini = useMiniPlayerStore()
const videoEl = ref(null)
const err = ref('')
const wechat = isWeChat()

const resolved = computed(() => resolvePlayUrl(pb, props.archive))
const playUrl = computed(() => resolved.value.url)
const originalUrl = computed(() => resolved.value.original)
const mode = computed(() => resolved.value.mode)
const note = computed(() => resolved.value.note)

function bindMediaSession() {
  if (!('mediaSession' in navigator)) return
  try {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: props.archive.title || '家族影像',
      artist: props.archive.uploader_name || '黄志松人生纪念馆',
      album: '家族记忆',
    })
    navigator.mediaSession.setActionHandler('play', () => videoEl.value?.play())
    navigator.mediaSession.setActionHandler('pause', () => videoEl.value?.pause())
  } catch (_) {}
}

function onPlay() {
  err.value = ''
  bindMediaSession()
  mini.attach({
    archiveId: props.archive.id,
    title: props.archive.title,
    url: playUrl.value,
    videoEl: videoEl.value,
  })
}

function onError() {
  err.value = note.value || '当前浏览器无法播放此视频，请下载后用系统播放器打开'
}

async function enterPiP() {
  const el = videoEl.value
  if (!el) return
  try {
    if (document.pictureInPictureElement) {
      await document.exitPictureInPicture()
      return
    }
    if (el.requestPictureInPicture) {
      await el.requestPictureInPicture()
    } else {
      mini.openFloating()
    }
  } catch (_) {
    mini.openFloating()
  }
}

function openMini() {
  if (videoEl.value && playUrl.value) {
    mini.attach({
      archiveId: props.archive.id,
      title: props.archive.title,
      url: playUrl.value,
      videoEl: videoEl.value,
    })
    mini.openFloating()
  }
}

watch(playUrl, () => {
  err.value = ''
})

onMounted(() => {
  const el = videoEl.value
  if (!el) return
  el.setAttribute('playsinline', 'true')
  el.setAttribute('webkit-playsinline', 'true')
  el.setAttribute('x5-playsinline', 'true')
  el.setAttribute('x5-video-player-type', 'h5')
  el.setAttribute('x5-video-player-fullscreen', 'true')
})

onBeforeUnmount(() => {
  if (mini.archiveId === props.archive.id && !mini.floating) {
    mini.detach(props.archive.id)
  }
})
</script>

<template>
  <div class="relative w-full h-full bg-ink/90 text-parchment">
    <video
      v-if="playUrl"
      ref="videoEl"
      :src="playUrl"
      class="w-full h-full object-contain bg-black"
      controls
      playsinline
      preload="metadata"
      controlslist="nodownload"
      data-testid="archive-video"
      @play="onPlay"
      @error="onError"
    />
    <div
      v-else
      class="absolute inset-0 flex flex-col items-center justify-center gap-3 p-4 text-center"
      data-testid="video-fallback"
    >
      <p class="font-song text-lg">
        {{ mode === 'pending' ? '视频转码中…' : '暂无法在线播放' }}
      </p>
      <p class="text-sm opacity-80">{{ note || '请稍候刷新，或下载原文件用系统播放器打开' }}</p>
      <a
        v-if="originalUrl"
        :href="originalUrl"
        download
        class="inline-flex items-center gap-2 min-h-tap px-4 border border-parchment/40"
        data-testid="video-download"
      >
        <Download class="w-5 h-5" /> 下载原视频
      </a>
    </div>

    <div
      v-if="playUrl"
      class="absolute top-2 right-2 flex gap-2"
    >
      <button
        type="button"
        class="min-h-[40px] min-w-[40px] grid place-items-center bg-ink/55 border border-parchment/30"
        title="画中画"
        data-testid="video-pip"
        @click="enterPiP"
      >
        <PictureInPicture2 class="w-5 h-5" />
      </button>
      <button
        type="button"
        class="min-h-[40px] min-w-[40px] grid place-items-center bg-ink/55 border border-parchment/30"
        title="小窗播放"
        data-testid="video-mini"
        @click="openMini"
      >
        <Minimize2 class="w-5 h-5" />
      </button>
    </div>

    <p
      v-if="wechat"
      class="absolute bottom-10 left-0 right-0 text-center text-xs px-3 opacity-80 pointer-events-none"
      data-testid="wechat-hint"
    >
      微信内建议竖屏播放；若黑屏请点右上角用浏览器打开，或下载后播放
    </p>
    <p v-if="err" class="absolute bottom-2 left-2 right-2 text-sm text-cinnabar bg-parchment/95 text-ink p-2">
      {{ err }}
      <a v-if="originalUrl" :href="originalUrl" download class="underline ml-2">下载原文件</a>
    </p>
  </div>
</template>
