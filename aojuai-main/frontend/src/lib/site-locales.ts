import { PUBLIC_SITE_ROUTING_MODE } from '@/lib/public-site'

/**
 * Public-site locale configuration (URL prefixes).
 *
 * Locale-prefixed URLs (/zh-CN/…, /en-US/…) are the SEO-recommended structure
 * (subdirectory per language). Configured via env so a deployment/tenant can
 * declare which languages it serves.
 */
export const SITE_LOCALES: string[] = (process.env.NEXT_PUBLIC_SITE_LOCALES || 'zh-CN,en-US')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean)

export const DEFAULT_LOCALE: string =
  process.env.NEXT_PUBLIC_SITE_DEFAULT_LOCALE || SITE_LOCALES[0] || 'zh-CN'

export function isSupportedLocale(value: string | undefined | null): value is string {
  return !!value && SITE_LOCALES.includes(value)
}

const LABELS: Record<string, string> = {
  'zh-CN': '中文',
  'zh': '中文',
  'en-US': 'English',
  'en': 'English',
  'es-ES': 'Español',
}

export function localeLabel(locale: string): string {
  return LABELS[locale] || locale
}

/** BCP-47 value for <html lang> / hreflang (already BCP-47 in our config). */
export function htmlLang(locale: string): string {
  return locale
}

/**
 * "as-needed" locale prefix: the default language is served WITHOUT a prefix
 * (canonical `/`, `/pricing`), non-default languages are prefixed (`/en-US/...`).
 * subPath is the path after the locale segment: '' (home) | '/pricing' | '/blog/x'.
 */
export function localePath(locale: string, subPath = ''): string {
  const sp = subPath && subPath !== '/' ? subPath : ''
  const logicalPath = locale === DEFAULT_LOCALE ? sp || '/' : `/${locale}${sp}`
  if (PUBLIC_SITE_ROUTING_MODE !== 'path' || logicalPath === '/') return logicalPath
  return `/site${logicalPath}`
}
