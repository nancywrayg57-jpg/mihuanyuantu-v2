import type { NextRequest, NextResponse } from 'next/server'

const EXTERNAL_SCRIPT_SOURCES = ['https://res.wx.qq.com']
const CONFIGURED_ORIGIN_ENV_KEYS = [
  'NEXT_PUBLIC_API_BASE_URL',
  'API_BASE_URL',
  'NEXT_PUBLIC_BACKEND_PUBLIC_ORIGIN',
] as const

const RELAXED_EMBED_PATH_PREFIXES = [
  '/share',
  '/share-groups',
  '/conversation-share',
  '/forms/share',
  '/reports/share',
  '/s',
  '/stage',
  '/appearance',
  '/assets',
  '/emojis',
  '/plugins',
  '/snippets',
  '/widgets',
  '/export',
  '/history',
  '/files',
] as const

function normalizePathname(pathname: string | null | undefined) {
  const value = String(pathname || '').trim()
  if (!value) return '/'
  if (value === '/') return value
  return value.endsWith('/') ? value.slice(0, -1) : value
}

function matchesPrefix(pathname: string, prefix: string) {
  return pathname === prefix || pathname.startsWith(`${prefix}/`)
}

function normalizeOrigin(value: string | null | undefined) {
  const raw = String(value || '').trim()
  if (!raw) return null
  try {
    return new URL(raw).origin
  } catch {
    return null
  }
}

function toWebSocketOrigin(origin: string) {
  if (origin.startsWith('https://')) {
    return `wss://${origin.slice('https://'.length)}`
  }
  if (origin.startsWith('http://')) {
    return `ws://${origin.slice('http://'.length)}`
  }
  return null
}

function uniqueSources(values: Array<string | null | undefined>) {
  return Array.from(new Set(values.map((item) => String(item || '').trim()).filter(Boolean)))
}

function configuredOrigins() {
  return uniqueSources(CONFIGURED_ORIGIN_ENV_KEYS.map((key) => normalizeOrigin(process.env[key])))
}

function configuredWebSocketOrigins() {
  return uniqueSources(configuredOrigins().map((origin) => toWebSocketOrigin(origin)))
}

function buildPermissionsPolicy() {
  return [
    'accelerometer=()',
    'browsing-topics=()',
    'geolocation=()',
    'gyroscope=()',
    'magnetometer=()',
    'payment=()',
    'usb=()',
  ].join(', ')
}

function buildContentSecurityPolicy() {
  const isDevelopment = process.env.NODE_ENV !== 'production'
  const externalOrigins = configuredOrigins()
  const websocketOrigins = configuredWebSocketOrigins()
  const frameSources = uniqueSources(["'self'", ...externalOrigins])
  const connectSources = uniqueSources(["'self'", ...externalOrigins, ...websocketOrigins])

  const directives = [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "form-action 'self'",
    "frame-ancestors 'self'",
    `script-src ${uniqueSources(["'self'", "'unsafe-inline'", isDevelopment ? "'unsafe-eval'" : null, ...EXTERNAL_SCRIPT_SOURCES]).join(' ')}`,
    `style-src ${uniqueSources(["'self'", "'unsafe-inline'"]).join(' ')}`,
    `img-src ${uniqueSources(["'self'", 'data:', 'blob:', 'https:', 'http:']).join(' ')}`,
    `font-src ${uniqueSources(["'self'", 'data:']).join(' ')}`,
    `connect-src ${connectSources.join(' ')}`,
    `media-src ${uniqueSources(["'self'", 'blob:', 'data:', ...externalOrigins]).join(' ')}`,
    `worker-src ${uniqueSources(["'self'", 'blob:']).join(' ')}`,
    `frame-src ${frameSources.join(' ')}`,
    "manifest-src 'self'",
  ]

  return directives.join('; ')
}

function isHttpsRequest(request: NextRequest) {
  const forwardedProto = String(request.headers.get('x-forwarded-proto') || '')
    .split(',', 1)[0]
    .trim()
    .toLowerCase()
  if (forwardedProto) {
    return forwardedProto === 'https'
  }
  return request.nextUrl.protocol === 'https:'
}

export function shouldRelaxEmbedProtection(pathname: string) {
  const normalized = normalizePathname(pathname)
  return RELAXED_EMBED_PATH_PREFIXES.some((prefix) => matchesPrefix(normalized, prefix))
}

export function applySecurityHeaders(response: NextResponse, request: NextRequest) {
  const pathname = normalizePathname(request.nextUrl.pathname)
  const relaxEmbedProtection = shouldRelaxEmbedProtection(pathname)

  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin')
  response.headers.set('X-Content-Type-Options', 'nosniff')
  response.headers.set('X-DNS-Prefetch-Control', 'off')
  response.headers.set('Permissions-Policy', buildPermissionsPolicy())

  if (isHttpsRequest(request)) {
    response.headers.set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
  }

  if (relaxEmbedProtection) {
    response.headers.delete('Content-Security-Policy')
    response.headers.delete('X-Frame-Options')
    return response
  }

  response.headers.set('Content-Security-Policy', buildContentSecurityPolicy())
  response.headers.set('X-Frame-Options', 'SAMEORIGIN')
  return response
}
