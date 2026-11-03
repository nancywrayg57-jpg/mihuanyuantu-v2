import type { PublicSiteRoutingMode } from './public-site'

export const INTERNAL_SITE_PREFIX = '/__cms-site'

export type PublicSiteRouteDecision =
  | { action: 'next'; owner: 'app' | 'static' }
  | { action: 'not-found'; owner: 'internal' }
  | { action: 'redirect'; owner: 'public'; pathname: string; locale?: string }
  | { action: 'rewrite'; owner: 'public'; pathname: string; locale: string }

export type PublicSiteRouteInput = {
  pathname: string
  hostname: string
  mode: PublicSiteRoutingMode
  publicDomains: readonly string[]
  locales: readonly string[]
  defaultLocale: string
}

function isPathSegment(pathname: string, segment: string) {
  return pathname === segment || pathname.startsWith(`${segment}/`)
}

function normalizeHostname(value: string) {
  const raw = String(value || '').split(',')[0]?.trim().toLowerCase().replace(/\.$/, '') || ''
  if (raw.startsWith('[') && raw.includes(']')) return raw.slice(1, raw.indexOf(']'))
  if (raw.split(':').length === 2) {
    const [host, port] = raw.split(':')
    if (port && /^\d+$/.test(port)) return host
  }
  return raw
}

function isStaticRequest(pathname: string) {
  if (isPathSegment(pathname, '/_next') || isPathSegment(pathname, '/api')) return true
  if (
    [
      '/static', '/vendor', '/assets', '/appearance', '/emojis', '/plugins',
      '/snippets', '/widgets', '/export', '/history', '/files', '/stage', '/ws',
    ].some((prefix) => isPathSegment(pathname, prefix))
  ) return true
  return /\/[^/]+\.[^/]+$/.test(pathname)
}

function externalPath(mode: PublicSiteRoutingMode, logicalPath: string) {
  if (mode !== 'path' || logicalPath === '/') return logicalPath
  return `/site${logicalPath}`
}

function internalPath(locale: string, rest: string) {
  const suffix = rest === '/' ? '' : rest
  return `${INTERNAL_SITE_PREFIX}/${locale}${suffix}`
}

function publicLogicalPath(pathname: string, mode: PublicSiteRoutingMode, hostname: string, domains: readonly string[]) {
  if (mode === 'domain') {
    const requestHost = normalizeHostname(hostname)
    const matched = domains.some((domain) => normalizeHostname(domain) === requestHost)
    return matched ? { path: pathname, canonical: true } : null
  }

  if (mode === 'path') {
    if (pathname === '/') return { path: '/', canonical: true }
    if (pathname === '/site' || pathname === '/site/') return { path: '/', canonical: false }
    if (pathname.startsWith('/site/')) return { path: pathname.slice('/site'.length), canonical: true }
  }

  return null
}

/** Pure route decision used by middleware and the ownership matrix tests. */
export function resolvePublicSiteRoute(input: PublicSiteRouteInput): PublicSiteRouteDecision {
  const pathname = input.pathname || '/'

  // The internal namespace is never a public URL, even when its tail looks like a file.
  if (isPathSegment(pathname, INTERNAL_SITE_PREFIX)) {
    return { action: 'not-found', owner: 'internal' }
  }
  if (isStaticRequest(pathname)) return { action: 'next', owner: 'static' }
  if (input.mode === 'off') return { action: 'next', owner: 'app' }

  const publicPath = publicLogicalPath(pathname, input.mode, input.hostname, input.publicDomains)
  if (!publicPath) return { action: 'next', owner: 'app' }
  if (!publicPath.canonical) {
    return { action: 'redirect', owner: 'public', pathname: '/' }
  }

  const logicalPath = publicPath.path
  const first = logicalPath.split('/')[1] || ''
  const matchedLocale = input.locales.find(
    (locale) => locale.toLowerCase() === first.toLowerCase(),
  )

  if (matchedLocale) {
    const rest = logicalPath.slice(first.length + 1) || '/'
    if (matchedLocale !== first) {
      return {
        action: 'redirect',
        owner: 'public',
        pathname: externalPath(input.mode, `/${matchedLocale}${rest === '/' ? '' : rest}`),
        locale: matchedLocale,
      }
    }
    if (matchedLocale === input.defaultLocale) {
      return {
        action: 'redirect',
        owner: 'public',
        pathname: externalPath(input.mode, rest),
        locale: matchedLocale,
      }
    }
    return {
      action: 'rewrite',
      owner: 'public',
      pathname: internalPath(matchedLocale, rest),
      locale: matchedLocale,
    }
  }

  return {
    action: 'rewrite',
    owner: 'public',
    pathname: internalPath(input.defaultLocale, logicalPath),
    locale: input.defaultLocale,
  }
}

/** Convert the browser-visible public URL back to a locale-independent subpath. */
export function publicSiteSubPath(
  pathname: string,
  locale: string,
  defaultLocale: string,
  mode: PublicSiteRoutingMode,
) {
  let logicalPath = pathname || '/'
  if (mode === 'path') {
    if (logicalPath === '/site' || logicalPath === '/site/') logicalPath = '/'
    else if (logicalPath.startsWith('/site/')) logicalPath = logicalPath.slice('/site'.length)
  }

  if (locale !== defaultLocale) {
    const localePrefix = `/${locale}`
    if (logicalPath === localePrefix) return '/'
    if (logicalPath.startsWith(`${localePrefix}/`)) {
      return logicalPath.slice(localePrefix.length) || '/'
    }
  }
  return logicalPath
}
