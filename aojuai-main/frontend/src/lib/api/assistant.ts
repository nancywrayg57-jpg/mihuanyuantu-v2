import { apiFetch } from '@/lib/api'
import {
  clearSession,
  createBearerSession,
  createCookieBackedSession,
  emitAuthEvent,
  getSessionAccessBearer,
  getSessionRefreshToken,
  isCookieBackedSession,
  isTokenExpired,
  loadSession,
  saveSession,
  type Session,
} from '@/lib/auth'
import { translateActive } from '@/lib/i18n/registry'

type ApiOpts = { session?: Session | null; tenantId?: number | null }
type AnyRecord = Record<string, unknown>

function toRecord(value: unknown): AnyRecord {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  return value as AnyRecord
}

function read<T = unknown>(obj: AnyRecord, camelKey: string, snakeKey?: string): T | undefined {
  const snake = snakeKey || camelKey.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
  return (obj[camelKey] ?? obj[snake]) as T | undefined
}

function toStringValue(value: unknown, fallback = ''): string {
  if (typeof value === 'string') return value
  if (value == null) return fallback
  return String(value)
}

function toNumberValue(value: unknown, fallback = 0): number {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

function toBooleanValue(value: unknown, fallback = false): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') {
    const lowered = value.toLowerCase()
    if (lowered === 'true') return true
    if (lowered === 'false') return false
  }
  return fallback
}

export type AssistantPreset = {
  id: string
  label: string
  prompt: string
  icon?: string | null
}

export type AssistantContextResult = {
  moduleCode: string
  moduleName: string
  routePath: string
  data: Record<string, unknown>
}

export type AssistantPresetsResult = {
  moduleCode: string
  moduleName: string
  routePath: string
  presets: AssistantPreset[]
}

export type AssistantSessionResult = {
  id: number
  moduleCode: string
  moduleName: string
  routePath: string
  contextData: Record<string, unknown>
  createdAt: string
}

export type AssistantSessionMessageResult = {
  id: number
  role: string
  content: string
  actionType: string | null
  actionResult: Record<string, unknown> | null
  createdAt: string
  action: AssistantAction | null
}

export type AssistantChatResult = {
  sessionId: number
  moduleCode: string
  moduleName: string
  routePath: string
  reply: string
  usedAi: boolean
  context: Record<string, unknown>
  suggestions: string[]
  action: AssistantAction | null
}

export type AssistantActionField = {
  key: string
  label: string
  required: boolean
  description: string
  examples: string[]
}

export type AssistantAction = {
  version: number
  toolId: string
  toolLabel?: string | null
  skillId?: string | null
  skillLabel?: string | null
  mode: string
  summary: string
  targetRoutePath?: string | null
  targetModuleCode?: string | null
  targetContextParams?: Record<string, unknown>
  confirmationRequired: boolean
  canExecute: boolean
  autoExecute?: boolean | null
  confirmText: string
  reason?: string | null
  nextQuestion?: string | null
  suggestedReplies: string[]
  collectedParams: Record<string, unknown>
  missingFields: AssistantActionField[]
}

export type AssistantActionResult = {
  success: boolean
  actionType: string
  result: Record<string, unknown> | null
  message: string | null
}

export type AssistantStreamChunk = {
  type: 'content' | 'error' | 'done'
  content?: string
  reply?: string
  usedAi?: boolean
  context?: Record<string, unknown>
  suggestions?: string[]
  action?: AssistantAction | null
  moduleCode?: string
  moduleName?: string
  routePath?: string
}

function normalizePreset(raw: unknown): AssistantPreset {
  const obj = toRecord(raw)
  return {
    id: toStringValue(read(obj, 'id')),
    label: toStringValue(read(obj, 'label')),
    prompt: toStringValue(read(obj, 'prompt')),
    icon: toStringValue(read(obj, 'icon')) || null,
  }
}

function normalizeContextResult(raw: unknown): AssistantContextResult {
  const obj = toRecord(raw)
  return {
    moduleCode: toStringValue(read(obj, 'moduleCode', 'module_code')),
    moduleName: toStringValue(read(obj, 'moduleName', 'module_name')),
    routePath: toStringValue(read(obj, 'routePath', 'route_path')),
    data: toRecord(read(obj, 'data')),
  }
}

