'use client'

import {
  clearSession,
  createBearerSession,
  createCookieBackedSession,
  emitAuthEvent,
  getSessionAccessBearer,
  getSessionRefreshToken,
  isCurrentPathPublicAuthOptional,
  isCookieBackedSession,
  isTokenExpired,
  loadSession,
  saveSession,
  type Session,
} from '@/lib/auth'
import { getDemoModeMessage, isDemoMode } from '@/lib/demo'
import { type MessageKey } from '@/lib/i18n'
import { translateActive } from '@/lib/i18n/registry'

export type ApiResponse<T> = {
  success: boolean
  data: T | null
  message: string | null
  code: string
  details?: unknown
  detail?: unknown
}

export class ApiError extends Error {
  readonly code?: string
  readonly status?: number
  readonly details?: unknown

  constructor(message: string, opts?: { code?: string; status?: number; details?: unknown }) {
    super(message)
    this.name = 'ApiError'
    this.code = opts?.code
    this.status = opts?.status
    this.details = opts?.details
  }
}

const HTTP_STATUS_MESSAGE_KEYS: Record<number, MessageKey> = {
  400: 'system.api.http400',
  401: 'system.api.http401',
  403: 'system.api.http403',
  404: 'system.api.http404',
  408: 'system.api.http408',
  429: 'system.api.http429',
  500: 'system.api.http500',
  502: 'system.api.http502',
  503: 'system.api.http503',
  504: 'system.api.http504',
}

function getFallbackHttpMessage(status: number): string {
  const key = HTTP_STATUS_MESSAGE_KEYS[status]
  return key
    ? translateActive(key)
    : translateActive('system.api.requestFailedWithStatus').replace('{status}', String(status))
}

function looksLikeHtml(content: string | null | undefined): boolean {
  const text = String(content || '').trim().toLowerCase()
  if (!text) return false
  if (text.startsWith('<!doctype html') || text.startsWith('<html')) return true
  return /<(html|head|body|title|meta|script|style)\b/i.test(text)
}

function normalizeRawErrorText(content: string | null | undefined): string | null {
  const text = String(content || '').trim()
  if (!text || looksLikeHtml(text)) return null
  const compact = text.replace(/\s+/g, ' ')
  return compact.length > 180 ? `${compact.slice(0, 180)}…` : compact
}

function resolveHttpErrorMessage(status: number, ...sources: Array<string | null | undefined>): string {
  for (const source of sources) {
    const normalized = normalizeRawErrorText(source)
    if (normalized) return normalized
  }
  return getFallbackHttpMessage(status)
}

function resolveErrorDetails(content: string | null | undefined): string | undefined {
  const text = String(content || '').trim()
  if (!text || looksLikeHtml(text)) return undefined
  return text.length > 1000 ? `${text.slice(0, 1000)}…` : text
}

export function getApiBaseUrl() {
  if (typeof window !== 'undefined') {
    return ''
  }
  const base = process.env.NEXT_PUBLIC_API_BASE_URL
  return typeof base === 'string' ? base.replace(/\/+$/, '') : ''
}

function shouldAttachJsonContentType(body: BodyInit | null | undefined) {
  if (!body) return false
  if (typeof FormData !== 'undefined' && body instanceof FormData) return false
  if (typeof Blob !== 'undefined' && body instanceof Blob) return false
  if (typeof URLSearchParams !== 'undefined' && body instanceof URLSearchParams) return false
  return true
}

type ApiRequestOptions = RequestInit & {
  session?: Session | null
  tenantId?: number | null
  timeoutMs?: number
  authOptional?: boolean
  anonymous?: boolean
}

function createRequestControl(signal: AbortSignal | null | undefined, timeoutMs?: number) {
  if (!timeoutMs || timeoutMs <= 0) {
    return {
      signal: signal ?? undefined,
      cleanup() {},
      didTimeout() {
        return false
      },
    }
  }

  const controller = new AbortController()
  let timedOut = false
  const onAbort = () => controller.abort(signal?.reason)

  if (signal?.aborted) {
    controller.abort(signal.reason)
  } else if (signal) {
    signal.addEventListener('abort', onAbort, { once: true })
  }

  const timerId = globalThis.setTimeout(() => {
    timedOut = true
    controller.abort(
      typeof DOMException === 'function'
        ? new DOMException(getFallbackHttpMessage(408), 'TimeoutError')
        : new Error(getFallbackHttpMessage(408)),
    )
  }, timeoutMs)

  return {
    signal: controller.signal,
    cleanup() {
      globalThis.clearTimeout(timerId)
      if (signal) {
        signal.removeEventListener('abort', onAbort)
      }
    },
    didTimeout() {
      return timedOut
    },
  }
}

