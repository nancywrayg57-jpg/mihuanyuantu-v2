'use client'

import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useT } from '@/lib/i18n'
import { translateActive } from '@/lib/i18n/registry'

export type ProviderFieldOptionLike = {
  value: string
  label: string
  description?: string | null
}

export type ProviderFieldSchemaLike = {
  key: string
  label: string
  type: 'string' | 'secret' | 'number' | 'boolean' | 'select' | 'multiselect' | 'json' | 'textarea'
  required?: boolean
  description?: string | null
  placeholder?: string | null
  default?: unknown
  options?: ProviderFieldOptionLike[]
  ui?: Record<string, unknown> | null
}

export type ProviderDescriptorLike = {
  id: string
  fields: ProviderFieldSchemaLike[]
}

export type ProviderDraft = {
  providerId: string
  settings: Record<string, unknown>
  secretDrafts: Record<string, string>
  secretsSet: Record<string, boolean>
}

function splitWordList(value: string) {
  return value
    .split(/\r?\n|,|，/u)
    .map((item) => item.trim())
    .filter(Boolean)
}

function cloneValue<T>(value: T): T {
  if (value === null || value === undefined) return value
  if (typeof value !== "object") return value
  return JSON.parse(JSON.stringify(value)) as T
}

function defaultFieldValue(field: ProviderFieldSchemaLike): unknown {
  if (field.default !== undefined) return cloneValue(field.default)
  switch (field.type) {
    case 'boolean':
      return false
    case 'number':
      return ''
    case 'multiselect':
      return ''
    case 'json':
      return '{}'
    default:
      return ''
  }
}

function normalizeFieldValueForSubmit(field: ProviderFieldSchemaLike, rawValue: unknown): unknown {
  switch (field.type) {
    case 'number': {
      if (rawValue === '' || rawValue === null || rawValue === undefined) return undefined
      const numeric = typeof rawValue === 'number' ? rawValue : Number(rawValue)
      if (Number.isNaN(numeric)) {
        throw new Error(translateActive('system.common.numericFieldError').replace('{name}', field.label))
      }
      return numeric
    }
    case 'boolean':
      return Boolean(rawValue)
    case 'multiselect':
      return Array.isArray(rawValue) ? rawValue : splitWordList(String(rawValue || ''))
    case 'json': {
      if (typeof rawValue === 'string') {
        const trimmed = rawValue.trim()
        if (!trimmed) return {}
        try {
          return JSON.parse(trimmed)
        } catch {
          throw new Error(translateActive('system.common.jsonFieldError').replace('{name}', field.label))
        }
      }
      return rawValue ?? {}
    }
    default:
      return rawValue == null ? '' : String(rawValue)
  }
}

function isEmptyRequiredValue(value: unknown) {
  if (typeof value === 'string') return value.trim().length === 0
  if (Array.isArray(value)) return value.length === 0
  if (value && typeof value === 'object') return Object.keys(value as Record<string, unknown>).length === 0
  return value === null || value === undefined
}

function getFieldTextValue(field: ProviderFieldSchemaLike, value: unknown) {
  if (field.type === 'json') {
    return typeof value === 'string' ? value : JSON.stringify(value ?? {}, null, 2)
  }
  if (field.type === 'multiselect' && Array.isArray(value)) {
    return value.join('\n')
  }
  if (value === undefined || value === null) return ''
  return String(value)
}

export function buildProviderDraft(
  descriptors: ProviderDescriptorLike[],
  selection: { providerId: string; settings: Record<string, unknown> } | null | undefined,
  secretsSet: Record<string, boolean>,
): ProviderDraft {
  const providerId = String(selection?.providerId || '').trim()
  const descriptor = descriptors.find((item) => item.id === providerId) || null

  if (!descriptor) {
    return {
      providerId,
      settings: cloneValue(selection?.settings || {}),
      secretDrafts: {},
      secretsSet: cloneValue(secretsSet || {}),
    }
  }

  const settings: Record<string, unknown> = {}
  const secretDrafts: Record<string, string> = {}
  const nextSecretsSet: Record<string, boolean> = {}

  for (const field of descriptor.fields) {
    if (field.type === 'secret') {
      secretDrafts[field.key] = ''
      nextSecretsSet[field.key] = Boolean(secretsSet?.[field.key])
      continue
    }

    let value = selection?.settings?.[field.key]
    if (value === undefined) {
      value = defaultFieldValue(field)
    }
    if (field.type === 'json' && typeof value !== 'string') {
      value = JSON.stringify(value ?? {}, null, 2)
    }
    if (field.type === 'multiselect' && Array.isArray(value)) {
      value = value.join('\n')
    }
    settings[field.key] = value
  }

  return {
    providerId,
    settings,
    secretDrafts,
    secretsSet: nextSecretsSet,
  }
}