function normalizePresetsResult(raw: unknown): AssistantPresetsResult {
  const obj = toRecord(raw)
  const presetsRaw = read(obj, 'presets')
  return {
    moduleCode: toStringValue(read(obj, 'moduleCode', 'module_code')),
    moduleName: toStringValue(read(obj, 'moduleName', 'module_name')),
    routePath: toStringValue(read(obj, 'routePath', 'route_path')),
    presets: Array.isArray(presetsRaw) ? presetsRaw.map(normalizePreset) : [],
  }
}

function normalizeSession(raw: unknown): AssistantSessionResult {
  const obj = toRecord(raw)
  return {
    id: toNumberValue(read(obj, 'id')),
    moduleCode: toStringValue(read(obj, 'moduleCode', 'module_code')),
    moduleName: toStringValue(read(obj, 'moduleName', 'module_name')) || translateActive('system.assistant.unifiedAssistant'),
    routePath: toStringValue(read(obj, 'routePath', 'route_path')),
    contextData: toRecord(read(obj, 'contextData', 'context_data')),
    createdAt: toStringValue(read(obj, 'createdAt', 'created_at')),
  }
}

function normalizeSessionMessage(raw: unknown): AssistantSessionMessageResult {
  const obj = toRecord(raw)
  const actionResult = toRecord(read(obj, 'actionResult', 'action_result'))
  return {
    id: toNumberValue(read(obj, 'id')),
    role: toStringValue(read(obj, 'role')),
    content: toStringValue(read(obj, 'content')),
    actionType: toStringValue(read(obj, 'actionType', 'action_type')) || null,
    actionResult: Object.keys(actionResult).length > 0 ? actionResult : null,
    createdAt: toStringValue(read(obj, 'createdAt', 'created_at')),
    action: normalizeAssistantAction(read(actionResult, 'assistantAction', 'assistant_action')),
  }
}

function normalizeChatResult(raw: unknown): AssistantChatResult {
  const obj = toRecord(raw)
  const suggestionsRaw = read(obj, 'suggestions')
  return {
    sessionId: toNumberValue(read(obj, 'sessionId', 'session_id')),
    moduleCode: toStringValue(read(obj, 'moduleCode', 'module_code')),
    moduleName: toStringValue(read(obj, 'moduleName', 'module_name')) || translateActive('system.assistant.unifiedAssistant'),
    routePath: toStringValue(read(obj, 'routePath', 'route_path')),
    reply: toStringValue(read(obj, 'reply')),
    usedAi: toBooleanValue(read(obj, 'usedAi', 'used_ai')),
    context: toRecord(read(obj, 'context')),
    suggestions: Array.isArray(suggestionsRaw) ? suggestionsRaw.map((item) => toStringValue(item)).filter(Boolean) : [],
    action: normalizeAssistantAction(read(obj, 'action')),
  }
}

function normalizeAssistantActionField(raw: unknown): AssistantActionField | null {
  const obj = toRecord(raw)
  const key = toStringValue(read(obj, 'key'))
  if (!key) return null
  const examplesRaw = read(obj, 'examples')
  return {
    key,
    label: toStringValue(read(obj, 'label')) || key,
    required: toBooleanValue(read(obj, 'required')),
    description: toStringValue(read(obj, 'description')),
    examples: Array.isArray(examplesRaw) ? examplesRaw.map((item) => toStringValue(item)).filter(Boolean) : [],
  }
}

