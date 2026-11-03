import type { MetadataRoute } from 'next'

import { getSitemapSSR } from '@/lib/server/cms-server'
import { PUBLIC_SITE_ENABLED } from '@/lib/public-site'
import { DEFAULT_LOCALE, localePath, SITE_LOCALES } from '@/lib/site-locales'

export const dynamic = 'force-dynamic'

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  if (!PUBLIC_SITE_ENABLED) return []
  const data = await getSitemapSSR()
  const origin = String(data?.canonicalOrigin || '').replace(/\/+$/, '')
  if (!origin) return []
  const locales = data?.locales && data.locales.length ? data.locales : SITE_LOCALES
  const entries: MetadataRoute.Sitemap = []

  // path is the sub-path after the locale segment, e.g. '' | '/pricing' | '/blog/x'
  const addLocalized = (subPath: string, lastmod?: string | null) => {
    const languages: Record<string, string> = {}
    for (const l of locales) languages[l] = `${origin}${localePath(l, subPath)}`
    languages['x-default'] = `${origin}${localePath(DEFAULT_LOCALE, subPath)}`
    for (const l of locales) {
      entries.push({
        url: `${origin}${localePath(l, subPath)}`,
        lastModified: lastmod ? new Date(lastmod) : undefined,
        alternates: { languages },
      })
    }
  }

  // home
  addLocalized('')
  // static marketing route
  addLocalized('/blog')
  addLocalized('/contact')
  // CMS pages
  for (const p of data?.pages || []) {
    if (p.slug === 'home') continue
    addLocalized(`/${p.slug}`, p.updatedAt)
  }
  // blog posts
  for (const p of data?.posts || []) {
    addLocalized(`/blog/${p.slug}`, p.updatedAt)
  }

  return entries
}