export function serializeProviderDraft(
  draft: ProviderDraft,
  descriptor: ProviderDescriptorLike | null,
) {
  if (!draft.providerId) {
    return { providerId: '', settings: {}, secrets: undefined as Record<string, unknown> | undefined }
  }
  if (!descriptor) {
    throw new Error(translateActive('system.common.providerNotFound').replace('{id}', draft.providerId))
  }

  const settings: Record<string, unknown> = {}
  const secrets: Record<string, unknown> = {}

  for (const field of descriptor.fields) {
    if (field.type === 'secret') {
      const value = String(draft.secretDrafts[field.key] || '').trim()
      if (field.required && !value && !draft.secretsSet[field.key]) {
        throw new Error(translateActive('system.common.fieldUnconfigured').replace('{name}', field.label))
      }
      if (value) {
        secrets[field.key] = value
      }
      continue
    }

    const normalized = normalizeFieldValueForSubmit(field, draft.settings[field.key])
    if (field.required && isEmptyRequiredValue(normalized)) {
      throw new Error(translateActive('system.common.fieldRequired').replace('{name}', field.label))
    }
    if (normalized !== undefined) {
      settings[field.key] = normalized
    }
  }

  return {
    providerId: draft.providerId,
    settings,
    secrets: Object.keys(secrets).length ? secrets : undefined,
  }
}

export function ProviderFieldEditor({
  idPrefix,
  field,
  value,
  secretConfigured,
  onChange,
}: {
  idPrefix: string
  field: ProviderFieldSchemaLike
  value: unknown
  secretConfigured?: boolean
  onChange: (value: unknown) => void
}) {
  const t = useT()
  const inputId = `${idPrefix}-${field.key}`
  const textValue = getFieldTextValue(field, value)
  const description = [field.description, field.required ? t('system.common.required') : null].filter(Boolean).join(' · ')

  if (field.type === 'boolean') {
    return (
      <div className="flex items-start gap-3 rounded-lg border p-3">
        <Checkbox id={inputId} checked={Boolean(value)} onCheckedChange={(checked) => onChange(Boolean(checked))} />
        <div className="grid gap-1">
          <Label htmlFor={inputId}>{field.label}</Label>
          {description ? <div className="text-xs text-muted-foreground">{description}</div> : null}
        </div>
      </div>
    )
  }

  if (field.type === 'select') {
    return (
      <div className="grid gap-2">
        <Label htmlFor={inputId}>{field.label}</Label>
        <Select value={textValue || '__empty__'} onValueChange={(next) => onChange(next === '__empty__' ? '' : next)}>
          <SelectTrigger id={inputId}>
            <SelectValue placeholder={field.placeholder || t('system.common.chooseField').replace('{name}', field.label)} />
          </SelectTrigger>
          <SelectContent>
            {!field.required ? <SelectItem value="__empty__">{t('system.common.unset')}</SelectItem> : null}
            {(field.options || []).map((option) => (
              <SelectItem key={`${field.key}-${option.value}`} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {description ? <div className="text-xs text-muted-foreground">{description}</div> : null}
      </div>
    )
  }

  if (field.type === 'textarea' || field.type === 'json' || field.type === 'multiselect' || field.type === 'secret') {
    return (
      <div className="grid gap-2">
        <Label htmlFor={inputId}>{field.label}</Label>
        <Textarea
          id={inputId}
          value={textValue}
          rows={field.type === 'json' ? 8 : field.type === 'textarea' ? 5 : 4}
          placeholder={field.placeholder || ''}
          onChange={(event) => onChange(event.target.value)}
        />
        <div className="text-xs text-muted-foreground">
          {description || ' '}
          {field.type === 'secret' && secretConfigured ? t('system.common.savedSecretHint') : null}
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-2">
      <Label htmlFor={inputId}>{field.label}</Label>
      <Input
        id={inputId}
        type={field.type === 'number' ? 'number' : 'text'}
        value={textValue}
        placeholder={field.placeholder || ''}
        onChange={(event) => onChange(field.type === 'number' ? event.target.value : event.target.value)}
      />
      {description ? <div className="text-xs text-muted-foreground">{description}</div> : null}
    </div>
  )
}