function normalizeAssistantAction(raw: unknown): AssistantAction | null {
  const obj = toRecord(raw)
  const toolId = toStringValue(read(obj, 'toolId', 'tool_id'))
  if (!toolId) return null
  const collectedParams = toRecord(
    read(obj, 'collectedParams', 'collected_params') ??
      read(obj, 'params') ??
      read(obj, 'args') ??
      read(obj, 'parameters'),
  )
  const missingRaw = read(obj, 'missingFields', 'missing_fields')
  const suggestedRepliesRaw = read(obj, 'suggestedReplies', 'suggested_replies')
  const targetContextParams = toRecord(
    read(obj, 'targetContextParams', 'target_context_params') ??
      read(collectedParams, 'targetContextParams', 'target_context_params'),
  )
  const targetRoutePath =
    toStringValue(read(obj, 'targetRoutePath', 'target_route_path')) ||
    toStringValue(read(collectedParams, 'targetRoutePath', 'target_route_path')) ||
    toStringValue(read(collectedParams, 'routePath', 'route_path')) ||
    toStringValue(read(collectedParams, 'path')) ||
    null
  const targetModuleCode =
    toStringValue(read(obj, 'targetModuleCode', 'target_module_code')) ||
    toStringValue(read(collectedParams, 'targetModuleCode', 'target_module_code')) ||
    toStringValue(read(collectedParams, 'moduleCode', 'module_code')) ||
    null
  return {
    version: toNumberValue(read(obj, 'version'), 1),
    toolId,
    toolLabel: toStringValue(read(obj, 'toolLabel', 'tool_label')) || null,
    skillId: toStringValue(read(obj, 'skillId', 'skill_id')) || null,
    skillLabel: toStringValue(read(obj, 'skillLabel', 'skill_label')) || null,
    mode: toStringValue(read(obj, 'mode')) || 'collect',
    summary: toStringValue(read(obj, 'summary')),
    targetRoutePath,
    targetModuleCode,
    targetContextParams,
    confirmationRequired: toBooleanValue(read(obj, 'confirmationRequired', 'confirmation_required')),
    canExecute: toBooleanValue(read(obj, 'canExecute', 'can_execute')),
    autoExecute: toBooleanValue(read(obj, 'autoExecute', 'auto_execute')),
    confirmText:
      toStringValue(read(obj, 'confirmText', 'confirm_text')) ||
      (toolId === 'page.router.navigate'
        ? translateActive('system.assistant.goToPage')
        : translateActive('system.assistant.confirmExecute')),
    reason: toStringValue(read(obj, 'reason')) || null,
    nextQuestion: toStringValue(read(obj, 'nextQuestion', 'next_question')) || null,
    suggestedReplies: Array.isArray(suggestedRepliesRaw)
      ? suggestedRepliesRaw.map((item) => toStringValue(item)).filter(Boolean)
      : [],
    collectedParams,
    missingFields: Array.isArray(missingRaw)
      ? missingRaw.map(normalizeAssistantActionField).filter((item): item is AssistantActionField => Boolean(item))
      : [],
  }
}

function normalizeAssistantActionResult(raw: unknown): AssistantActionResult {
  const obj = toRecord(raw)
  return {
    success: toBooleanValue(read(obj, 'success')),
    actionType: toStringValue(read(obj, 'actionType', 'action_type')),
    result: Object.keys(toRecord(read(obj, 'result'))).length > 0 ? toRecord(read(obj, 'result')) : null,
    message: toStringValue(read(obj, 'message')) || null,
  }
}

function getApiBaseUrl() {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL
  return typeof base === 'string' ? base.replace(/\/+$/, '') : ''
}

type RefreshTokenResponseData = {
  accessToken: string
  refreshToken: string
  mustCompleteProfile?: boolean
  expires: string
}

async function refreshSession(session: Session, apiBase: string): Promise<Session> {
  const refreshToken = getSessionRefreshToken(session)
  if (!refreshToken && !isCookieBackedSession(session)) {
    throw new Error('Missing refresh token')
  }

  const response = await fetch(`${apiBase}/api/v1/auth/refresh-token`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: refreshToken ? JSON.stringify({ refreshToken }) : undefined,
  })

  const json = (await response.json().catch(() => null)) as
    | {
        success?: boolean
        data?: RefreshTokenResponseData
        message?: string | null
      }
    | null

  if (!response.ok || !json?.success || !json?.data) {
    throw new Error(json?.message || `HTTP ${response.status}`)
  }

  const next = isCookieBackedSession(session)
    ? createCookieBackedSession({
        avatar: session.avatar,
        username: session.username,
        nickname: session.nickname,
        roles: session.roles,
        permissions: session.permissions,
        isSuperuser: session.isSuperuser,
        mustCompleteProfile: Boolean(json.data.mustCompleteProfile ?? session.mustCompleteProfile),
        expires: json.data.expires,
      })
    : createBearerSession({
        ...session,
        accessToken: json.data.accessToken,
        refreshToken: json.data.refreshToken,
        mustCompleteProfile: Boolean(json.data.mustCompleteProfile ?? session.mustCompleteProfile),
        expires: json.data.expires,
        authMode: 'bearer',
      })
  saveSession(next)
  return next
}

