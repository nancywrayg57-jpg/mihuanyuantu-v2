'use client'

import type { ReactNode } from 'react'

import { ProviderFieldEditor, type ProviderDraft } from '@/components/speech/provider-form'
import { Badge } from '@/components/ui/badge'
import { useT } from '@/lib/i18n'
import type { SpeechProviderDescriptor } from '@/lib/api/speech'
import { cn } from '@/lib/utils'

export function StatusNote({
  tone,
  children,
}: {
  tone: 'info' | 'warn' | 'error' | 'success'
  children: ReactNode
}) {
  const toneClass =
    tone === 'error'
      ? 'border-destructive/30 bg-destructive/5 text-destructive'
      : tone === 'warn'
        ? 'border-amber-500/30 bg-amber-500/5 text-amber-700 dark:text-amber-300'
        : tone === 'success'
          ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-700 dark:text-emerald-300'
          : 'border-border bg-muted/40 text-muted-foreground'

  return <div className={`rounded-md border px-3 py-2 text-sm ${toneClass}`}>{children}</div>
}

export function WorkspaceSwitch<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T
  onChange: (value: T) => void
  options: Array<{ value: T; label: string }>
}) {
  return (
    <div className="grid grid-cols-2 gap-2 rounded-xl border bg-muted/30 p-1 sm:grid-cols-none sm:auto-cols-fr sm:grid-flow-col">
      {options.map((option) => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={cn(
              'rounded-lg px-3 py-2 text-sm font-medium transition',
              active ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:bg-background/70 hover:text-foreground',
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

function readSettingText(settings: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = settings[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
    if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  }
  return null
}

function getSettingsSummary(settings: Record<string, unknown>, t: (key: string) => string) {
  return [
    { label: t('system.speech.model'), value: readSettingText(settings, ['model']) },
    { label: t('system.speech.voice'), value: readSettingText(settings, ['voice', 'voiceName', 'speaker', 'voiceCloneId']) },
    { label: t('system.speech.language'), value: readSettingText(settings, ['language', 'languageType']) },
  ].filter((item): item is { label: string; value: string } => Boolean(item.value))
}

export function SummaryPills({ settings }: { settings: Record<string, unknown> }) {
  const t = useT()
  const items = getSettingsSummary(settings, t)
  if (!items.length) {
    return <div className="text-sm text-muted-foreground">{t('system.speech.noModelParams')}</div>
  }

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <Badge key={`${item.label}-${item.value}`} variant="secondary" className="max-w-full">
          <span className="truncate">
            {item.label} · {item.value}
          </span>
        </Badge>
      ))}
    </div>
  )
}

export function ConfigFieldGrid({
  idPrefix,
  provider,
  draft,
  onChange,
}: {
  idPrefix: string
  provider: SpeechProviderDescriptor | null
  draft: ProviderDraft
  onChange: (key: string, value: unknown, options?: { secret?: boolean }) => void
}) {
  const t = useT()

  if (!provider) {
    return <StatusNote tone="warn">{t('system.speech.chooseProviderFirst')}</StatusNote>
  }

  if (provider.fields.length === 0) {
    return <StatusNote tone="info">{t('system.speech.noExtraParams')}</StatusNote>
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {provider.fields.map((field) => (
        <ProviderFieldEditor
          key={`${idPrefix}-${field.key}`}
          idPrefix={idPrefix}
          field={field}
          value={field.type === 'secret' ? draft.secretDrafts[field.key] || '' : draft.settings[field.key]}
          secretConfigured={field.type === 'secret' ? Boolean(draft.secretsSet[field.key]) : undefined}
          onChange={(value) => onChange(field.key, value, { secret: field.type === 'secret' })}
        />
      ))}
    </div>
  )
}
