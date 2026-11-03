'use client'

export const COOKIE_SESSION_MARKER = '__cookie_session__'

export type SessionAuthMode = 'bearer' | 'cookie'

export type Session = {
  avatar?: string
  username: string
  nickname?: string
  roles: string[]
  permissions: string[]
  isSuperuser: boolean
  mustCompleteProfile?: boolean
  accessToken: string
  refreshToken: string
  expires: string
  authMode: SessionAuthMode
}

const SESSION_STORAGE_KEY = 'aojuai.session'
const PUBLIC_AUTH_OPTIONAL_PATH_PATTERNS: RegExp[] = []

export function isPublicAuthOptionalPath(pathname: string | null | undefined): boolean {
  if (!pathname) return false
  return PUBLIC_AUTH_OPTIONAL_PATH_PATTERNS.some((pattern) => pattern.test(pathname))
}

export function isCurrentPathPublicAuthOptional(): boolean {
  if (typeof window === 'undefined') return false
  return isPublicAuthOptionalPath(window.location.pathname)
}

export function shouldSkipAnonymousSessionProbe(pathname: string | null | undefined, storedSession: Session | null) {
  if (storedSession) return false
  return isPublicAuthOptionalPath(pathname)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function normalizeStringArray(value: unknown): string[] | null {
  if (value == null) return []
  if (!Array.isArray(value)) return null
  const next = value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean)
  return next
}

function normalizeAuthMode(value: unknown): SessionAuthMode | null {
  if (typeof value !== 'string') return null
  const normalized = value.trim().toLowerCase()
  if (normalized === 'bearer' || normalized === 'cookie') {
    return normalized
  }
  return null
}

function normalizeSession(input: unknown): Session | null {
  if (!isRecord(input)) return null

  const username = isNonEmptyString(input.username) ? input.username.trim() : ''
  const expires = isNonEmptyString(input.expires) ? input.expires.trim() : ''
  const roles = normalizeStringArray(input.roles)
  const permissions = normalizeStringArray(input.permissions)
  const authMode = normalizeAuthMode(input.authMode)
  const rawAccessToken = isNonEmptyString(input.accessToken) ? input.accessToken.trim() : ''
  const rawRefreshToken = isNonEmptyString(input.refreshToken) ? input.refreshToken.trim() : ''
  const cookieBacked =
    authMode === 'cookie' ||
    rawAccessToken === COOKIE_SESSION_MARKER ||
    rawRefreshToken === COOKIE_SESSION_MARKER

  if (!username || !expires || !roles || !permissions) {
    return null
  }

  if (Number.isNaN(new Date(expires).getTime())) {
    return null
  }

  if (!cookieBacked && (!rawAccessToken || !rawRefreshToken)) {
    return null
  }

  const accessToken = cookieBacked ? COOKIE_SESSION_MARKER : rawAccessToken
  const refreshToken = cookieBacked ? COOKIE_SESSION_MARKER : rawRefreshToken

  return {
    username,
    accessToken,
    refreshToken,
    expires,
    roles,
    permissions,
    isSuperuser: Boolean(input.isSuperuser),
    mustCompleteProfile: Boolean(input.mustCompleteProfile),
    avatar: isNonEmptyString(input.avatar) ? input.avatar.trim() : undefined,
    nickname: isNonEmptyString(input.nickname) ? input.nickname.trim() : undefined,
    authMode: cookieBacked ? 'cookie' : 'bearer',
  }
}

type SessionMetadata = Omit<Session, 'accessToken' | 'refreshToken' | 'authMode'>

export function createCookieBackedSession(session: SessionMetadata): Session {
  const normalized = normalizeSession({
    ...session,
    authMode: 'cookie',
    accessToken: COOKIE_SESSION_MARKER,
    refreshToken: COOKIE_SESSION_MARKER,
  })
  if (!normalized) {
    throw new Error('Invalid cookie-backed session payload')
  }
  return normalized
}

export function createBearerSession(session: Session): Session {
  const normalized = normalizeSession({
    ...session,
    authMode: 'bearer',
  })
  if (!normalized) {
    throw new Error('Invalid bearer session payload')
  }
  return normalized
}

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY)
    if (!raw) return null
    const normalized = normalizeSession(JSON.parse(raw))
    if (!normalized) {
      localStorage.removeItem(SESSION_STORAGE_KEY)
      return null
    }
    return normalized
  } catch {
    localStorage.removeItem(SESSION_STORAGE_KEY)
    return null
  }
}

export function saveSession(session: Session) {
  const normalized = normalizeSession(session)
  if (!normalized) {
    localStorage.removeItem(SESSION_STORAGE_KEY)
    return
  }
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(normalized))
}

export function clearSession() {
  localStorage.removeItem(SESSION_STORAGE_KEY)
}

export function isCookieBackedSession(session: Session | null | undefined): boolean {
  return Boolean(
    session &&
      (session.authMode === 'cookie' ||
        session.accessToken === COOKIE_SESSION_MARKER ||
        session.refreshToken === COOKIE_SESSION_MARKER),
  )
}

export function getSessionAccessBearer(session: Session | null | undefined): string | null {
  if (!session || isCookieBackedSession(session)) return null
  const token = session.accessToken.trim()
  return token || null
}

export function getSessionRefreshToken(session: Session | null | undefined): string | null {
  if (!session || isCookieBackedSession(session)) return null
  const token = session.refreshToken.trim()
  return token || null
}

export function hasAnyPermission(session: Session | null, perms: string[]) {
  if (!session) return false
  if (session.isSuperuser) return true
  const userPerms = new Set(session.permissions || [])
  return perms.some((p) => userPerms.has(p))
}

export function hasTenantAdminRole(session: Session | null | undefined): boolean {
  if (!session) return false
  if (session.isSuperuser) return true
  const roles = new Set((session.roles || []).map((role) => String(role || '').trim().toLowerCase()))
  return roles.has('admin') || roles.has('tenant_admin')
}

// Auth event system for cross-component communication
type AuthEventType = 'logout'
type AuthEventCallback = () => void

const authEventListeners: Map<AuthEventType, Set<AuthEventCallback>> = new Map()

export function onAuthEvent(event: AuthEventType, callback: AuthEventCallback): () => void {
  if (!authEventListeners.has(event)) {
    authEventListeners.set(event, new Set())
  }
  authEventListeners.get(event)!.add(callback)

  // Return unsubscribe function
  return () => {
    authEventListeners.get(event)?.delete(callback)
  }
}

export function emitAuthEvent(event: AuthEventType): void {
  authEventListeners.get(event)?.forEach((cb) => cb())
}

// Check if token is expired
export function isTokenExpired(session: Session | null): boolean {
  if (!session?.expires) return true
  const expiresTime = new Date(session.expires).getTime()
  return Date.now() >= expiresTime
}
