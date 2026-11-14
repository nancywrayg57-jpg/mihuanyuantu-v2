'use client'

import { createCookieBackedSession, type Session } from '@/lib/auth'

type LoginResponseData = {
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
}

type AuthSessionResponseData = {
  avatar?: string
  username: string
  nickname?: string
  roles: string[]
  permissions: string[]
  isSuperuser: boolean
  mustCompleteProfile?: boolean
  expires: string
  authMode?: string
}

type AuthEnvelope<T> = {
  success?: boolean
  data?: T | null
  message?: string | null
  code?: string | null
}

export type LoginChallenge = {
  challengeId: string
  expiresAt: string
  ttlSeconds: number
  /** data:image/svg+xml,... 或 data:image/png;base64,...（FR-001） */
  imageBase64: string
  /** 仅开发/测试开关下返回；不得替代图形展示 */
  devCode?: string
}

/** DEBUG 兜底：旧后端无 image 字段时，用明文码本地绘 SVG（仅当服务端返回了 devCode）。 */
export function buildDevCaptchaDataUrl(code: string): string {
  const digits = String(code || '').trim()
  const safe = digits.replace(/[^\dA-Za-z]/g, '').slice(0, 8) || '------'
  const chars = [...safe]
  const texts = chars
    .map((ch, i) => {
      const x = 18 + i * 22
      const y = 32 + ((i % 2) * 4 - 2)
      const rot = (i % 3) * 6 - 6
      return `<text x="${x}" y="${y}" fill="#1e293b" font-size="22" font-family="ui-monospace,monospace" transform="rotate(${rot} ${x} ${y})">${ch}</text>`
    })
    .join('')
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="160" height="52" viewBox="0 0 160 52">` +
    `<rect width="100%" height="100%" fill="#f8f9fc"/>` +
    `<line x1="8" y1="12" x2="150" y2="40" stroke="#cbd5e1" />` +
    `<line x1="12" y1="44" x2="148" y2="10" stroke="#cbd5e1" />` +
    texts +
    `</svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

function normalizeLoginChallenge(raw: LoginChallenge & { image_base64?: string }): LoginChallenge {
  const image =
    (typeof raw.imageBase64 === 'string' && raw.imageBase64.trim()) ||
    (typeof raw.image_base64 === 'string' && raw.image_base64.trim()) ||
    ''
  let imageBase64 = image
  // 旧 API（未重启）只有 devCode：开发态本地绘图像素，避免登录页空白
  if (!imageBase64 && raw.devCode) {
    imageBase64 = buildDevCaptchaDataUrl(raw.devCode)
  }
  return {
    challengeId: raw.challengeId,
    expiresAt: raw.expiresAt,
    ttlSeconds: raw.ttlSeconds,
    imageBase64,
    ...(raw.devCode ? { devCode: raw.devCode } : {}),
  }
}

function getApiBaseUrl() {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL
  return typeof base === 'string' ? base.replace(/\/+$/, '') : ''
}

function coerceExpires(value: unknown): string {
  if (typeof value === 'string' && value.trim()) return value.trim()
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value.toISOString()
  if (typeof value === 'number' && Number.isFinite(value)) return new Date(value).toISOString()
  // Backend may occasionally leave a serializable datetime-like object
  if (value && typeof value === 'object' && 'toISOString' in value) {
    try {
      const iso = (value as { toISOString: () => string }).toISOString()
      if (typeof iso === 'string' && iso.trim()) return iso.trim()
    } catch {
      /* ignore */
    }
  }
  throw new Error('Invalid cookie-backed session payload')
}

function toCookieBackedSession(data: AuthSessionResponseData): Session {
  return createCookieBackedSession({
    avatar: data.avatar,
    username: data.username,
    nickname: data.nickname,
    roles: Array.isArray(data.roles) ? data.roles : [],
    permissions: Array.isArray(data.permissions) ? data.permissions : [],
    isSuperuser: Boolean(data.isSuperuser),
    mustCompleteProfile: Boolean(data.mustCompleteProfile),
    expires: coerceExpires(data.expires),
  })
}

async function readEnvelope<T>(response: Response): Promise<T> {
  const json = (await response.json().catch(() => null)) as AuthEnvelope<T> | null
  if (!response.ok || !json?.success || !json.data) {
    const error = new Error(json?.message || `HTTP ${response.status}`) as Error & {
      status?: number
      code?: string | null
    }
    error.status = response.status
    error.code = json?.code
    throw error
  }
  return json.data
}

/** FR-001：拉取 realphotos 验证码挑战（勿走底座无验证码 login）。 */
export async function fetchLoginChallenge(clientKey?: string): Promise<LoginChallenge> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/realphotos/auth/challenges`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    cache: 'no-store',
    body: JSON.stringify(clientKey ? { clientKey } : {}),
  })
  const data = await readEnvelope<LoginChallenge & { image_base64?: string }>(response)
  return normalizeLoginChallenge(data)
}

/** FR-001：用户名 + 密码 + challengeId/captcha → realphotos 登录（写 cookie）。 */
export async function loginByPassword(
  username: string,
  password: string,
  challengeId: string,
  challengeCode: string,
): Promise<Session> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/realphotos/auth/login`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    cache: 'no-store',
    body: JSON.stringify({
      username,
      password,
      challengeId,
      challengeCode,
    }),
  })
  const data = await readEnvelope<LoginResponseData>(response)
  return toCookieBackedSession(data)
}

export type MerchantRegisterResult = {
  userId: string
  username: string
  nickname?: string
  tenantId: string
  tenantCode: string
  roleCode: string
  requireAudit: boolean
}

/** FR-001 / 架构 §9.2：验证码 + 用户名密码 → 新建商家租户与 rp_merchant。 */
export async function registerMerchant(
  username: string,
  password: string,
  nickname: string | undefined,
  challengeId: string,
  challengeCode: string,
): Promise<MerchantRegisterResult> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/realphotos/auth/register`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    cache: 'no-store',
    body: JSON.stringify({
      username,
      password,
      nickname: nickname?.trim() || undefined,
      challengeId,
      challengeCode,
    }),
  })
  return readEnvelope<MerchantRegisterResult>(response)
}

export async function fetchAuthSession(): Promise<Session | null> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/session`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    credentials: 'include',
    cache: 'no-store',
  })

  if (response.status === 401) {
    return null
  }

  const json = (await response.json().catch(() => null)) as AuthEnvelope<AuthSessionResponseData> | null
  if (!response.ok || !json?.success || !json.data) {
    throw new Error(json?.message || `HTTP ${response.status}`)
  }

  return toCookieBackedSession(json.data)
}

export async function logoutCurrentSession(): Promise<void> {
  await fetch(`${getApiBaseUrl()}/api/v1/auth/logout`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
    },
    credentials: 'include',
    keepalive: true,
  }).catch(() => undefined)
}
