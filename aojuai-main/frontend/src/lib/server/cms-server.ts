import 'server-only'

import { headers } from 'next/headers'

import type { NavItem, PublicPage, PublicPost, SiteSettings } from '@/lib/cms-api'

/**
 * Server-side CMS fetchers — used by the public (site) pages so content is
 * server-rendered (in the HTML) for SEO. Mirrors the proxy-key + host handling
 * of lib/server/site-metadata.ts.
 */

function backendBaseUrl(): string {
  const explicit = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL
  if (explicit && explicit.trim()) return explicit.replace(/\/+$/, '')
  const port = process.env.BACKEND_PORT
  if (port && port.trim()) return `http://127.0.0.1:${port.trim()}`
  return ''
}

export async function requestHost(): Promise<string | null> {
  const h = await headers()
  // Next receives the effective Host from the serving proxy.  Do not promote
  // an arbitrary client-supplied forwarding header using our backend secret.
  const raw = (h.get('host') || '').split(',')[0]?.trim().toLowerCase()
  return raw || null
}

export async function siteOrigin(): Promise<string> {
  const config = await cmsFetch<{ canonicalOrigin?: string }>(
    '/api/v1/site/public-config',
    300,
  )
  return String(config?.canonicalOrigin || '').replace(/\/+$/, '')
}

async function cmsFetch<T>(path: string, revalidate = 60): Promise<T | null> {
  const base = backendBaseUrl()
  if (!base) return null
  const host = await requestHost()
  const reqHeaders = new Headers({ Accept: 'application/json' })
  if (host) reqHeaders.set('x-forwarded-host', host)
  const secret = process.env.AOJ_PROXY_SHARED_SECRET?.trim()
  if (secret) reqHeaders.set('x-aoju-proxy-key', secret)
  try {
    const res = await fetch(`${base}${path}`, { headers: reqHeaders, next: { revalidate } })
    if (!res.ok) return null
    const payload = (await res.json().catch(() => null)) as { success?: boolean; data?: T } | null
    if (!payload?.success) return null
    return (payload.data ?? null) as T | null
  } catch {
    return null
  }
}

const lq = (locale?: string) => (locale && locale !== 'default' ? `?locale=${encodeURIComponent(locale)}` : '')

export function getPageSSR(slug: string, locale?: string) {
  return cmsFetch<PublicPage>(`/api/v1/site/cms/pages/${slug}${lq(locale)}`)
}
export function getPostsSSR(locale?: string, pageSize = 24) {
  const q = locale && locale !== 'default' ? `&locale=${encodeURIComponent(locale)}` : ''
  return cmsFetch<{ list: PublicPost[]; total: number }>(
    `/api/v1/site/cms/posts?currentPage=1&pageSize=${pageSize}${q}`,
  )
}
export function getPostSSR(slug: string, locale?: string) {
  return cmsFetch<PublicPost>(`/api/v1/site/cms/posts/${slug}${lq(locale)}`)
}
export function getNavigationSSR() {
  return cmsFetch<{ header: NavItem[]; footer: NavItem[] }>(`/api/v1/site/cms/navigation`)
}
export function getSettingsSSR() {
  return cmsFetch<{ settings: SiteSettings }>(`/api/v1/site/cms/settings`)
}
export function getLanguagesSSR() {
  return cmsFetch<{ list: { code: string; name: string; isDefault: boolean }[]; defaultCode: string }>(
    `/api/v1/site/cms/languages`,
  )
}
export function getSitemapSSR() {
  return cmsFetch<{
    canonicalOrigin: string
    defaultLocale: string
    locales: string[]
    pages: { slug: string; updatedAt: string | null }[]
    posts: { slug: string; updatedAt: string | null }[]
  }>(`/api/v1/site/cms/sitemap`, 300)
}
