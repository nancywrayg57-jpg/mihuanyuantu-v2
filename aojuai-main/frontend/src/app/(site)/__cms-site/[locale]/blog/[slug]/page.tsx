import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { cmsMetadata } from '@/lib/server/cms-metadata'
import { getPostSSR } from '@/lib/server/cms-server'
import { isSupportedLocale, localePath } from '@/lib/site-locales'

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>
}): Promise<Metadata> {
  const { locale, slug } = await params
  const post = await getPostSSR(slug, locale)
  return cmsMetadata({
    locale,
    subPath: `/blog/${slug}`,
    title: post?.title,
    description: post?.excerpt,
  })
}

export default async function BlogPost({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>
}) {
  const { locale, slug } = await params
  if (!isSupportedLocale(locale)) notFound()
  const post = await getPostSSR(slug, locale)
  if (!post) notFound()

  return (
    <article className="mx-auto w-full max-w-3xl px-5 py-16 sm:px-8 sm:py-20">
      <Link href={localePath(locale, '/blog')} className="text-sm text-primary hover:underline">← 返回博客</Link>
      <div className="mt-6 flex flex-wrap gap-1.5">
        {(post.tags || []).map((t) => (
          <span key={t} className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground">{t}</span>
        ))}
      </div>
      <h1 className="mt-4 text-4xl font-bold leading-tight tracking-tight">{post.title}</h1>
      {post.publishedAt ? (
        <time className="mt-3 block text-sm text-muted-foreground">{new Date(post.publishedAt).toLocaleDateString('zh-CN')}</time>
      ) : null}
      {post.coverImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={post.coverImage} alt={post.title} className="mt-8 w-full rounded-2xl border border-border/60" />
      ) : null}
      <div className="prose-cms mt-10 space-y-4 text-[15px] leading-7 text-foreground/90 [&_h2]:mt-8 [&_h2]:text-2xl [&_h2]:font-bold [&_h3]:mt-6 [&_h3]:text-lg [&_h3]:font-semibold [&_ul]:list-disc [&_ul]:pl-6 [&_a]:text-primary [&_a]:underline">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{post.body || ''}</ReactMarkdown>
      </div>
    </article>
  )
}