async function resolveValidSession(preferred?: Session | null): Promise<Session> {
  const apiBase = getApiBaseUrl()
  let session = loadSession() ?? preferred ?? null
  if (!session?.accessToken) {
    throw new Error(translateActive('system.assistant.notLoggedInOrExpired'))
  }

  if (isTokenExpired(session)) {
    session = await refreshSession(session, apiBase)
  }

  return session
}

function normalizeAssistantStreamChunk(raw: unknown): AssistantStreamChunk | null {
  const obj = toRecord(raw)
  const type = toStringValue(read(obj, 'type')).trim() as AssistantStreamChunk['type']
  if (!type || !['content', 'error', 'done'].includes(type)) return null
  const suggestionsRaw = read(obj, 'suggestions')
  return {
    type,
    content: toStringValue(read(obj, 'content')) || undefined,
    reply: toStringValue(read(obj, 'reply')) || undefined,
    usedAi: type === 'done' ? toBooleanValue(read(obj, 'usedAi', 'used_ai')) : undefined,
    context: type === 'done' ? toRecord(read(obj, 'context')) : undefined,
    suggestions: Array.isArray(suggestionsRaw) ? suggestionsRaw.map((item) => toStringValue(item)).filter(Boolean) : undefined,
    action: type === 'done' ? normalizeAssistantAction(read(obj, 'action')) : undefined,
    moduleCode: toStringValue(read(obj, 'moduleCode', 'module_code')) || undefined,
    moduleName: toStringValue(read(obj, 'moduleName', 'module_name')) || undefined,
    routePath: toStringValue(read(obj, 'routePath', 'route_path')) || undefined,
  }
}

function buildAssistantRouteQuery(route: string, contextParams?: Record<string, unknown>) {
  const search = new URLSearchParams()
  search.set('route', route)
  if (contextParams && Object.keys(contextParams).length > 0) {
    search.set('context', JSON.stringify(contextParams))
  }
  return search.toString()
}

export async function getAssistantContext(route: string, contextParams?: Record<string, unknown>, opts?: ApiOpts) {
  const query = buildAssistantRouteQuery(route, contextParams)
  const raw = await apiFetch<unknown>(`/api/v1/assistant/context?${query}`, { ...opts })
  return normalizeContextResult(raw)
}

export async function getAssistantPresets(route: string, contextParams?: Record<string, unknown>, opts?: ApiOpts) {
  const query = buildAssistantRouteQuery(route, contextParams)
  const raw = await apiFetch<unknown>(`/api/v1/assistant/presets?${query}`, { ...opts })
  return normalizePresetsResult(raw)
}

export async function createAssistantSession(
  payload: {
    routePath: string
    moduleCode?: string
    contextParams?: Record<string, unknown>
  },
  opts?: ApiOpts,
) {
  const body: Record<string, unknown> = {
    route_path: payload.routePath,
    context_params: payload.contextParams ?? {},
  }
  if (payload.moduleCode) {
    body.module_code = payload.moduleCode
  }
  const raw = await apiFetch<unknown>('/api/v1/assistant/sessions', {
    ...opts,
    method: 'POST',
    body: JSON.stringify(body),
  })
  return normalizeSession(raw)
}

export async function listAssistantSessions(limit = 20, opts?: ApiOpts) {
  const raw = await apiFetch<unknown>(`/api/v1/assistant/sessions?limit=${Math.max(1, Math.min(limit, 100))}`, { ...opts })
  return Array.isArray(raw) ? raw.map(normalizeSession) : []
}

export async function getAssistantSession(sessionId: number, opts?: ApiOpts) {
  const raw = await apiFetch<unknown>(`/api/v1/assistant/sessions/${sessionId}`, { ...opts })
  return normalizeSession(raw)
}

export async function getAssistantSessionMessages(
  sessionId: number,
  opts?: ApiOpts & {
    limit?: number
  },
) {
  const search = new URLSearchParams()
  if (opts?.limit) {
    search.set('limit', String(opts.limit))
  }
  const suffix = search.size > 0 ? `?${search.toString()}` : ''
  const raw = await apiFetch<unknown>(`/api/v1/assistant/sessions/${sessionId}/messages${suffix}`, { ...opts })
  return Array.isArray(raw) ? raw.map(normalizeSessionMessage) : []
}

