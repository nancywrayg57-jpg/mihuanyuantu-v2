import 'server-only'

import type { Metadata } from 'next'

import { siteOrigin } from '@/lib/server/cms-server'
import { DEFAULT_LOCALE, localePath, SITE_LOCALES } from '@/lib/site-locales'

/**
 * Build SEO metadata with self-referencing canonical + bidirectional hreflang
 * alternates (subPath is the path AFTER the locale segment, e.g. '' | '/pricing'
 * | '/blog/my-post').
 */
export async function cmsMetadata(opts: {
  locale: string
  subPath: string
  title?: string | null
  description?: string | null
  keywords?: string | null
}): Promise<Metadata> {
  const origin = await siteOrigin()
  const languages: Record<string, string> = {}
  for (const l of SITE_LOCALES) languages[l] = `${origin}${localePath(l, opts.subPath)}`
  languages['x-default'] = `${origin}${localePath(DEFAULT_LOCALE, opts.subPath)}`

  const url = `${origin}${localePath(opts.locale, opts.subPath)}`
  const title = (opts.title || '').trim() || undefined
  const description = (opts.description || '').trim() || undefined

  return {
    title,
    description,
    keywords: opts.keywords || undefined,
    alternates: { canonical: url, languages },
    openGraph: { title, description, url, type: 'website', locale: opts.locale },
    twitter: { card: 'summary_large_image', title, description },
  }
}
