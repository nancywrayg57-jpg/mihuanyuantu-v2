import { NextRequest } from 'next/server'

const REQUEST_HEADER_ALLOWLIST = ['accept', 'authorization', 'content-type', 'cookie', 'x-tenant-id', 'x-forwarded-for']
const HOP_BY_HOP_RESPONSE_HEADERS = new Set([
  'connection',
  'content-length',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
])

function resolveBackendBaseUrl() {
  const explicit = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL
  if (typeof explicit === 'string' && explicit.trim()) {
    return explicit.replace(/\/+$/, '')
  }

  const backendPort = process.env.BACKEND_PORT
  if (typeof backendPort === 'string' && backendPort.trim()) {
    return `http://127.0.0.1:${backendPort.trim()}`
  }

  throw new Error('Backend API base URL is not configured (API_BASE_URL / NEXT_PUBLIC_API_BASE_URL / BACKEND_PORT)')
}

function buildUpstreamHeaders(request: NextRequest) {
  const headers = new Headers()

  for (const name of REQUEST_HEADER_ALLOWLIST) {
    const value = request.headers.get(name)
    if (value) {
      headers.set(name, value)
    }
  }

  const proxySharedSecret = process.env.AOJ_PROXY_SHARED_SECRET?.trim()
  if (proxySharedSecret) {
    headers.set('x-aoju-proxy-key', proxySharedSecret)
  }

  return headers
}

function buildClientResponseHeaders(upstream: Response) {
  const headers = new Headers()

  upstream.headers.forEach((value, key) => {
    const normalizedKey = key.toLowerCase()
    if (HOP_BY_HOP_RESPONSE_HEADERS.has(normalizedKey) || normalizedKey === 'set-cookie') {
      return
    }
    headers.set(key, value)
  })

  const getSetCookie = (upstream.headers as Headers & { getSetCookie?: () => string[] }).getSetCookie
  const setCookies = typeof getSetCookie === 'function' ? getSetCookie.call(upstream.headers) : []
  for (const cookie of setCookies) {
    if (cookie) {
      headers.append('set-cookie', cookie)
    }
  }

  headers.set('x-aoju-proxy', 'next-app-route')
  return headers
}

export async function proxyToBackend(request: NextRequest, pathname: string) {
  const backendBaseUrl = resolveBackendBaseUrl()
  const search = request.nextUrl.search || ''
  const targetUrl = `${backendBaseUrl}${pathname}${search}`
  const headers = buildUpstreamHeaders(request)
  const shouldSendBody = request.method !== 'GET' && request.method !== 'HEAD'

  try {
    const upstream = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: shouldSendBody ? await request.arrayBuffer() : undefined,
      cache: 'no-store',
      redirect: 'manual',
    })

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: buildClientResponseHeaders(upstream),
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return Response.json(
      {
        success: false,
        code: 'UPSTREAM_PROXY_ERROR',
        message: 'Frontend proxy failed to reach the backend',
        details: message,
      },
      { status: 502 },
    )
  }
}
