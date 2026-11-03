import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { CmsPageRender } from '@/components/cms/page-render'
import { cmsMetadata } from '@/lib/server/cms-metadata'
import { getPageSSR } from '@/lib/server/cms-server'
import { isSupportedLocale } from '@/lib/site-locales'

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params
  const page = await getPageSSR('home', locale)
  return cmsMetadata({
    locale,
    subPath: '',
    title: page?.seo?.title || page?.title,
    description: page?.seo?.description,
    keywords: page?.seo?.keywords,
  })
}

export default async function LocaleHome({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  if (!isSupportedLocale(locale)) notFound()
  const page = await getPageSSR('home', locale)
  if (!page) notFound()
  return <CmsPageRender data={page.blocks} />
}
