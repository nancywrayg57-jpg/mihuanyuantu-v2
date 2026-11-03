'use client'

import type { ReactNode } from 'react'
import { useCallback, useEffect, useId, useMemo, useState } from 'react'
import { Copy } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { Button } from '@/components/ui/button'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'

type MermaidRenderResult = {
  svg: string
}

type MermaidApi = {
  initialize?: (config: Record<string, unknown>) => void
  render: (id: string, text: string) => Promise<MermaidRenderResult | string> | MermaidRenderResult | string
}

async function copyToClipboard(text: string) {
  const value = String(text || '')
  if (!value) return
  try {
    await navigator.clipboard.writeText(value)
  } catch {
    // ignore clipboard failures
  }
}

function omitNodeProp<T extends { node?: unknown }>(props: T): Omit<T, 'node'> {
  const { node, ...rest } = props
  void node
  return rest
}

function MermaidBlock({ chart }: { chart: string }) {
  const t = useT()
  const reactId = useId()
  const chartId = useMemo(() => `mermaid-${reactId.replace(/[^a-zA-Z0-9_-]/g, '')}`, [reactId])
  const [svg, setSvg] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function renderChart() {
      try {
        const mermaidModule = await import('mermaid')
        const mermaid = mermaidModule.default as MermaidApi
        mermaid.initialize?.({
          startOnLoad: false,
          securityLevel: 'strict',
          suppressErrorRendering: true,
        })
        const renderResult = await mermaid.render(`${chartId}-${Date.now()}`, chart)
        const nextSvg = typeof renderResult === 'string' ? renderResult : renderResult.svg
        if (!active) return
        if (!nextSvg) throw new Error('empty mermaid svg')
        setSvg(nextSvg)
        setError(null)
      } catch {
        if (!active) return
        setSvg('')
        setError(t('system.markdown.mermaidError'))
      }
    }

    void renderChart()
    return () => {
      active = false
    }
  }, [chart, chartId, t])

  if (error) {
    return (
      <div className="space-y-2">
        <div className="text-xs text-destructive">{error}</div>
        <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">
          <code className="font-mono">{chart}</code>
        </pre>
      </div>
    )
  }

  if (!svg) {
    return <div className="rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">{t('system.markdown.mermaidLoading')}</div>
  }

  return (
    <div
      className="overflow-x-auto rounded-md border bg-background/60 p-3 [&_svg]:h-auto [&_svg]:max-w-full"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}

export function MarkdownContent({ content, className }: { content: string; className?: string }) {
  const t = useT()
  const value = String(content || '').trim()
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async (text: string) => {
    await copyToClipboard(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }, [])

  if (!value) {
    return <div className={cn('text-sm text-muted-foreground', className)}>{t('system.markdown.empty')}</div>
  }

  return (
    <div className={cn('space-y-3 text-sm', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (props) => <h1 className="scroll-m-20 text-2xl font-semibold tracking-tight" {...omitNodeProp(props)} />,
          h2: (props) => <h2 className="scroll-m-20 text-xl font-semibold tracking-tight" {...omitNodeProp(props)} />,
          h3: (props) => <h3 className="scroll-m-20 text-lg font-semibold tracking-tight" {...omitNodeProp(props)} />,
          p: (props) => <p className="leading-7" {...omitNodeProp(props)} />,
          ul: (props) => <ul className="ml-6 list-disc space-y-1" {...omitNodeProp(props)} />,
          ol: (props) => <ol className="ml-6 list-decimal space-y-1" {...omitNodeProp(props)} />,
          li: (props) => <li className="leading-7" {...omitNodeProp(props)} />,
          a: (props) => (
            <a className="text-primary underline underline-offset-4" target="_blank" rel="noreferrer" {...omitNodeProp(props)} />
          ),
          blockquote: (props) => (
            <blockquote className="border-l-2 pl-4 italic text-muted-foreground" {...omitNodeProp(props)} />
          ),
          code: (raw) => {
            const { node, inline, className: blockClassName, children, ...props } = raw as unknown as {
              node?: unknown
              inline?: boolean
              className?: string
              children?: ReactNode
            }
            void node

            const codeText = String(children ?? '').replace(/\n$/, '')
            const language = /language-([\w-]+)/.exec(blockClassName || '')?.[1]?.toLowerCase() || ''

            if (inline) {
              return (
                <code className={cn('rounded bg-muted px-1 py-0.5 font-mono text-xs', blockClassName)} {...props}>
                  {children}
                </code>
              )
            }

            if (language === 'mermaid') {
              return (
                <div className="space-y-2">
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() => void handleCopy(codeText)}
                      title={copied ? t('system.common.copied') : t('system.common.copyCode')}
                    >
                      <Copy className="mr-1 h-3.5 w-3.5" />
                      {copied ? t('system.common.copied') : t('system.common.copy')}
                    </Button>
                  </div>
                  <MermaidBlock chart={codeText} />
                </div>
              )
            }

            return (
              <div className="space-y-2">
                <div className="flex justify-end">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => void handleCopy(codeText)}
                    title={copied ? t('system.common.copied') : t('system.common.copyCode')}
                  >
                    <Copy className="mr-1 h-3.5 w-3.5" />
                    {copied ? t('system.common.copied') : t('system.common.copy')}
                  </Button>
                </div>
                <pre className="overflow-x-auto rounded-md border bg-muted/40 p-3 text-xs">
                  <code className={cn('font-mono', blockClassName)} {...props}>
                    {children}
                  </code>
                </pre>
              </div>
            )
          },
        }}
      >
        {value}
      </ReactMarkdown>
    </div>
  )
}
