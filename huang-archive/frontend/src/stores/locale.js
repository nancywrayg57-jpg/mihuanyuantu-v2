import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { LOCALES, localeFromAcceptLanguage, localeFromCountry, t as translate } from '../lib/i18n'

const STORAGE_KEY = 'hz_locale_override_v1'

export const useLocaleStore = defineStore('locale', () => {
  const override = ref(localStorage.getItem(STORAGE_KEY) || '')
  const suggested = ref('zh')
  const ready = ref(false)

  const locale = computed(() => {
    if (override.value && LOCALES.some((l) => l.code === override.value)) return override.value
    return suggested.value || 'zh'
  })

  const localeMeta = computed(() => LOCALES.find((l) => l.code === locale.value) || LOCALES[0])

  function t(key, vars) {
    return translate(locale.value, key, vars)
  }

  function setOverride(code) {
    if (!LOCALES.some((l) => l.code === code)) return
    override.value = code
    localStorage.setItem(STORAGE_KEY, code)
  }

  function clearOverride() {
    override.value = ''
    localStorage.removeItem(STORAGE_KEY)
  }

  async function initFromIp() {
    try {
      // Prefer server suggestion (CF-IPCountry / Accept-Language); fallback client IP API.
      const r = await fetch('/api/hz/locale-suggest', { credentials: 'omit' })
      if (r.ok) {
        const data = await r.json()
        if (data?.locale && LOCALES.some((l) => l.code === data.locale)) {
          suggested.value = data.locale
          ready.value = true
          return
        }
        if (data?.country) {
          suggested.value = localeFromCountry(data.country)
          ready.value = true
          return
        }
      }
    } catch (_) {}

    try {
      const r = await fetch('https://ipapi.co/json/', { signal: AbortSignal.timeout(4000) })
      if (r.ok) {
        const data = await r.json()
        suggested.value = localeFromCountry(data?.country_code)
        ready.value = true
        return
      }
    } catch (_) {}

    suggested.value = localeFromAcceptLanguage(navigator.language || '')
    ready.value = true
  }

  return {
    LOCALES,
    override,
    suggested,
    ready,
    locale,
    localeMeta,
    t,
    setOverride,
    clearOverride,
    initFromIp,
  }
})
