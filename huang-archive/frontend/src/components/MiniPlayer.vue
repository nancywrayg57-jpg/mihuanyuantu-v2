<script setup>
import { nextTick, ref, watch } from 'vue'
import { X, PictureInPicture2 } from 'lucide-vue-next'
import { useMiniPlayerStore } from '../stores/miniPlayer'

const mini = useMiniPlayerStore()
const el = ref(null)

watch(
  () => mini.floating,
  async (v) => {
    if (!v) return
    await nextTick()
    if (!el.value) return
    el.value.currentTime = mini.currentTime || 0
    if (mini.wasPlaying) {
      el.value.play().catch(() => {})
    }
  },
)

async function pip() {
  if (!el.value?.requestPictureInPicture) return
  try {
    await el.value.requestPictureInPicture()
  } catch (_) {}
}

function close() {
  if (el.value) {
    try {
      el.value.pause()
    } catch (_) {}
  }
  mini.closeFloating()
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="mini.floating && mini.url"
      class="fixed z-[70] right-3 bottom-3 w-[220px] sm:w-[280px] bg-ink border border-clay shadow-lg overflow-hidden"
      data-testid="mini-player"
    >
      <div class="flex items-center justify-between gap-2 px-2 py-1 text-parchment text-sm">
        <span class="truncate font-song">{{ mini.title }}</span>
        <div class="flex gap-1 shrink-0">
          <button type="button" class="p-1" title="画中画" @click="pip">
            <PictureInPicture2 class="w-4 h-4" />
          </button>
          <button type="button" class="p-1" title="关闭小窗" @click="close">
            <X class="w-4 h-4" />
          </button>
        </div>
      </div>
      <video
        ref="el"
        :src="mini.url"
        class="w-full aspect-video bg-black"
        controls
        playsinline
        preload="metadata"
      />
    </div>
  </Teleport>
</template>
