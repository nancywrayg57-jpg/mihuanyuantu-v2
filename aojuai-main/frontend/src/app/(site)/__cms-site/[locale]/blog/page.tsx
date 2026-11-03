import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'

import { cmsMetadata } from '@/lib/server/cms-metadata'
import { getPostsSSR } from '@/lib/server/cms-server'
import { isSupportedLocale, localePath } from '@/lib/site-locales'

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params
  return cmsMetadata({ locale, subPath: '/blog', title: '博客', description: '产品更新、最佳实践与团队思考。' })
}

export default async function BlogIndex({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  if (!isSupportedLocale(locale)) notFound()
  const data = await getPostsSSR(locale, 24)
  const posts = data?.list || []

  return (
    <div className="mx-auto w-full max-w-6xl px-5 py-16 sm:px-8 sm:py-20">
      <header className="text-center">
        <span className="inline-flex rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">博客</span>
        <h1 className="mt-4 text-4xl font-bold tracking-tight">最新动态与洞察</h1>
        <p className="mx-auto mt-3 max-w-xl text-muted-foreground">产品更新、最佳实践与团队思考。</p>
      </header>

      {posts.length === 0 ? (
        <p className="mt-16 text-center text-muted-foreground">还没有发布的文章。</p>
      ) : (
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {posts.map((p) => (
            <Link
              key={p.slug}
              href={localePath(locale, `/blog/${p.slug}`)}
              className="group flex flex-col overflow-hidden rounded-2xl border border-border/60 bg-card transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5"
            >
              <div className="aspect-[16/9] overflow-hidden bg-gradient-to-br from-primary/15 to-primary/5">
                {p.coverImage ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={p.coverImage} alt={p.title} className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full items-center justify-center text-4xl font-bold text-primary/30">{p.title.charAt(0)}</div>
                )}
              </div>
              <div className="flex flex-1 flex-col p-5">
                <div className="flex flex-wrap gap-1.5">
                  {(p.tags || []).slice(0, 2).map((t) => (
                    <span key={t} className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{t}</span>
                  ))}
                </div>
                <h2 className="mt-2 text-lg font-semibold leading-6 group-hover:text-primary">{p.title}</h2>
                {p.excerpt ? <p className="mt-2 line-clamp-2 flex-1 text-sm text-muted-foreground">{p.excerpt}</p> : null}
                {p.publishedAt ? (
                  <time className="mt-4 text-xs text-muted-foreground">{new Date(p.publishedAt).toLocaleDateString('zh-CN')}</time>
                ) : null}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
