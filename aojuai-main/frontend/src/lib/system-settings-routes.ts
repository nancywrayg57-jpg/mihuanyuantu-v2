export type RouteSearchParams = Record<string, string | string[] | undefined>

export type SpeechSettingsPanel = 'tts' | 'stt' | 'barge-in'

function appendParam(params: URLSearchParams, key: string, value: string | string[] | undefined) {
  if (typeof value === 'string') {
    if (value) params.append(key, value)
    return
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      if (item) params.append(key, item)
    }
  }
}

function buildPathWithSearch(
  basePath: string,
  searchParams?: RouteSearchParams,
  overrides?: Record<string, string | null | undefined>,
) {
  const params = new URLSearchParams()

  for (const [key, value] of Object.entries(searchParams || {})) {
    appendParam(params, key, value)
  }

  for (const [key, value] of Object.entries(overrides || {})) {
    params.delete(key)
    if (value) params.set(key, value)
  }

  const query = params.toString()
  return query ? `${basePath}?${query}` : basePath
}

export function normalizeSpeechSettingsPanel(value: string | string[] | null | undefined): SpeechSettingsPanel {
  const normalized = Array.isArray(value) ? String(value[0] || '').trim().toLowerCase() : String(value || '').trim().toLowerCase()
  if (normalized === 'stt') return 'stt'
  if (normalized === 'barge-in' || normalized === 'barge_in' || normalized === 'bargein' || normalized === 'demo' || normalized === 'lab') {
    return 'barge-in'
  }
  return 'tts'
}

export function resolveSpeechSettingsPanelFromPath(pathname: string | null | undefined): SpeechSettingsPanel {
  const normalized = String(pathname || '').trim().toLowerCase()
  if (
    normalized.includes('/barge-in') ||
    normalized.includes('/barge_in') ||
    normalized.includes('/bargein') ||
    normalized.includes('/demo')
  ) {
    return 'barge-in'
  }
  if (normalized.includes('/stt')) return 'stt'
  return 'tts'
}

export function resolveSpeechSettingsPanelFromSlug(slug: string[] | null | undefined): SpeechSettingsPanel {
  const joined = Array.isArray(slug) ? slug.join('/') : ''
  return resolveSpeechSettingsPanelFromPath(joined)
}

export function buildTenantSpeechSettingsHref(
  panel?: string | string[] | null,
  searchParams?: RouteSearchParams,
) {
  const normalizedPanel = normalizeSpeechSettingsPanel(panel)
  return buildPathWithSearch('/system/tenant-settings', searchParams, {
    tab: 'speech',
    panel: normalizedPanel === 'tts' ? null : normalizedPanel,
  })
}
