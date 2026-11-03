import type { Metadata } from 'next'
import { CheckCircle2 } from 'lucide-react'
import { notFound } from 'next/navigation'

import { ContactForm } from '@/components/cms/contact-form'
import { cmsMetadata } from '@/lib/server/cms-metadata'
import { isSupportedLocale, localePath } from '@/lib/site-locales'

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params
  return cmsMetadata({ locale, subPath: '/contact', title: '联系我们', description: '产品咨询、定制部署与合作洽谈。' })
}

export default async function ContactPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  if (!isSupportedLocale(locale)) notFound()

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute -top-24 left-1/2 h-72 w-[42rem] -translate-x-1/2 rounded-full bg-primary/15 blur-3xl" />
      <div className="relative mx-auto grid w-full max-w-5xl gap-12 px-5 py-16 sm:px-8 sm:py-24 md:grid-cols-2">
        <div>
          <span className="inline-flex rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">联系我们</span>
          <h1 className="mt-4 text-4xl font-bold leading-tight tracking-tight">让我们聊聊你的需求</h1>
          <p className="mt-4 text-muted-foreground">无论是产品咨询、定制部署还是合作洽谈，填写表单后我们会尽快与你联系。</p>
          <ul className="mt-8 space-y-3 text-sm">
            {['专业团队 1 对 1 服务', '支持私有化与定制集成', '7×24 小时技术支持'].map((t) => (
              <li key={t} className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-primary" /> {t}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-2xl border border-border/60 bg-card p-6 shadow-xl shadow-primary/5 sm:p-8">
          <ContactForm sourcePath={localePath(locale, '/contact')} />
        </div>
      </div>
    </div>
  )
}
