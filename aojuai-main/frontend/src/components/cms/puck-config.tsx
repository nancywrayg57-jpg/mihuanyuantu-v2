'use client'

/**
 * Puck configuration — the single source of truth for CMS block components.
 * Shared by the admin editor (<Puck>) and the public site (<Render>).
 *
 * Component names here MUST match the `type` values seeded in
 * backend/scripts/seed_cms.py.
 */
import type { Config } from '@measured/puck'
import {
  ArrowRight,
  Bell,
  CheckCircle2,
  CreditCard,
  Layout,
  type LucideIcon,
  Mic,
  Shield,
  Sparkles,
  Star,
  Zap,
} from 'lucide-react'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { VditorEditor } from '@/components/cms/vditor-editor'

const ICONS: Record<string, LucideIcon> = {
  shield: Shield,
  zap: Zap,
  layout: Layout,
  'credit-card': CreditCard,
  bell: Bell,
  mic: Mic,
  star: Star,
  sparkles: Sparkles,
}

function Icon({ name, className }: { name?: string; className?: string }) {
  const Cmp = ICONS[name || 'sparkles'] || Sparkles
  return <Cmp className={className} />
}

type FeatureItem = { icon?: string; title?: string; description?: string }
type Plan = {
  name?: string
  price?: string
  period?: string
  description?: string
  features?: { value?: string }[] | string[]
  ctaText?: string
  ctaHref?: string
  highlighted?: boolean
}

