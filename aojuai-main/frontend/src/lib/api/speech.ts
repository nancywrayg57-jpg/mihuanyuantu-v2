import { apiFetch, apiFetchBlob } from '@/lib/api'
import type { Session } from '@/lib/auth'

type ApiOpts = {
  session?: Session | null
  tenantId?: number | null
}

export type SpeechFieldType =
  | 'string'
  | 'secret'
  | 'number'
  | 'boolean'
  | 'select'
  | 'multiselect'
  | 'json'
  | 'textarea'

export type SpeechProviderFieldOption = {
  value: string
  label: string
  description?: string | null
}

export type SpeechProviderFieldSchema = {
  key: string
  label: string
  type: SpeechFieldType
  required?: boolean
  description?: string | null
  placeholder?: string | null
  default?: unknown
  options?: SpeechProviderFieldOption[]
  ui?: Record<string, unknown> | null
}

export type SpeechProviderCapabilities = {
  supportsVoicesList?: boolean
  supportsTtsStreamAudio?: boolean
  supportsTtsStreamText?: boolean
  supportsAsrStream?: boolean
  supportsCancel?: boolean
  supportsVoiceClone?: boolean
}

export type SpeechProviderDescriptor = {
  id: string
  category: 'tts' | 'stt'
  name: string
  description?: string | null
  capabilities?: SpeechProviderCapabilities
  fields: SpeechProviderFieldSchema[]
}

export type SpeechProviderSelection = {
  providerId: string
  settings: Record<string, unknown>
}

export type SpeechProviderProfileView = {
  id: string
  label: string
  providerId: string
  settings: Record<string, unknown>
  isDefault?: boolean
  allowVoiceClone?: boolean
  secretsSet?: Record<string, boolean>
}

export type SpeechTenantConfigView = {
  enabled?: boolean
  status?: string
  tts?: SpeechProviderSelection | null
  ttsProfiles?: SpeechProviderProfileView[]
  defaultTtsProfileId?: string | null
  stt?: SpeechProviderSelection | null
  asr?: SpeechProviderSelection | null
  bargeIn?: {
    enabled?: boolean
    mode?: 'vad_onset' | 'asr_text' | 'stop_words' | 'client_abort'
    stopWords?: string[]
    wakeWords?: string[]
  } | null
  secretsSet?: Record<string, unknown>
}

export type SpeechSttDemoResponse = {
  text: string
  providerId: string
  model?: string | null
  language?: string | null
}

export type SpeechVoiceCloneSupport = {
  enabled: boolean
  providerId?: string | null
  enrollmentModel?: string | null
  synthesisModel?: string | null
  maxUploadBytes: number
  maxDurationSeconds: number
  allowedContentTypes: string[]
  note?: string | null
}

export type SpeechVoiceCloneAsset = {
  id: number
  displayName: string
  sourceFileName: string
  sourceContentType: string
  sourceFileSizeBytes: number
  sourceDurationMs: number
  transcriptText?: string | null
  languageType?: string | null
  status: string
  lastError?: string | null
  createdAt: string
  updatedAt?: string | null
  createdByUserId: number
  sourceStreamUrl: string
}

export type SpeechVoiceClone = {
  id: number
  assetId: number
  displayName: string
  providerId: string
  enrollmentModel: string
  synthesisModel: string
  remoteVoiceId: string
  languageType?: string | null
  status: string
  errorMessage?: string | null
  createdAt: string
  updatedAt?: string | null
  createdByUserId: number
}

export type SpeechVoiceCloneWorkspaceItem = {
  asset: SpeechVoiceCloneAsset
  clone?: SpeechVoiceClone | null
}

export type SpeechVoiceCloneWorkspacePayload = {
  support: SpeechVoiceCloneSupport
  items: SpeechVoiceCloneWorkspaceItem[]
}

export async function listSpeechProviders(opts: ApiOpts = {}) {
  return apiFetch<{ tts?: SpeechProviderDescriptor[]; stt?: SpeechProviderDescriptor[] }>(
    '/api/v1/speech/providers',
    { ...opts, cache: 'no-store' },
  )
}

