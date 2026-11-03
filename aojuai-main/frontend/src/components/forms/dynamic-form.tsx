'use client'

import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { useT } from '@/lib/i18n'
import { translateActive } from '@/lib/i18n/registry'
import { cn } from '@/lib/utils'

export type DynamicFormFieldOption = {
  label: string
  value: string | number | boolean
}

export type DynamicFormFieldType =
  | 'text'
  | 'string'
  | 'textarea'
  | 'number'
  | 'select'
  | 'date'
  | 'datetime'
  | 'boolean'
  | 'switch'
  | 'kv_table'

export type DynamicFormField = {
  key: string
  label: string
  type?: DynamicFormFieldType
  required?: boolean
  placeholder?: string
  options?: DynamicFormFieldOption[]
  multiple?: boolean
  defaultAll?: boolean
  help?: string
  min?: number
  max?: number
  minLength?: number
  maxLength?: number
  pattern?: string
  default?: unknown
}

export type DynamicFormSchema = {
  version?: number
  title?: string
  fields?: DynamicFormField[]
}

type DynamicFormLikeField = DynamicFormField | Record<string, unknown>

type DynamicFormProps = {
  schema?: DynamicFormSchema | Record<string, unknown> | null
  value?: Record<string, unknown>
  onChange?: (value: Record<string, unknown>) => void
  readonly?: boolean
  emptyText?: string
  className?: string
}

type DynamicFieldInputProps = {
  field: DynamicFormField
  value: unknown
  onChange: (value: unknown) => void
  readonly?: boolean
  fieldId?: string
  labelId?: string
  variant?: 'default' | 'compact' | 'primary'
  selectPlaceholder?: string
  emptySelectLabel?: string
}

function coerceRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function coerceNumber(value: unknown) {
  const num = Number(value)
  return Number.isFinite(num) ? num : undefined
}