function Container({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-6xl px-5 sm:px-8 ${className}`}>{children}</div>
}

function Cta({ text, href, variant = 'primary' }: { text?: string; href?: string; variant?: 'primary' | 'ghost' }) {
  if (!text) return null
  const base =
    'inline-flex items-center justify-center gap-1.5 rounded-full px-5 py-2.5 text-sm font-semibold transition'
  const styles =
    variant === 'primary'
      ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/25 hover:opacity-90'
      : 'border border-border/70 bg-background/60 text-foreground hover:bg-muted'
  return (
    <Link href={href || '#'} className={`${base} ${styles}`}>
      {text}
      {variant === 'primary' ? <ArrowRight className="h-4 w-4" /> : null}
    </Link>
  )
}

export const puckConfig: Config = {
  root: {
    render: ({ children }: { children?: React.ReactNode }) => <div className="cms-site cms-root">{children}</div>,
  },
  components: {
    Hero: {
      label: 'Hero 头图',
      fields: {
        eyebrow: { type: 'text', label: '小标题' },
        title: { type: 'textarea', label: '主标题' },
        subtitle: { type: 'textarea', label: '副标题' },
        primaryText: { type: 'text', label: '主按钮文字' },
        primaryHref: { type: 'text', label: '主按钮链接' },
        secondaryText: { type: 'text', label: '次按钮文字' },
        secondaryHref: { type: 'text', label: '次按钮链接' },
        image: { type: 'text', label: '配图 URL（可选）' },
      },
      defaultProps: {
        eyebrow: '全新发布',
        title: '一句话讲清你的产品价值',
        subtitle: '用一两句话补充说明，让访客立刻明白能获得什么。',
        primaryText: '免费开始',
        primaryHref: '/register',
        secondaryText: '了解更多',
        secondaryHref: '/features',
        image: '',
      },
      render: ({ eyebrow, title, subtitle, primaryText, primaryHref, secondaryText, secondaryHref, image }) => (
        <section className="relative overflow-hidden border-b border-border/40 bg-gradient-to-b from-primary/5 via-background to-background py-20 sm:py-28">
          <div className="pointer-events-none absolute -top-24 left-1/2 h-72 w-[42rem] -translate-x-1/2 rounded-full bg-primary/20 blur-3xl" />
          <Container className="relative text-center">
            {eyebrow ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                <Sparkles className="h-3.5 w-3.5" /> {eyebrow}
              </span>
            ) : null}
            <h1 className="mx-auto mt-5 max-w-3xl text-balance text-4xl font-bold leading-tight tracking-tight sm:text-5xl md:text-6xl">
              {title}
            </h1>
            {subtitle ? (
              <p className="mx-auto mt-5 max-w-2xl text-balance text-base text-muted-foreground sm:text-lg">
                {subtitle}
              </p>
            ) : null}
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Cta text={primaryText} href={primaryHref} />
              <Cta text={secondaryText} href={secondaryHref} variant="ghost" />
            </div>
            {image ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={image}
                alt=""
                className="mx-auto mt-14 w-full max-w-4xl rounded-xl border border-border/60 shadow-2xl shadow-primary/10"
              />
            ) : null}
          </Container>
        </section>
      ),
    },

    Stats: {
      label: '数据指标',
      fields: {
        items: {
          type: 'array',
          label: '指标',
          getItemSummary: (it: { value?: string; label?: string }) => it.label || '指标',
          arrayFields: { value: { type: 'text', label: '数值' }, label: { type: 'text', label: '说明' } },
        },
      },
      defaultProps: {
        items: [
          { value: '99.9%', label: '可用性' },
          { value: '10k+', label: '用户' },
          { value: '24/7', label: '支持' },
        ],
      },
      render: ({ items }) => (
        <section className="py-12">
          <Container>
            <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-border/60 bg-border/60 sm:grid-cols-4">
              {((items as { value?: string; label?: string }[]) || []).map((it, i) => (
                <div key={i} className="bg-background p-6 text-center">
                  <div className="text-3xl font-bold text-primary">{it.value}</div>
                  <div className="mt-1 text-sm text-muted-foreground">{it.label}</div>
                </div>
              ))}
            </div>
          </Container>
        </section>
      ),
    },

    Features: {
      label: '功能网格',
      fields: {
        title: { type: 'text', label: '标题' },
        subtitle: { type: 'textarea', label: '副标题' },
        columns: { type: 'select', label: '列数', options: [{ label: '2', value: '2' }, { label: '3', value: '3' }] },
        items: {
          type: 'array',
          label: '功能项',
          getItemSummary: (it: FeatureItem) => it.title || '功能',
          arrayFields: {
            icon: {
              type: 'select',
              label: '图标',
              options: Object.keys(ICONS).map((k) => ({ label: k, value: k })),
            },
            title: { type: 'text', label: '标题' },
            description: { type: 'textarea', label: '描述' },
          },
        },
      },
      defaultProps: {
        title: '为什么选择我们',
        subtitle: '',
        columns: '3',
        items: [
          { icon: 'zap', title: '快速', description: '极速上手，几分钟即可接入。' },
          { icon: 'shield', title: '安全', description: '企业级权限与租户隔离。' },
          { icon: 'sparkles', title: '智能', description: '原生内置 AI 能力。' },
        ],
      },
      render: ({ title, subtitle, columns, items }) => (
        <section className="py-16 sm:py-20">
          <Container>
            {title ? <h2 className="text-center text-3xl font-bold tracking-tight">{title}</h2> : null}
            {subtitle ? <p className="mx-auto mt-3 max-w-2xl text-center text-muted-foreground">{subtitle}</p> : null}
            <div className={`mt-12 grid gap-5 ${columns === '2' ? 'sm:grid-cols-2' : 'sm:grid-cols-2 lg:grid-cols-3'}`}>
              {((items as FeatureItem[]) || []).map((it, i) => (
                <div
                  key={i}
                  className="group rounded-2xl border border-border/60 bg-card p-6 transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5"
                >
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary transition group-hover:bg-primary group-hover:text-primary-foreground">
                    <Icon name={it.icon} className="h-5 w-5" />
                  </div>
                  <h3 className="mt-4 text-base font-semibold">{it.title}</h3>
                  <p className="mt-1.5 text-sm leading-6 text-muted-foreground">{it.description}</p>
                </div>
              ))}
            </div>
          </Container>
        </section>
      ),
    },

    Pricing: {
      label: '定价方案',
      fields: {
        title: { type: 'text', label: '标题' },
        subtitle: { type: 'textarea', label: '副标题' },
        plans: {
          type: 'array',
          label: '方案',
          getItemSummary: (it: Plan) => it.name || '方案',
          arrayFields: {
            name: { type: 'text', label: '名称' },
            price: { type: 'text', label: '价格' },
            period: { type: 'text', label: '周期' },
            description: { type: 'text', label: '描述' },
            features: {
              type: 'array',
              label: '特性',
              getItemSummary: (it: { value?: string }) => it.value || '特性',
              arrayFields: { value: { type: 'text', label: '特性' } },
            },
            ctaText: { type: 'text', label: '按钮文字' },
            ctaHref: { type: 'text', label: '按钮链接' },
            highlighted: { type: 'radio', label: '突出显示', options: [{ label: '是', value: true }, { label: '否', value: false }] },
          },
        },
      },
      defaultProps: {
        title: '简单透明的定价',
        subtitle: '',
        plans: [
          { name: '入门', price: '¥0', period: '/月', description: '适合个人', features: [{ value: '基础功能' }], ctaText: '开始', ctaHref: '/register', highlighted: false },
        ],
      },
      render: ({ title, subtitle, plans }) => (
        <section className="py-16 sm:py-20">
          <Container>
            {title ? <h2 className="text-center text-3xl font-bold tracking-tight">{title}</h2> : null}
            {subtitle ? <p className="mx-auto mt-3 max-w-2xl text-center text-muted-foreground">{subtitle}</p> : null}
            <div className="mt-12 grid gap-6 lg:grid-cols-3">
              {((plans as Plan[]) || []).map((p, i) => {
                const feats = (p.features || []).map((f) => (typeof f === 'string' ? f : f?.value || ''))
                return (
                  <div
                    key={i}
                    className={`relative flex flex-col rounded-2xl border p-7 ${
                      p.highlighted
                        ? 'border-primary bg-primary/5 shadow-xl shadow-primary/10 lg:scale-[1.03]'
                        : 'border-border/60 bg-card'
                    }`}
                  >
                    {p.highlighted ? (
                      <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground">
                        最受欢迎
                      </span>
                    ) : null}
                    <div className="text-sm font-semibold text-muted-foreground">{p.name}</div>
                    <div className="mt-3 flex items-end gap-1">
                      <span className="text-4xl font-bold">{p.price}</span>
                      <span className="pb-1 text-sm text-muted-foreground">{p.period}</span>
                    </div>
                    {p.description ? <p className="mt-2 text-sm text-muted-foreground">{p.description}</p> : null}
                    <ul className="mt-6 flex-1 space-y-3 text-sm">
                      {feats.map((f, j) => (
                        <li key={j} className="flex items-start gap-2">
                          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>
                    <div className="mt-7">
                      <Link
                        href={p.ctaHref || '#'}
                        className={`flex w-full items-center justify-center rounded-full px-5 py-2.5 text-sm font-semibold transition ${
                          p.highlighted
                            ? 'bg-primary text-primary-foreground hover:opacity-90'
                            : 'border border-border/70 hover:bg-muted'
                        }`}
                      >
                        {p.ctaText || '选择'}
                      </Link>
                    </div>
                  </div>
                )
              })}
            </div>
          </Container>
        </section>
      ),
    },

    FAQ: {
      label: '常见问题',
      fields: {
        title: { type: 'text', label: '标题' },
        items: {
          type: 'array',
          label: '问答',
          getItemSummary: (it: { question?: string }) => it.question || '问题',
          arrayFields: { question: { type: 'text', label: '问题' }, answer: { type: 'textarea', label: '回答' } },
        },
      },
      defaultProps: {
        title: '常见问题',
        items: [{ question: '问题示例？', answer: '回答示例。' }],
      },
      render: ({ title, items }) => (
        <section className="py-16 sm:py-20">
          <Container className="max-w-3xl">
            {title ? <h2 className="text-center text-3xl font-bold tracking-tight">{title}</h2> : null}
            <div className="mt-10 divide-y divide-border/60 rounded-2xl border border-border/60 bg-card">
              {((items as { question?: string; answer?: string }[]) || []).map((it, i) => (
                <details key={i} className="group p-5 [&_summary]:cursor-pointer">
                  <summary className="flex items-center justify-between text-base font-medium marker:content-['']">
                    {it.question}
                    <span className="text-primary transition group-open:rotate-45">+</span>
                  </summary>
                  <p className="mt-3 text-sm leading-6 text-muted-foreground">{it.answer}</p>
                </details>
              ))}
            </div>
          </Container>
        </section>
      ),
    },

    CTA: {
      label: '行动号召',
      fields: {
        title: { type: 'text', label: '标题' },
        subtitle: { type: 'textarea', label: '副标题' },
        buttonText: { type: 'text', label: '按钮文字' },
        buttonHref: { type: 'text', label: '按钮链接' },
      },
      defaultProps: {
        title: '准备好开始了吗？',
        subtitle: '立即免费体验。',
        buttonText: '免费开始',
        buttonHref: '/register',
      },
      render: ({ title, subtitle, buttonText, buttonHref }) => (
        <section className="py-16 sm:py-20">
          <Container>
            <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-primary to-primary/70 px-8 py-14 text-center text-primary-foreground">
              <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-2xl" />
              <h2 className="relative text-3xl font-bold tracking-tight">{title}</h2>
              {subtitle ? <p className="relative mx-auto mt-3 max-w-xl text-primary-foreground/90">{subtitle}</p> : null}
              {buttonText ? (
                <Link
                  href={buttonHref || '#'}
                  className="relative mt-7 inline-flex items-center gap-1.5 rounded-full bg-background px-6 py-3 text-sm font-semibold text-foreground shadow-lg transition hover:opacity-90"
                >
                  {buttonText} <ArrowRight className="h-4 w-4" />
                </Link>
              ) : null}
            </div>
          </Container>
        </section>
      ),
    },

    RichText: {
      label: '富文本（Markdown）',
      fields: {
        content: {
          type: 'custom',
          label: '内容',
          render: ({ value, onChange }: { value?: string; onChange: (v: string) => void }) => (
            <VditorEditor value={value || ''} onChange={onChange} height={280} />
          ),
        },
      },
      defaultProps: { content: '## 标题\n\n正文内容，支持 **Markdown**。' },
      render: ({ content }) => (
        <section className="py-12">
          <Container className="max-w-3xl">
            <div className="prose-cms space-y-4 text-[15px] leading-7 text-foreground/90">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{(content as string) || ''}</ReactMarkdown>
            </div>
          </Container>
        </section>
      ),
    },
  },
}

export default puckConfig
