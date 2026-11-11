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
  /** 仅开发/测试开关下返回；生产不出现 */
  devCode?: string
}

function getApiBaseUrl() {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL
  return typeof base === 'string' ? base.replace(/\/+$/, '') : ''
}

function toCookieBackedSession(data: AuthSessionResponseData): Session {
  return createCookieBackedSession({
    avatar: data.avatar,
    username: data.username,
    nickname: data.nickname,
    roles: data.roles || [],
    permissions: data.permissions || [],
    isSuperuser: Boolean(data.isSuperuser),
    mustCompleteProfile: Boolean(data.mustCompleteProfile),
    expires: data.expires,
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
  return readEnvelope<LoginChallenge>(response)
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
