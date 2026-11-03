'use client'

import { apiFetch } from '@/lib/api'
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

export async function loginByPassword(username: string, password: string): Promise<Session> {
  const data = await apiFetch<LoginResponseData>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })

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
