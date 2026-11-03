import type { ReactNode } from 'react'
import { notFound } from 'next/navigation'

import { SiteShell } from '@/components/cms/site-shell'
import { getLanguagesSSR, getNavigationSSR, getSettingsSSR } from '@/lib/server/cms-server'
import { PUBLIC_SITE_ENABLED } from '@/lib/public-site'
import { isSupportedLocale } from '@/lib/site-locales'

export default async function LocaleSiteLayout({
  children,
  params,
}: {
  children: ReactNode
  params: Promise<{ locale: string }>
}) {
  const { locale } = await params
  if (!PUBLIC_SITE_ENABLED || !isSupportedLocale(locale)) notFound()

  const [nav, settings, languages] = await Promise.all([
    getNavigationSSR(),
    getSettingsSSR(),
    getLanguagesSSR(),
  ])
  return (
    <SiteShell
      locale={locale}
      header={nav?.header || []}
      footer={nav?.footer || []}
      settings={settings?.settings || {}}
      languages={(languages?.list || []).map((l) => ({ code: l.code, name: l.name }))}
    >
      {children}
    </SiteShell>
  )
}
