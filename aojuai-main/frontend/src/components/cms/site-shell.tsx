'use client'

import { Globe, Menu, X } from 'lucide-react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

import { RawScripts } from '@/components/cms/raw-scripts'
import { setDocLangOverride } from '@/lib/i18n/doc-lang'
import type { NavItem, SiteSettings } from '@/lib/cms-api'
import { PUBLIC_SITE_ROUTING_MODE } from '@/lib/public-site'
import { publicSiteSubPath } from '@/lib/public-site-routing'
import { DEFAULT_LOCALE, localeLabel, localePath, SITE_LOCALES } from '@/lib/site-locales'
import { cn } from '@/lib/utils'

function brandInitial(name?: string) {
  return (name || 'A').trim().charAt(0).toUpperCase()
}

/** Localize an internal href (as-needed prefix); leave external/app links alone. */
function localizeHref(href: string, locale: string): string {
  if (!href) return localePath(locale, '')
  if (/^https?:\/\//i.test(href) || href.startsWith('#') || href.startsWith('mailto:')) return href
  // app/auth routes that are not localized
  if (href === '/login' || href === '/register' || href.startsWith('/login') || href.startsWith('/register')) return href
  if (href === '/') return localePath(locale, '')
  return localePath(locale, href.startsWith('/') ? href : `/${href}`)
}

export function SiteShell({
  locale,
  header,
  footer,
  settings,
  languages,
  children,
}: {
  locale: string
  header: NavItem[]
  footer: NavItem[]
  settings: SiteSettings
  languages?: { code: string; name: string }[]
  children: React.ReactNode
}) {
  const pathname = usePathname()
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const brand = settings.brandName || 'AOJUAI'
  const langs: { code: string; name: string }[] =
    languages && languages.length
      ? languages
      : (settings.locales && settings.locales.length ? settings.locales : SITE_LOCALES).map((c) => ({
          code: c,
          name: localeLabel(c),
        }))
  const locales = langs.map((l) => l.code)

  // Pin the live-DOM <html lang> to the content locale on the public site,
  // overriding the admin UI i18n provider. Cleared when leaving the public site.
  useEffect(() => {
    setDocLangOverride(locale)
    return () => setDocLangOverride(null)
  }, [locale])

  function switchLocale(next: string) {
    const subPath = publicSiteSubPath(
      pathname || '/',
      locale,
      DEFAULT_LOCALE,
      PUBLIC_SITE_ROUTING_MODE,
    )
    router.push(localePath(next, subPath))
  }

  return (
    <div className="cms-site flex min-h-screen flex-col bg-background text-foreground">
      <RawScripts head={settings.headHtml} body={settings.bodyHtml} />
      <header className="sticky top-0 z-40 border-b border-border/50 bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-5 sm:px-8">
          <Link href={localePath(locale, "")} className="flex items-center gap-2 font-semibold">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
              {brandInitial(brand)}
            </span>
            <span className="text-base">{brand}</span>
          </Link>

          <nav className="hidden items-center gap-1 md:flex">
            {header.map((item) => {
              const href = localizeHref(item.href, locale)
              const active = href === pathname
              return (
                <Link
                  key={item.href + item.label}
                  href={href}
                  target={item.external ? '_blank' : undefined}
                  className={cn(
                    'rounded-full px-3.5 py-2 text-sm font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground',
                    active && 'bg-muted text-foreground',
                  )}
                >
                  {item.label}
                </Link>
              )
            })}
          </nav>

          <div className="hidden items-center gap-2 md:flex">
            {locales.length > 1 ? (
              <div className="flex items-center gap-1 rounded-full border border-border/60 px-1 py-0.5">
                <Globe className="ml-1.5 h-3.5 w-3.5 text-muted-foreground" />
                {langs.map((l) => (
                  <button
                    key={l.code}
                    type="button"
                    onClick={() => switchLocale(l.code)}
                    className={cn(
                      'rounded-full px-2 py-1 text-xs font-medium transition',
                      l.code === locale ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground',
                    )}
                  >
                    {l.name}
                  </button>
                ))}
              </div>
            ) : null}
            <Link href="/login" className="rounded-full px-4 py-2 text-sm font-medium text-muted-foreground transition hover:text-foreground">
              登录
            </Link>
            <Link
              href="/register"
              className="inline-flex items-center rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/25 transition hover:opacity-90"
            >
              免费开始
            </Link>
          </div>

          <button
            type="button"
            aria-label="菜单"
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border/60 md:hidden"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

        {open ? (
          <div className="border-t border-border/50 bg-background md:hidden">
            <div className="mx-auto flex w-full max-w-6xl flex-col gap-1 px-5 py-3">
              {header.map((item) => (
                <Link
                  key={item.href + item.label}
                  href={localizeHref(item.href, locale)}
                  onClick={() => setOpen(false)}
                  className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  {item.label}
                </Link>
              ))}
              {locales.length > 1 ? (
                <div className="mt-1 flex gap-1">
                  {langs.map((l) => (
                    <button
                      key={l.code}
                      type="button"
                      onClick={() => switchLocale(l.code)}
                      className={cn(
                        'rounded-full border px-3 py-1 text-xs',
                        l.code === locale ? 'border-primary bg-primary text-primary-foreground' : 'border-border/60',
                      )}
                    >
                      {l.name}
                    </button>
                  ))}
                </div>
              ) : null}
              <div className="mt-2 flex gap-2">
                <Link href="/login" className="flex-1 rounded-full border border-border/60 px-4 py-2 text-center text-sm font-medium">
                  登录
                </Link>
                <Link href="/register" className="flex-1 rounded-full bg-primary px-4 py-2 text-center text-sm font-semibold text-primary-foreground">
                  免费开始
                </Link>
              </div>
            </div>
          </div>
        ) : null}
      </header>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-border/50 bg-muted/30">
        <div className="mx-auto grid w-full max-w-6xl gap-8 px-5 py-12 sm:px-8 md:grid-cols-[1.5fr_1fr]">
          <div>
            <Link href={localePath(locale, "")} className="flex items-center gap-2 font-semibold">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
                {brandInitial(brand)}
              </span>
              <span>{brand}</span>
            </Link>
            {settings.tagline ? <p className="mt-3 max-w-sm text-sm text-muted-foreground">{settings.tagline}</p> : null}
            {settings.contactEmail ? (
              <a href={`mailto:${settings.contactEmail}`} className="mt-3 inline-block text-sm text-primary hover:underline">
                {settings.contactEmail}
              </a>
            ) : null}
          </div>
          <div className="flex flex-col gap-2 md:items-end">
            {footer.map((item) => (
              <Link
                key={item.href + item.label}
                href={localizeHref(item.href, locale)}
                className="text-sm text-muted-foreground transition hover:text-foreground"
              >
                {item.label}
              </Link>
            ))}
          </div>
        </div>
        <div className="border-t border-border/50 py-5 text-center text-xs text-muted-foreground">
          {settings.footerText || `© ${brand}`}
        </div>
      </footer>
    </div>
  )
}

export default SiteShell
