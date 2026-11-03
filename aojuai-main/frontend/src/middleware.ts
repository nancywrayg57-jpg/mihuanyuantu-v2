import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

import { PUBLIC_SITE_DOMAINS, PUBLIC_SITE_ROUTING_MODE } from '@/lib/public-site'
import { resolvePublicSiteRoute } from '@/lib/public-site-routing'
import { applySecurityHeaders } from '@/lib/security-headers'
import { DEFAULT_LOCALE, SITE_LOCALES } from '@/lib/site-locales'

/**
 * Public content is resolved only after explicit deployment-level ownership has
 * been established.  App routes never rely on a hand-maintained slug allowlist.
 */
export function middleware(request: NextRequest) {
  const decision = resolvePublicSiteRoute({
    pathname: request.nextUrl.pathname,
    hostname: request.headers.get('host') || request.nextUrl.host,
    mode: PUBLIC_SITE_ROUTING_MODE,
    publicDomains: PUBLIC_SITE_DOMAINS,
    locales: SITE_LOCALES,
    defaultLocale: DEFAULT_LOCALE,
  })

  if (decision.action === 'next') {
    return applySecurityHeaders(NextResponse.next(), request)
  }
  if (decision.action === 'not-found') {
    return applySecurityHeaders(new NextResponse('Not Found', { status: 404 }), request)
  }

  const url = request.nextUrl.clone()
  url.pathname = decision.pathname
  if (decision.action === 'redirect') {
    return applySecurityHeaders(NextResponse.redirect(url, 308), request)
  }

  const headers = new Headers(request.headers)
  headers.set('x-cms-locale', decision.locale)
  return applySecurityHeaders(NextResponse.rewrite(url, { request: { headers } }), request)
}

export const config = {
  matcher: ['/((?!_next|favicon.ico).*)'],
}
