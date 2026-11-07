import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const KEY = 'hz_a11y_v1'

export const useA11yStore = defineStore('a11y', () => {
  const fontScale = ref(1) // 1 | 1.15 | 1.3
  const largeTap = ref(false)

  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || '{}')
    if (saved.fontScale) fontScale.value = saved.fontScale
    if (saved.largeTap) largeTap.value = !!saved.largeTap
  } catch (_) {}

  function persist() {
    localStorage.setItem(
      KEY,
      JSON.stringify({ fontScale: fontScale.value, largeTap: largeTap.value }),
    )
    apply()
  }

  function apply() {
    if (typeof document === 'undefined') return
    document.documentElement.style.setProperty('--hz-font-scale', String(fontScale.value))
    document.documentElement.classList.toggle('hz-large-tap', largeTap.value)
  }

  watch([fontScale, largeTap], persist, { immediate: true })

  function cycleFont() {
    const steps = [1, 1.15, 1.3]
    const i = steps.indexOf(fontScale.value)
    fontScale.value = steps[(i + 1) % steps.length]
  }

  return { fontScale, largeTap, cycleFont, apply }
})