function stringifyValue(value: unknown): string {
  if (value === undefined || value === null || value === '') return '-'
  if (Array.isArray(value)) return value.map((item) => stringifyValue(item)).join('、')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function normalizeDynamicFormFieldType(type: unknown, options?: unknown): DynamicFormFieldType {
  const raw = String(type || '').trim().toLowerCase()
  if (raw === 'string') return 'text'
  if (raw === 'text-area' || raw === 'paragraph' || raw === 'long_text') return 'textarea'
  if (raw === 'switch') return 'boolean'
  if (raw) return raw as DynamicFormFieldType
  if (Array.isArray(options) && options.length > 0) return 'select'
  return 'text'
}

export function normalizeDynamicFormFieldOptions(options: unknown): DynamicFormFieldOption[] {
  if (!Array.isArray(options) || options.length === 0) return []
  if (typeof options[0] === 'string' || typeof options[0] === 'number' || typeof options[0] === 'boolean') {
    return options
      .map((item) => String(item).trim())
      .filter(Boolean)
      .map((item) => ({ label: item, value: item }))
  }

  return options
    .map((item) => {
      const record = coerceRecord(item)
      if (!record) return null
      const value = String(record.value ?? record.id ?? '').trim()
      const label = String(record.label ?? record.name ?? value).trim()
      if (!value && !label) return null
      return {
        label: label || value,
        value: value || label,
      }
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item && String(item.value).trim()))
}

export function normalizeDynamicFormField(field: DynamicFormLikeField): DynamicFormField | null {
  const raw = coerceRecord(field)
  if (!raw) return null
  const key = String(raw.key ?? raw.name ?? raw.variable ?? '').trim()
  if (!key) return null

  return {
    key,
    label: String(raw.label ?? raw.title ?? key ?? translateActive('system.common.parameter')).trim() || key,
    type: normalizeDynamicFormFieldType(raw.type, raw.options),
    required: Boolean(raw.required),
    placeholder: String(raw.placeholder ?? '').trim() || undefined,
    options: normalizeDynamicFormFieldOptions(raw.options),
    multiple: Boolean(raw.multiple),
    defaultAll: Boolean(raw.defaultAll ?? raw.default_all),
    help: String(raw.help ?? raw.description ?? '').trim() || undefined,
    min: coerceNumber(raw.min),
    max: coerceNumber(raw.max),
    minLength: coerceNumber(raw.minLength ?? raw.min_length),
    maxLength: coerceNumber(raw.maxLength ?? raw.max_length),
    pattern: String(raw.pattern ?? '').trim() || undefined,
    default: raw.default,
  }
}

export function normalizeDynamicFormFields(fields: unknown): DynamicFormField[] {
  if (!Array.isArray(fields)) return []
  return fields.map((field) => normalizeDynamicFormField(field)).filter((field): field is DynamicFormField => Boolean(field))
}

export function buildDynamicFormInitialValues(
  fields: Array<DynamicFormLikeField>,
  preset?: Record<string, unknown> | null,
): Record<string, unknown> {
  const next: Record<string, unknown> = {}
  for (const rawField of fields) {
    const field = normalizeDynamicFormField(rawField)
    if (!field) continue
    if (preset && preset[field.key] !== undefined) {
      next[field.key] = preset[field.key]
      continue
    }

    if (field.default !== undefined && field.default !== '') {
      next[field.key] = field.default
      continue
    }

    if (field.type === 'boolean') {
      next[field.key] = false
      continue
    }

    if (field.type === 'kv_table') {
      next[field.key] = []
      continue
    }

    if (field.type === 'select' && field.multiple) {
      next[field.key] = field.defaultAll ? field.options?.map((item) => String(item.value)) || [] : []
      continue
    }

    next[field.key] = ''
  }
  return next
}

export function isDynamicFormFieldValueMissing(field: DynamicFormLikeField, value: unknown) {
  const normalized = normalizeDynamicFormField(field)
  if (!normalized) return false

  if (normalized.type === 'boolean') {
    return value === undefined || value === null
  }

  if (normalized.type === 'number') {
    return value === null || value === undefined || value === '' || Number.isNaN(Number(value))
  }

  if (normalized.type === 'select' && normalized.multiple) {
    return !Array.isArray(value) || value.length === 0
  }

  if (normalized.type === 'kv_table') {
    return !Array.isArray(value) || value.length === 0
  }

  return !String(value ?? '').trim()
}

export function findFirstMissingRequiredDynamicField(
  fields: Array<DynamicFormLikeField>,
  values: Record<string, unknown>,
): DynamicFormField | null {
  for (const rawField of fields) {
    const field = normalizeDynamicFormField(rawField)
    if (!field || !field.required) continue
    if (isDynamicFormFieldValueMissing(field, values[field.key])) return field
  }
  return null
}

function KvEditor({
  value,
  onChange,
  readonly,
}: {
  value: Array<{ key: string; value: string }>
  onChange?: (rows: Array<{ key: string; value: string }>) => void
  readonly?: boolean
}) {
  const t = useT()
  const rows = value || []

  function updateRow(index: number, patch: Partial<{ key: string; value: string }>) {
    onChange?.(rows.map((item, idx) => (idx === index ? { ...item, ...patch } : item)))
  }

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('system.common.key')}</TableHead>
              <TableHead>{t('system.common.value')}</TableHead>
              {!readonly ? <TableHead className="w-20 text-right">{t('common.actions')}</TableHead> : null}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, index) => (
              <TableRow key={`${index}-${row.key}`}>
                <TableCell>
                  {readonly ? (
                    <div className="text-sm">{row.key || '-'}</div>
                  ) : (
                    <Input value={row.key} onChange={(event) => updateRow(index, { key: event.target.value })} />
                  )}
                </TableCell>
                <TableCell>
                  {readonly ? (
                    <div className="whitespace-pre-wrap break-words text-sm">{row.value || '-'}</div>
                  ) : (
                    <Input value={row.value} onChange={(event) => updateRow(index, { value: event.target.value })} />
                  )}
                </TableCell>
                {!readonly ? (
                  <TableCell className="text-right">
                    <button
                      type="button"
                      className="text-xs text-destructive transition hover:opacity-80"
                      onClick={() => onChange?.(rows.filter((_, idx) => idx !== index))}
                    >
                      {t('common.delete')}
                    </button>
                  </TableCell>
                ) : null}
              </TableRow>
            ))}
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={readonly ? 2 : 3} className="text-center text-xs text-muted-foreground">
                  {t('system.common.emptyContent')}
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>
      {!readonly ? (
        <button
          type="button"
          className="text-sm text-primary transition hover:opacity-80"
          onClick={() => onChange?.([...(rows || []), { key: '', value: '' }])}
        >
          {t('system.common.addRow')}
        </button>
      ) : null}
    </div>
  )
}

