/** @type {import('next').NextConfig} */
if (!process.env.NEXT_PUBLIC_AOJ_ENABLED_MODULES && process.env.AOJ_ENABLED_MODULES) {
  process.env.NEXT_PUBLIC_AOJ_ENABLED_MODULES = process.env.AOJ_ENABLED_MODULES
}
if (!process.env.NEXT_PUBLIC_PUBLIC_SITE_ROUTING_MODE && process.env.PUBLIC_SITE_ROUTING_MODE) {
  process.env.NEXT_PUBLIC_PUBLIC_SITE_ROUTING_MODE = process.env.PUBLIC_SITE_ROUTING_MODE
}
if (!process.env.NEXT_PUBLIC_PUBLIC_SITE_DOMAINS && process.env.PUBLIC_SITE_DOMAINS) {
  process.env.NEXT_PUBLIC_PUBLIC_SITE_DOMAINS = process.env.PUBLIC_SITE_DOMAINS
}

function isBackendRewriteEnabled() {
  const value = String(process.env.NEXT_ENABLE_BACKEND_REWRITES || '').trim().toLowerCase()
  return ['1', 'true', 'yes', 'on'].includes(value)
}

function getApiProxyTarget() {
  const explicit = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL
  if (explicit && typeof explicit === 'string') return explicit.replace(/\/+$/, '')
  const backendPort = process.env.BACKEND_PORT
  if (backendPort) return `http://127.0.0.1:${backendPort}`
  return ''
}

function getBackendRewriteRules(target) {
  // Production `/api/v1/*` traffic belongs to Nginx -> FastAPI.
  // Keep Next rewrites for legacy/direct-port compatibility only; do not
  // rewrite `/api/:path*`, otherwise it can bypass the App Route proxy and
  // cannot reliably attach the trusted proxy secret.
  const rules = [
    '/health',
    '/s/:path*',
    '/static/:path*',
    '/stage/:path*',
    '/appearance/:path*',
    '/assets/:path*',
    '/emojis/:path*',
    '/plugins/:path*',
    '/snippets/:path*',
    '/widgets/:path*',
    '/export/:path*',
    '/history/:path*',
    '/files/:path*',
    '/ws',
    '/ws/:path*',
  ]

  return rules.map((source) => ({
    source,
    destination: `${target}${source}`,
  }))
}

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    if (!isBackendRewriteEnabled()) return []
    const apiProxyTarget = getApiProxyTarget()
    if (!apiProxyTarget) return []
    return {
      beforeFiles: getBackendRewriteRules(apiProxyTarget),
      afterFiles: [],
      fallback: [],
    }
  },
}

export default nextConfig
