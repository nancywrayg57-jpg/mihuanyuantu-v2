import type { MetadataRoute } from 'next'

import { PUBLIC_SITE_ENABLED } from '@/lib/public-site'
import { siteOrigin } from '@/lib/server/cms-server'

export const dynamic = 'force-dynamic'

export default async function robots(): Promise<MetadataRoute.Robots> {
  const origin = PUBLIC_SITE_ENABLED ? (await siteOrigin()) || '' : ''
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        // Keep the authenticated app out of the index.
        disallow: ['/api/', '/system/', '/tenant/', '/personal/', '/cms/', '/dashboard', '/welcome'],
      },
    ],
    sitemap: PUBLIC_SITE_ENABLED && origin ? `${origin}/sitemap.xml` : undefined,
  }
}