export async function deleteAssistantSession(sessionId: number, opts?: ApiOpts) {
  await apiFetch<unknown>(`/api/v1/assistant/sessions/${sessionId}`, {
    ...opts,
    method: 'DELETE',
  })
}

export async function chatAssistant(
  payload: {
    sessionId: number
    message: string
    routePath?: string
    contextParams?: Record<string, unknown>
  },
  opts?: ApiOpts,
) {
  const raw = await apiFetch<unknown>('/api/v1/assistant/chat/reply', {
    ...opts,
    method: 'POST',
    body: JSON.stringify({
      session_id: payload.sessionId,
      message: payload.message,
      route_path: payload.routePath,
      context_params: payload.contextParams ?? {},
    }),
  })
  return normalizeChatResult(raw)
}

type AssistantStreamSessionPayload = {
  sessionId: number
  message: string
  routePath?: string
  contextParams?: Record<string, unknown>
}

type AssistantStreamLegacyPayload = {
  message: string
  routePath: string
  contextParams?: Record<string, unknown>
}

export async function streamAssistantChat(
  payload: AssistantStreamSessionPayload | AssistantStreamLegacyPayload,
  onMessage: (chunk: AssistantStreamChunk) => void,
  opts?: ApiOpts & { signal?: AbortSignal | null },
) {
  const apiBase = getApiBaseUrl()
  const url = `${apiBase}/api/v1/assistant/chat`

  let session: Session
  try {
    session = await resolveValidSession(opts?.session)
  } catch {
    clearSession()
    emitAuthEvent('logout')
    throw new Error(translateActive('system.assistant.loginExpiredRelogin'))
  }

  async function doFetch(token: string | null) {
    const headers: HeadersInit = {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
    }
    if (token) headers.Authorization = `Bearer ${token}`
    if (opts?.tenantId) {
      headers['X-Tenant-Id'] = String(opts.tenantId)
    }

    const body = 'sessionId' in payload
      ? {
          session_id: payload.sessionId,
          message: payload.message,
          route_path: payload.routePath,
          context_params: payload.contextParams ?? {},
        }
      : {
          message: payload.message,
          route_path: payload.routePath,
          context_params: payload.contextParams ?? {},
        }

    return fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      credentials: 'include',
      signal: opts?.signal ?? undefined,
    })
  }

  let response = await doFetch(getSessionAccessBearer(session))
  if (response.status === 401) {
    try {
      session = await refreshSession(session, apiBase)
      response = await doFetch(getSessionAccessBearer(session))
    } catch {
      clearSession()
      emitAuthEvent('logout')
      throw new Error(translateActive('system.assistant.loginExpiredRelogin'))
    }
  }

  if (!response.ok) {
    const errorText = await response.text().catch(() => '')
    throw new Error(errorText || translateActive('system.api.requestFailedWithStatus').replace('{status}', String(response.status)))
  }

  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const json = await response.json().catch(() => null)
    const msg = json?.message || json?.detail || json?.error || translateActive('system.assistant.nonStreamResponseFailed')
    throw new Error(msg)
  }

  const reader = response.body?.getReader()
  const decoder = new TextDecoder()
  if (!reader) throw new Error('No response body')

  const flushLine = (line: string) => {
    const trimmedLine = line.trim()
    if (!trimmedLine.startsWith('data: ')) return
    const dataStr = trimmedLine.slice(6)
    if (!dataStr) return
    try {
      const chunk = normalizeAssistantStreamChunk(JSON.parse(dataStr))
      if (chunk) onMessage(chunk)
    } catch {
      // ignore malformed stream chunk
    }
  }

  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      buffer += decoder.decode()
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      flushLine(line)
    }
  }

  if (buffer.trim()) {
    for (const line of buffer.split('\n')) {
      flushLine(line)
    }
  }
}

export async function executeAssistantAction(
  payload: {
    sessionId: number
    actionType: string
    params?: Record<string, unknown>
  },
  opts?: ApiOpts,
) {
  const raw = await apiFetch<unknown>('/api/v1/assistant/actions/execute', {
    ...opts,
    method: 'POST',
    body: JSON.stringify({
      session_id: payload.sessionId,
      action_type: payload.actionType,
      params: payload.params ?? {},
    }),
  })
  return normalizeAssistantActionResult(raw)
}