export async function getSpeechConfig(opts: ApiOpts = {}) {
  return apiFetch<SpeechTenantConfigView>('/api/v1/speech/config', { ...opts, cache: 'no-store' })
}

export async function upsertSpeechConfig(
  payload: {
    enabled?: boolean
    status?: string
    tts?: {
      providerId?: string | null
      settings?: Record<string, unknown>
      secrets?: Record<string, unknown>
    } | null
    ttsProfiles?: Array<{
      id?: string | null
      label?: string | null
      providerId?: string | null
      settings?: Record<string, unknown>
      secrets?: Record<string, unknown>
      isDefault?: boolean
      allowVoiceClone?: boolean
    }>
    defaultTtsProfileId?: string | null
    stt?: {
      providerId?: string | null
      settings?: Record<string, unknown>
      secrets?: Record<string, unknown>
    } | null
    bargeIn?: {
      enabled?: boolean
      mode?: 'vad_onset' | 'asr_text' | 'stop_words' | 'client_abort'
      stopWords?: string[]
      wakeWords?: string[]
    } | null
  },
  opts: ApiOpts = {},
) {
  return apiFetch<SpeechTenantConfigView>('/api/v1/speech/config', {
    ...opts,
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function demoSpeechTts(
  payload: {
    text: string
    providerId?: string | null
    settings?: Record<string, unknown>
    secrets?: Record<string, unknown>
    outputFormat?: string | null
  },
  opts: ApiOpts = {},
) {
  return apiFetchBlob('/api/v1/speech/demo/tts', {
    ...opts,
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function demoSpeechStt(
  payload: {
    file: File
    providerId?: string | null
    language?: string | null
    settings?: Record<string, unknown>
    secrets?: Record<string, unknown>
  },
  opts: ApiOpts = {},
) {
  const body = new FormData()
  body.append('file', payload.file)
  if (payload.providerId) body.append('providerId', payload.providerId)
  if (payload.language) body.append('language', payload.language)
  if (payload.settings) body.append('settings', JSON.stringify(payload.settings))
  if (payload.secrets) body.append('secrets', JSON.stringify(payload.secrets))

  return apiFetch<SpeechSttDemoResponse>('/api/v1/speech/demo/stt', {
    ...opts,
    method: 'POST',
    body,
  })
}

export async function listSpeechVoiceCloneWorkspace(opts: ApiOpts = {}) {
  return apiFetch<SpeechVoiceCloneWorkspacePayload>('/api/v1/speech/voice-clones/workspace', opts)
}

export async function createSpeechVoiceClone(
  payload: {
    file: File
    displayName?: string | null
    transcriptText?: string | null
    languageType?: string | null
    sourceDurationMs?: number | null
  },
  opts: ApiOpts = {},
) {
  const body = new FormData()
  body.append('file', payload.file)
  if (payload.displayName) body.append('displayName', payload.displayName)
  if (payload.transcriptText) body.append('transcriptText', payload.transcriptText)
  if (payload.languageType) body.append('languageType', payload.languageType)
  if (payload.sourceDurationMs && payload.sourceDurationMs > 0) {
    body.append('sourceDurationMs', String(payload.sourceDurationMs))
  }

  return apiFetch<SpeechVoiceCloneWorkspaceItem>('/api/v1/speech/voice-clones', {
    ...opts,
    method: 'POST',
    body,
  })
}

export async function previewSpeechVoiceClone(
  cloneId: number,
  payload: {
    text: string
  },
  opts: ApiOpts = {},
) {
  return apiFetchBlob(`/api/v1/speech/voice-clones/${cloneId}/preview-tts`, {
    ...opts,
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchSpeechVoiceCloneAssetSource(assetId: number, opts: ApiOpts = {}) {
  return apiFetchBlob(`/api/v1/speech/voice-clones/assets/${assetId}/source`, opts)
}

export async function deleteSpeechVoiceClone(cloneId: number, opts: ApiOpts = {}) {
  return apiFetch<{ id: number }>(`/api/v1/speech/voice-clones/${cloneId}`, {
    ...opts,
    method: 'DELETE',
  })
}
