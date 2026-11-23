import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useMiniPlayerStore = defineStore('miniPlayer', () => {
  const archiveId = ref('')
  const title = ref('')
  const url = ref('')
  const floating = ref(false)
  /** @type {import('vue').Ref<HTMLVideoElement|null>} */
  const sourceEl = ref(null)
  const currentTime = ref(0)
  const wasPlaying = ref(false)

  function attach({ archiveId: id, title: t, url: u, videoEl }) {
    archiveId.value = id || ''
    title.value = t || '家族影像'
    url.value = u || ''
    sourceEl.value = videoEl || null
  }

  function detach(id) {
    if (id && archiveId.value && id !== archiveId.value) return
    if (floating.value) return
    archiveId.value = ''
    title.value = ''
    url.value = ''
    sourceEl.value = null
    wasPlaying.value = false
  }

  function openFloating() {
    if (!url.value) return
    if (sourceEl.value) {
      currentTime.value = sourceEl.value.currentTime || 0
      wasPlaying.value = !sourceEl.value.paused
      try {
        sourceEl.value.pause()
      } catch (_) {}
    }
    floating.value = true
  }

  function closeFloating() {
    floating.value = false
  }

  function clear() {
    floating.value = false
    archiveId.value = ''
    title.value = ''
    url.value = ''
    sourceEl.value = null
  }

  return {
    archiveId,
    title,
    url,
    floating,
    sourceEl,
    currentTime,
    wasPlaying,
    attach,
    detach,
    openFloating,
    closeFloating,
    clear,
  }
})
