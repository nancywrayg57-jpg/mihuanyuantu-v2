import type { Metadata } from 'next'
import { headers } from 'next/headers'

export type SiteSeoConfig = {
  title?: string | null
  keywords?: string | null
  description?: string | null
}

export type SitePublicConfig = {
  tenantId?: number | null
  tenantCode?: string | null
  tenantName?: string | null
  canonicalOrigin?: string | null
  seo?: SiteSeoConfig | null
}

export type SiteMetadataContext = {
  host: string | null
  origin: string | null
}

type FetchBackendJsonOptions = {
  host?: string | null
}

type BuildSiteMetadataOptions = {
  site?: SitePublicConfig | null
  origin?: string | null
  pathname?: string
  pageTitle?: string | null
  pageDescription?: string | null
  pageKeywords?: string | null
  fallbackTitle?: string
  fallbackDescription?: string
}

const DEFAULT_SITE_TITLE = 'AOJUAI'

function resolveBackendBaseUrl() {
  const explicit = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL
  if (typeof explicit === 'string' && explicit.trim()) {
    return explicit.replace(/\/+$/, '')
  }

  const backendPort = process.env.BACKEND_PORT
  if (typeof backendPort === 'string' && backendPort.trim()) {
    return `http://127.0.0.1:${backendPort.trim()}`
  }

  return ''
}

function normalizeText(value: string | null | undefined) {
  const text = String(value || '').trim()
  return text || null
}

function normalizeHost(value: string | null | undefined) {
  const host = String(value || '').trim().toLowerCase()
  if (!host) return null
  return host.split(',')[0]?.trim() || null
}

function normalizeProto(value: string | null | undefined, host: string | null) {
  const raw = String(value || '').trim().toLowerCase()
  if (raw === 'http' || raw === 'https') return raw
  if (host && (host.startsWith('127.0.0.1') || host.startsWith('localhost'))) {
    return 'http'
  }
  return 'https'
}

function splitKeywords(value: string | null | undefined) {
  return String(value || '')
    .split(/[,\n，]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function composeTitle(pageTitle: string | null | undefined, siteTitle: string) {
  const page = normalizeText(pageTitle)
  if (page && page !== siteTitle) {
    return `${page} - ${siteTitle}`
  }
  return page || siteTitle
}

function safeUrl(value: string | null | undefined) {
  const text = normalizeText(value)
  if (!text) return null
  try {
    return new URL(text)
  } catch {
    return null
  }
}

async function fetchBackendJson<T>(pathname: string, options: FetchBackendJsonOptions = {}) {
  const backendBaseUrl = resolveBackendBaseUrl()
  if (!backendBaseUrl) return null

  const requestHeaders = new Headers({ Accept: 'application/json' })
  if (options.host) {
    requestHeaders.set('x-forwarded-host', options.host)
  }
  const proxySharedSecret = process.env.AOJ_PROXY_SHARED_SECRET?.trim()
  if (proxySharedSecret) {
    requestHeaders.set('x-aoju-proxy-key', proxySharedSecret)
  }

  try {
    const response = await fetch(`${backendBaseUrl}${pathname}`, {
      headers: requestHeaders,
      cache: 'no-store',
    })
    if (!response.ok) return null

    const payload = (await response.json().catch(() => null)) as
      | { success?: boolean; data?: T | null }
      | null
    if (!payload?.success) return null
    return payload.data ?? null
  } catch {
    return null
  }
}

export async function getRequestSiteMetadataContext(): Promise<SiteMetadataContext> {
  const requestHeaders = await headers()
  const host = normalizeHost(requestHeaders.get('host'))
  const proto = normalizeProto(requestHeaders.get('x-forwarded-proto'), host)
  return {
    host,
    origin: host ? `${proto}://${host}` : null,
  }
}

export async function fetchSitePublicConfig(options: FetchBackendJsonOptions = {}) {
  return fetchBackendJson<SitePublicConfig>('/api/v1/site/public-config', options)
}

export async function fetchBackendPublicData<T>(pathname: string, options: FetchBackendJsonOptions = {}) {
  return fetchBackendJson<T>(pathname, options)
}

export function buildSiteMetadata(options: BuildSiteMetadataOptions): Metadata {
  const fallbackTitle = normalizeText(options.fallbackTitle) || DEFAULT_SITE_TITLE
  const siteTitle =
    normalizeText(options.site?.seo?.title) ||
    normalizeText(options.site?.tenantName) ||
    fallbackTitle
  const title = composeTitle(options.pageTitle, siteTitle)
  const description =
    normalizeText(options.pageDescription) ||
    normalizeText(options.site?.seo?.description) ||
    normalizeText(options.fallbackDescription) ||
    undefined
  const keywords = splitKeywords(options.pageKeywords ?? options.site?.seo?.keywords)
  const metadataBase = safeUrl(options.origin)
  const pageUrl =
    metadataBase && options.pathname
      ? safeUrl(new URL(options.pathname, metadataBase).toString())
      : null

  return {
    title,
    description,
    keywords: keywords.length > 0 ? keywords : undefined,
    metadataBase: metadataBase || undefined,
    alternates: pageUrl ? { canonical: pageUrl.toString() } : undefined,
    openGraph: {
      title,
      description,
      siteName: siteTitle,
      url: pageUrl?.toString(),
      type: 'website',
    },
    twitter: {
      card: 'summary',
      title,
      description,
    },
  }
}