function throwRequestFailure(
  err: unknown,
  opts: {
    didTimeout: () => boolean
    signal: AbortSignal | null | undefined
  },
): never {
  const raw = err instanceof Error ? err.message : String(err)
  if (opts.didTimeout()) {
    throw new ApiError(getFallbackHttpMessage(408), {
      status: 408,
      code: 'REQUEST_TIMEOUT',
      details: raw || undefined,
    })
  }
  if (opts.signal?.aborted) {
    throw new ApiError(translateActive('system.api.requestCancelled'), {
      status: 499,
      code: 'REQUEST_ABORTED',
      details: raw || undefined,
    })
  }
  const message = raw
    ? translateActive('system.api.networkFailedWithReason').replace('{reason}', raw)
    : translateActive('system.api.networkFailed')
  throw new ApiError(message, { status: 0, code: 'NETWORK_ERROR', details: raw || undefined })
}

type RefreshTokenResponseData = {
  avatar?: string
  username?: string
  nickname?: string
  roles?: string[]
  permissions?: string[]
  isSuperuser?: boolean
  accessToken: string
  refreshToken: string
  mustCompleteProfile?: boolean
  expires: string
}

let refreshingPromise: Promise<Session> | null = null

export function applySessionAuthorizationHeader(headers: Headers, session: Session | null | undefined) {
  const accessToken = getSessionAccessBearer(session)
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`)
    return
  }
  headers.delete('Authorization')
}

function requestServerLogout(apiBase: string) {
  void fetch(`${apiBase}/api/v1/auth/logout`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
    },
    credentials: 'include',
    keepalive: true,
  }).catch(() => undefined)
}

function clearAuthState(apiBase: string) {
  requestServerLogout(apiBase)
  clearSession()
  emitAuthEvent('logout')
}

function logoutAndRedirect(redirectToLogin = true) {
  clearAuthState(getApiBaseUrl())
  if (
    redirectToLogin &&
    typeof window !== 'undefined' &&
    !isCurrentPathPublicAuthOptional() &&
    window.location.pathname !== '/login'
  ) {
    window.location.href = '/login'
  }
}

async function refreshSession(session: Session, apiBase: string): Promise<Session> {
  const refreshToken = getSessionRefreshToken(session)
  if (!refreshToken && !isCookieBackedSession(session)) {
    throw new ApiError('Missing refresh token', { status: 401, code: 'MISSING_REFRESH_TOKEN' })
  }

  if (!refreshingPromise) {
    refreshingPromise = (async () => {
      const url = `${apiBase}/api/v1/auth/refresh-token`
      const requestInit: RequestInit = {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      }
      if (refreshToken) {
        requestInit.body = JSON.stringify({ refreshToken })
      }
      const res = await fetch(url, requestInit)

      const json = (await res.json().catch(() => null)) as ApiResponse<RefreshTokenResponseData> | null
      if (!res.ok) {
        const message = json?.message || `HTTP ${res.status}`
        throw new ApiError(message, { status: res.status, code: json?.code, details: json?.details })
      }
      if (!json?.success || !json.data) {
        throw new ApiError(json?.message || 'Refresh token failed', {
          status: res.status,
          code: json?.code,
          details: json?.details,
        })
      }

      // RBAC metadata is not embedded in the token: take roles/permissions from
      // the refresh response so role changes reach long-lived sessions.
      const refreshedMetadata = {
        avatar: json.data.avatar ?? session.avatar,
        username: json.data.username || session.username,
        nickname: json.data.nickname ?? session.nickname,
        roles: Array.isArray(json.data.roles) ? json.data.roles : session.roles,
        permissions: Array.isArray(json.data.permissions) ? json.data.permissions : session.permissions,
        isSuperuser: typeof json.data.isSuperuser === 'boolean' ? json.data.isSuperuser : session.isSuperuser,
        mustCompleteProfile: Boolean(json.data.mustCompleteProfile ?? session.mustCompleteProfile),
        expires: json.data.expires,
      }
      const next = isCookieBackedSession(session)
        ? createCookieBackedSession(refreshedMetadata)
        : createBearerSession({
            ...refreshedMetadata,
            accessToken: json.data.accessToken,
            refreshToken: json.data.refreshToken,
            authMode: 'bearer',
          })
      saveSession(next)
      return next
    })()
      .catch((err) => {
        clearSession()
        throw err
      })
      .finally(() => {
        refreshingPromise = null
      })
  }

  return refreshingPromise
}

export async function apiFetchEnvelope<T>(
  path: string,
  opts: ApiRequestOptions = {},
): Promise<ApiResponse<T> & Record<string, unknown>> {
  const {
    session: providedSession = null,
    tenantId = null,
    timeoutMs,
    authOptional = false,
    anonymous = false,
    signal: requestSignal,
    ...requestInit
  } = opts
  const normalizedUrl = path.split('?')[0]
  const normalizedMethod = String(requestInit.method || 'GET').toLowerCase()
  const isAuthEndpoint = normalizedUrl === '/api/v1/auth/login' || normalizedUrl === '/api/v1/auth/refresh-token'
  const shouldSuppressAuthRedirect = authOptional || isCurrentPathPublicAuthOptional()

  if (isDemoMode()) {
    const allowPostExact = new Set<string>([
      '/api/v1/auth/login',
      '/api/v1/auth/refresh-token',
      '/api/v1/auth/logout',
      '/api/v1/auth/register',
      // List/search endpoints (read-only but use POST body)
      '/api/v1/users',
      '/api/v1/users/pending',
      '/api/v1/roles',
      '/api/v1/permissions',
      '/api/v1/menus',
      '/api/v1/tenants',
      '/api/v1/user-groups',
    ])

    const isAllowedInDemoMode = (() => {
      if (['get', 'head', 'options', 'option'].includes(normalizedMethod)) return true
      if (normalizedMethod === 'post') {
        if (allowPostExact.has(normalizedUrl)) return true
        if (/^\/api\/v1\/tenants\/[^/]+\/users$/.test(normalizedUrl)) return true
        return false
      }
      return false
    })()

    if (!isAllowedInDemoMode) {
      throw new ApiError(getDemoModeMessage(), { status: 403, code: 'DEMO_MODE_READONLY' })
    }
  }

  const apiBase = getApiBaseUrl()
  const url = `${apiBase}${path}`

  const headers = new Headers(requestInit.headers)
  headers.set('Accept', 'application/json')
  if (shouldAttachJsonContentType(requestInit.body) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  // Prefer the latest stored session to avoid stale tokens in React state.
  let session = anonymous ? null : loadSession() ?? providedSession ?? null

  // Refresh access token if needed. On auth-optional routes, fall back to anonymous access.
  if (session && !isAuthEndpoint && isTokenExpired(session)) {
    try {
      session = await refreshSession(session, apiBase)
    } catch {
      if (!shouldSuppressAuthRedirect) {
        logoutAndRedirect()
        throw new ApiError('Token expired', { status: 401, code: 'TOKEN_EXPIRED' })
      }
      clearAuthState(apiBase)
      session = null
    }
  }

  applySessionAuthorizationHeader(headers, session)

  if (tenantId) {
    headers.set('X-Tenant-Id', String(tenantId))
  }

  const requestControl = createRequestControl(requestSignal, timeoutMs)

  try {
    const sendRequest = async () => {
      try {
        return await fetch(url, {
          ...requestInit,
          headers,
          credentials: requestInit.credentials ?? 'include',
          signal: requestControl.signal,
        })
      } catch (err) {
        throwRequestFailure(err, {
          didTimeout: requestControl.didTimeout,
          signal: requestSignal,
        })
      }
    }

    let res = await sendRequest()

    // If backend returns 401, try refresh once then retry.
    if (res.status === 401 && session && !isAuthEndpoint) {
      try {
        session = await refreshSession(session, apiBase)
        applySessionAuthorizationHeader(headers, session)
        res = await sendRequest()
      } catch {
        if (!shouldSuppressAuthRedirect) {
          logoutAndRedirect()
          throw new ApiError('Token expired', { status: 401, code: 'TOKEN_EXPIRED' })
        }
        clearAuthState(apiBase)
        session = null
        applySessionAuthorizationHeader(headers, session)
        res = await sendRequest()
      }
    }

    const contentType = res.headers.get('content-type') || ''
    const isJson = contentType.includes('application/json')

    if (!isJson) {
      const text = await res.text().catch(() => '')
      if (!res.ok) {
        throw new ApiError(resolveHttpErrorMessage(res.status, text), {
          status: res.status,
          details: resolveErrorDetails(text),
        })
      }
      throw new ApiError('Expected JSON response', {
        status: res.status,
        details: resolveErrorDetails(text),
      })
    }

    const json = (await res.json()) as ApiResponse<T> & Record<string, unknown>
    if (!res.ok) {
      if (res.status === 401 && !shouldSuppressAuthRedirect) {
        logoutAndRedirect()
      }
      throw new ApiError(resolveHttpErrorMessage(res.status, json?.message), {
        status: res.status,
        code: json?.code,
        details: json?.details ?? json?.detail,
      })
    }
    if (!json?.success) {
      throw new ApiError(json?.message || 'Request failed', {
        status: res.status,
        code: json?.code,
        details: json?.details ?? json?.detail,
      })
    }
    return json
  } finally {
    requestControl.cleanup()
  }
}

export async function apiFetch<T>(
  path: string,
  opts: ApiRequestOptions = {},
): Promise<T> {
  const json = await apiFetchEnvelope<T>(path, opts)
  return json.data as T
}

export async function apiFetchBlob(
  path: string,
  opts: ApiRequestOptions = {},
): Promise<Blob> {
  const {
    session: providedSession = null,
    tenantId = null,
    timeoutMs,
    authOptional = false,
    anonymous = false,
    signal: requestSignal,
    ...requestInit
  } = opts
  const normalizedUrl = path.split('?')[0]
  const normalizedMethod = String(requestInit.method || 'GET').toLowerCase()
  const isAuthEndpoint = normalizedUrl === '/api/v1/auth/login' || normalizedUrl === '/api/v1/auth/refresh-token'
  const shouldSuppressAuthRedirect = authOptional || isCurrentPathPublicAuthOptional()

  if (isDemoMode()) {
    const allowPostExact = new Set<string>([
      '/api/v1/auth/login',
      '/api/v1/auth/refresh-token',
      '/api/v1/auth/logout',
      '/api/v1/users',
      '/api/v1/users/pending',
      '/api/v1/roles',
      '/api/v1/permissions',
      '/api/v1/menus',
      '/api/v1/tenants',
      '/api/v1/user-groups',
    ])

    const isAllowedInDemoMode = (() => {
      if (['get', 'head', 'options', 'option'].includes(normalizedMethod)) return true
      if (normalizedMethod === 'post') {
        if (allowPostExact.has(normalizedUrl)) return true
        if (/^\/api\/v1\/tenants\/[^/]+\/users$/.test(normalizedUrl)) return true
        return false
      }
      return false
    })()

    if (!isAllowedInDemoMode) {
      throw new ApiError(getDemoModeMessage(), { status: 403, code: 'DEMO_MODE_READONLY' })
    }
  }

  const apiBase = getApiBaseUrl()
  const url = `${apiBase}${path}`

  const headers = new Headers(requestInit.headers)
  headers.set('Accept', '*/*')
  if (shouldAttachJsonContentType(requestInit.body) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let session = anonymous ? null : loadSession() ?? providedSession ?? null

  if (session && !isAuthEndpoint && isTokenExpired(session)) {
    try {
      session = await refreshSession(session, apiBase)
    } catch {
      if (!shouldSuppressAuthRedirect) {
        logoutAndRedirect()
        throw new ApiError('Token expired', { status: 401, code: 'TOKEN_EXPIRED' })
      }
      clearAuthState(apiBase)
      session = null
    }
  }

  applySessionAuthorizationHeader(headers, session)

  if (tenantId) {
    headers.set('X-Tenant-Id', String(tenantId))
  }

  const requestControl = createRequestControl(requestSignal, timeoutMs)

  try {
    const sendRequest = async () => {
      try {
        return await fetch(url, {
          ...requestInit,
          headers,
          credentials: requestInit.credentials ?? 'include',
          signal: requestControl.signal,
        })
      } catch (err) {
        throwRequestFailure(err, {
          didTimeout: requestControl.didTimeout,
          signal: requestSignal,
        })
      }
    }

    let res = await sendRequest()

    if (res.status === 401 && session && !isAuthEndpoint) {
      try {
        session = await refreshSession(session, apiBase)
        applySessionAuthorizationHeader(headers, session)
        res = await sendRequest()
      } catch {
        if (!shouldSuppressAuthRedirect) {
          logoutAndRedirect()
          throw new ApiError('Token expired', { status: 401, code: 'TOKEN_EXPIRED' })
        }
        clearAuthState(apiBase)
        session = null
        applySessionAuthorizationHeader(headers, session)
        res = await sendRequest()
      }
    }

    if (!res.ok) {
      const text = await res.text().catch(() => '')
      if (res.status === 401 && !shouldSuppressAuthRedirect) {
        logoutAndRedirect()
      }
      throw new ApiError(resolveHttpErrorMessage(res.status, text), {
        status: res.status,
        details: resolveErrorDetails(text),
      })
    }

    return res.blob()
  } finally {
    requestControl.cleanup()
  }
}
