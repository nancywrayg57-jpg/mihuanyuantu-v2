import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { CmsPageRender } from '@/components/cms/page-render'
import { cmsMetadata } from '@/lib/server/cms-metadata'
import { getPageSSR } from '@/lib/server/cms-server'
import { isSupportedLocale } from '@/lib/site-locales'

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>
}): Promise<Metadata> {
  const { locale, slug } = await params
  const page = await getPageSSR(slug, locale)
  return cmsMetadata({
    locale,
    subPath: `/${slug}`,
    title: page?.seo?.title || page?.title,
    description: page?.seo?.description,
    keywords: page?.seo?.keywords,
  })
}

export default async function LocaleCmsPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>
}) {
  const { locale, slug } = await params
  if (!isSupportedLocale(locale)) notFound()
  const page = await getPageSSR(slug, locale)
  if (!page) notFound()
  return <CmsPageRender data={page.blocks} />
}