function ReadonlyField({ field, value }: { field: DynamicFormField; value: unknown }) {
  const t = useT()

  if (field.type === 'boolean') {
    return <div className="rounded-md border bg-muted/40 px-3 py-2 text-sm">{value ? t('system.common.yes') : t('system.common.no')}</div>
  }

  if (field.type === 'select') {
    const options = field.options || []
    if (field.multiple) {
      const selected = Array.isArray(value) ? value.map((item) => String(item)) : []
      const labels = options.filter((item) => selected.includes(String(item.value))).map((item) => item.label)
      return <div className="rounded-md border bg-muted/40 px-3 py-2 text-sm">{labels.join('、') || '-'}</div>
    }
    const selected = options.find((item) => String(item.value) === String(value ?? ''))
    return <div className="rounded-md border bg-muted/40 px-3 py-2 text-sm">{selected?.label || stringifyValue(value)}</div>
  }

  if (field.type === 'kv_table') {
    const rows = Array.isArray(value) ? (value as Array<{ key: string; value: string }>) : []
    return <KvEditor value={rows} readonly />
  }

  return <div className="whitespace-pre-wrap break-words rounded-md border bg-muted/40 px-3 py-2 text-sm">{stringifyValue(value)}</div>
}

export function DynamicFieldInput({
  field,
  value,
  onChange,
  readonly = false,
  fieldId,
  labelId,
  variant = 'default',
  selectPlaceholder,
  emptySelectLabel,
}: DynamicFieldInputProps) {
  const t = useT()
  const options = field.options || []
  const resolvedSelectPlaceholder = selectPlaceholder ?? t('system.common.selectPlaceholder')
  const resolvedEmptySelectLabel = emptySelectLabel ?? t('system.common.unselected')
  const inputClassName =
    variant === 'primary' ? 'min-h-[180px] text-base leading-7' : variant === 'compact' ? 'h-11' : undefined

  if (readonly) {
    return <ReadonlyField field={field} value={value} />
  }

  if (field.type === 'textarea') {
    return (
      <Textarea
        id={fieldId}
        aria-label={field.label}
        aria-labelledby={labelId}
        className={inputClassName}
        value={String(value ?? '')}
        onChange={(event) => onChange(event.target.value)}
        placeholder={field.placeholder || ''}
      />
    )
  }

  if (field.type === 'number') {
    return (
      <Input
        id={fieldId}
        aria-label={field.label}
        aria-labelledby={labelId}
        type="number"
        className={inputClassName}
        value={typeof value === 'number' || typeof value === 'string' ? String(value) : ''}
        min={field.min}
        max={field.max}
        onChange={(event) => {
          const raw = event.target.value
          onChange(raw === '' ? '' : Number(raw))
        }}
        placeholder={field.placeholder || ''}
      />
    )
  }

  if (field.type === 'date') {
    return (
      <Input
        id={fieldId}
        aria-label={field.label}
        aria-labelledby={labelId}
        type="date"
        className={inputClassName}
        value={String(value ?? '')}
        onChange={(event) => onChange(event.target.value)}
      />
    )
  }

  if (field.type === 'datetime') {
    return (
      <Input
        id={fieldId}
        aria-label={field.label}
        aria-labelledby={labelId}
        type="datetime-local"
        className={inputClassName}
        value={String(value ?? '')}
        onChange={(event) => onChange(event.target.value)}
      />
    )
  }

  if (field.type === 'boolean') {
    return (
      <div className="flex h-9 items-center" role="group" aria-labelledby={labelId}>
        <Switch
          id={fieldId}
          aria-label={field.label}
          aria-labelledby={labelId}
          checked={Boolean(value)}
          onCheckedChange={(checked) => onChange(checked)}
        />
      </div>
    )
  }

  if (field.type === 'select' && field.multiple) {
    const selectedValues = Array.isArray(value) ? value.map((item) => String(item)) : []
    return (
      <div
        id={fieldId}
        className="grid gap-2 rounded-md border p-3"
        role="group"
        aria-label={field.label}
        aria-labelledby={labelId}
      >
        {options.map((option) => {
          const optionValue = String(option.value)
          const checked = selectedValues.includes(optionValue)
          return (
            <label key={optionValue} className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={checked}
                onCheckedChange={(nextChecked) => {
                  if (nextChecked) onChange([...selectedValues, optionValue])
                  else onChange(selectedValues.filter((item) => item !== optionValue))
                }}
              />
              <span>{option.label}</span>
            </label>
          )
        })}
      </div>
    )
  }

  if (field.type === 'select') {
    const normalizedValue = value === undefined || value === null || value === '' ? '__none__' : String(value)
    return (
      <Select
        value={normalizedValue}
        onValueChange={(nextValue) => {
          onChange(nextValue === '__none__' ? '' : nextValue)
        }}
      >
        <SelectTrigger id={fieldId} aria-label={field.label} aria-labelledby={labelId}>
          <SelectValue placeholder={field.placeholder || resolvedSelectPlaceholder} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__none__">{resolvedEmptySelectLabel}</SelectItem>
          {options.map((option) => (
            <SelectItem key={String(option.value)} value={String(option.value)}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  }

  if (field.type === 'kv_table') {
    const rows = Array.isArray(value) ? (value as Array<{ key: string; value: string }>) : []
    return <KvEditor value={rows} onChange={(rowsValue) => onChange(rowsValue)} />
  }

  return (
    <Input
      id={fieldId}
      aria-label={field.label}
      aria-labelledby={labelId}
      className={inputClassName}
      value={String(value ?? '')}
      onChange={(event) => onChange(event.target.value)}
      placeholder={field.placeholder || ''}
    />
  )
}

export function DynamicForm({
  schema,
  value = {},
  onChange,
  readonly = false,
  emptyText,
  className,
}: DynamicFormProps) {
  const t = useT()
  const parsed = coerceRecord(schema)
  const fields = normalizeDynamicFormFields(parsed?.fields)
  const resolvedEmptyText = emptyText ?? t('system.common.emptyFields')

  if (fields.length === 0) {
    return <div className="rounded-md border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">{resolvedEmptyText}</div>
  }

  return (
    <div className={cn('grid gap-4', className)}>
      {fields.map((field) => {
        const fieldValue = value?.[field.key]
        return (
          <div key={field.key} className="grid gap-2">
            <Label className="text-sm font-medium">
              {field.label || field.key}
              {field.required ? <span className="ml-1 text-destructive">*</span> : null}
            </Label>
            {field.help ? <div className="text-xs text-muted-foreground">{field.help}</div> : null}
            <DynamicFieldInput
              field={field}
              value={fieldValue}
              readonly={readonly}
              onChange={(nextValue) => onChange?.({ ...(value || {}), [field.key]: nextValue })}
            />
          </div>
        )
      })}
    </div>
  )
}
