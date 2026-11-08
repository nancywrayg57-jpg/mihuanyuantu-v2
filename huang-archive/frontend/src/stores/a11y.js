import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

/** v2: default large type for elderly-friendly logged-in UI */
const KEY = 'hz_a11y_v2'

/** ~120% base (within 112–125%); cycle still allows standard / larger */
export const FONT_STEPS = [1, 1.2, 1.3]
export const DEFAULT_FONT_SCALE = 1.2

export const useA11yStore = defineStore('a11y', () => {
  const fontScale = ref(DEFAULT_FONT_SCALE)
  const largeTap = ref(false)

  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || '{}')
    if (typeof saved.fontScale === 'number' && FONT_STEPS.includes(saved.fontScale)) {
      fontScale.value = saved.fontScale
    }
    if (saved.largeTap) largeTap.value = !!saved.largeTap
  } catch (_) {}

  function persist() {
    localStorage.setItem(
      KEY,
      JSON.stringify({ fontScale: fontScale.value, largeTap: largeTap.value }),
    )
  }

  /** Apply type scale for logged-in chrome; login page stays at 1. */
  function apply(opts = {}) {
    if (typeof document === 'undefined') return
    const forLoggedIn = opts.loggedIn !== false
    const scale = forLoggedIn ? fontScale.value : 1
    document.documentElement.style.setProperty('--hz-font-scale', String(scale))
    document.documentElement.classList.toggle('hz-large-tap', forLoggedIn && largeTap.value)
    document.documentElement.classList.toggle('hz-logged-in-type', forLoggedIn)
  }

  watch([fontScale, largeTap], () => {
    persist()
    apply({ loggedIn: document.documentElement.classList.contains('hz-logged-in-type') })
  })

  function cycleFont() {
    const i = FONT_STEPS.indexOf(fontScale.value)
    fontScale.value = FONT_STEPS[(i + 1) % FONT_STEPS.length]
  }

  return { fontScale, largeTap, cycleFont, apply, FONT_STEPS, DEFAULT_FONT_SCALE }
})
