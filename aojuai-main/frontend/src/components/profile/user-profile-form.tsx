'use client'

import { MultiSelect, type MultiSelectOption } from '@/components/ui/multi-select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { getEnabledUserProfileFields, type UserProfileFieldDefinition, type UserProfileFieldsConfig } from '@/lib/user-profile-fields'

type UserProfileFormProps = {
  config: UserProfileFieldsConfig | null | undefined
  value: Record<string, unknown>
  onChange: (next: Record<string, unknown>) => void
  disabled?: boolean
  className?: string
  showHelpText?: boolean
}

function shouldRemoveFieldValue(field: UserProfileFieldDefinition, nextValue: unknown) {
  if (nextValue == null) return true
  if (field.type === 'multi_select') return !Array.isArray(nextValue) || nextValue.length === 0
  if (field.type === 'boolean') return false
  return !String(nextValue).trim()
}

function normalizeMultiSelectOptions(field: UserProfileFieldDefinition): MultiSelectOption[] {
  return (field.options || []).map((option) => ({
    value: option.value,
    label: option.label,
  }))
}

export function UserProfileForm({
  config,
  value,
  onChange,
  disabled = false,
  className,
  showHelpText = true,
}: UserProfileFormProps) {
  const t = useT()
  const fields = getEnabledUserProfileFields(config)

  if (!fields.length) return null

  const updateField = (field: UserProfileFieldDefinition, nextValue: unknown) => {
    const next = { ...value }
    if (shouldRemoveFieldValue(field, nextValue)) {
      delete next[field.key]
    } else {
      next[field.key] = nextValue
    }
    onChange(next)
  }

  return (
    <div className={cn('grid gap-4 md:grid-cols-2', className)}>
      {fields.map((field) => {
        const currentValue = value[field.key]
        const label = (
          <span>
            {field.label}
            {field.required ? <span className="ml-1 text-destructive">*</span> : null}
          </span>
        )

        if (field.type === 'textarea') {
          return (
            <div key={field.key} className="grid gap-2 md:col-span-2">
              <Label>{label}</Label>
              <Textarea
                value={typeof currentValue === 'string' ? currentValue : ''}
                onChange={(e) => updateField(field, e.target.value)}
                placeholder={field.placeholder || undefined}
                disabled={disabled}
              />
              {showHelpText && field.helpText ? <div className="text-xs text-muted-foreground">{field.helpText}</div> : null}
            </div>
          )
        }

        if (field.type === 'select') {
          return (
            <div key={field.key} className="grid gap-2">
              <Label>{label}</Label>
              <Select
                value={typeof currentValue === 'string' && currentValue ? currentValue : '__empty__'}
                onValueChange={(nextValue) => updateField(field, nextValue === '__empty__' ? null : nextValue)}
                disabled={disabled}
              >
                <SelectTrigger>
                  <SelectValue placeholder={field.placeholder || t('system.common.selectPlaceholder')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__empty__">{t('system.common.unselected')}</SelectItem>
                  {(field.options || []).map((option) => (
                    <SelectItem key={`${field.key}:${option.value}`} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {showHelpText && field.helpText ? <div className="text-xs text-muted-foreground">{field.helpText}</div> : null}
            </div>
          )
        }

        if (field.type === 'multi_select') {
          return (
            <div key={field.key} className="grid gap-2">
              <Label>{label}</Label>
              <MultiSelect
                options={normalizeMultiSelectOptions(field)}
                value={Array.isArray(currentValue) ? (currentValue as (string | number)[]) : []}
                onChange={(nextValue) => updateField(field, nextValue.map((item) => String(item)))}
                placeholder={field.placeholder || t('system.common.selectPlaceholder')}
                searchPlaceholder={t('system.common.searchOptionsPlaceholder')}
                emptyText={t('system.common.noMatches')}
                disabled={disabled}
              />
              {showHelpText && field.helpText ? <div className="text-xs text-muted-foreground">{field.helpText}</div> : null}
            </div>
          )
        }

        if (field.type === 'boolean') {
          const selectedValue =
            typeof currentValue === 'boolean' ? (currentValue ? 'true' : 'false') : '__empty__'
          return (
            <div key={field.key} className="grid gap-2">
              <Label>{label}</Label>
              <Select
                value={selectedValue}
                onValueChange={(nextValue) => {
                  if (nextValue === '__empty__') {
                    updateField(field, null)
                    return
                  }
                  updateField(field, nextValue === 'true')
                }}
                disabled={disabled}
              >
                <SelectTrigger>
                  <SelectValue placeholder={field.placeholder || t('system.common.selectPlaceholder')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__empty__">{t('system.common.unselected')}</SelectItem>
                  <SelectItem value="true">{t('system.common.yes')}</SelectItem>
                  <SelectItem value="false">{t('system.common.no')}</SelectItem>
                </SelectContent>
              </Select>
              {showHelpText && field.helpText ? <div className="text-xs text-muted-foreground">{field.helpText}</div> : null}
            </div>
          )
        }

        return (
          <div key={field.key} className="grid gap-2">
            <Label>{label}</Label>
            <Input
              type={field.type === 'number' ? 'number' : field.type === 'date' ? 'date' : 'text'}
              value={
                field.type === 'number'
                  ? currentValue == null
                    ? ''
                    : String(currentValue)
                  : typeof currentValue === 'string'
                    ? currentValue
                    : ''
              }
              onChange={(e) => {
                if (field.type === 'number') {
                  const nextValue = e.target.value
                  updateField(field, nextValue === '' ? null : Number(nextValue))
                  return
                }
                updateField(field, e.target.value)
              }}
              placeholder={field.placeholder || undefined}
              disabled={disabled}
            />
            {showHelpText && field.helpText ? <div className="text-xs text-muted-foreground">{field.helpText}</div> : null}
          </div>
        )
      })}
    </div>
  )
}
