'use client'

export type UserProfileFieldType = 'text' | 'textarea' | 'number' | 'select' | 'multi_select' | 'date' | 'boolean'

export type UserProfileFieldOption = {
  label: string
  value: string
}

export type UserProfileFieldDefinition = {
  key: string
  label: string
  type: UserProfileFieldType
  required?: boolean
  enabled?: boolean
  placeholder?: string | null
  helpText?: string | null
  options?: UserProfileFieldOption[]
  listVisible?: boolean
  filterable?: boolean
  sort?: number
}

export type UserProfileFieldsConfig = {
  enabled?: boolean
  enforceOnRegister?: boolean
  enforceAfterLogin?: boolean
  version?: number
  fields?: UserProfileFieldDefinition[]
}

export type UserProfileMeta = {
  enabled?: boolean
  schemaVersion?: number
  completed?: boolean
  requiredKeys?: string[]
  missingRequiredKeys?: string[]
  lastCompletedAt?: string | null
  source?: string | null
}

export function normalizeProfileFieldKey(value: unknown): string {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/-/g, '_')
    .replace(/\s+/g, '_')
    .replace(/_+/g, '_')
}

function normalizeFieldOption(raw: unknown): UserProfileFieldOption | null {
  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
  const label = String(source.label || '').trim()
  const value = String(source.value || '').trim()
  if (!label || !value) return null
  return { label, value }
}

export function normalizeUserProfileField(raw: unknown): UserProfileFieldDefinition | null {
  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
  const key = normalizeProfileFieldKey(source.key)
  const label = String(source.label || '').trim()
  if (!key || !label) return null

  const type = String(source.type || 'text').trim() as UserProfileFieldType
  const optionsSource = Array.isArray(source.options) ? source.options : []
  const options = optionsSource.map(normalizeFieldOption).filter(Boolean) as UserProfileFieldOption[]

  return {
    key,
    label,
    type:
      type === 'textarea' ||
      type === 'number' ||
      type === 'select' ||
      type === 'multi_select' ||
      type === 'date' ||
      type === 'boolean'
        ? type
        : 'text',
    required: Boolean(source.required),
    enabled: source.enabled !== false,
    placeholder: String(source.placeholder || '').trim() || null,
    helpText: String(source.helpText || source.help_text || '').trim() || null,
    options,
    listVisible: Boolean(source.listVisible || source.list_visible),
    filterable: Boolean(source.filterable),
    sort: Number(source.sort || 0),
  }
}

export function normalizeUserProfileFieldsConfig(raw: unknown): UserProfileFieldsConfig {
  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
  const fieldsSource = Array.isArray(source.fields) ? source.fields : []
  const fields = fieldsSource.map(normalizeUserProfileField).filter(Boolean) as UserProfileFieldDefinition[]

  return {
    enabled: Boolean(source.enabled),
    enforceOnRegister: source.enforceOnRegister !== false,
    enforceAfterLogin: source.enforceAfterLogin !== false,
    version: Math.max(1, Number(source.version || 1)),
    fields: fields.sort((a, b) => (Number(a.sort || 0) - Number(b.sort || 0)) || a.key.localeCompare(b.key)),
  }
}

export function getEnabledUserProfileFields(config: UserProfileFieldsConfig | null | undefined) {
  const normalized = normalizeUserProfileFieldsConfig(config)
  return (normalized.fields || []).filter((field) => field.enabled !== false)
}

export function buildUserProfileFieldMap(config: UserProfileFieldsConfig | null | undefined) {
  return getEnabledUserProfileFields(config).reduce(
    (acc, field) => {
      acc[field.key] = field
      return acc
    },
    {} as Record<string, UserProfileFieldDefinition>,
  )
}

export function profileValueMissing(field: UserProfileFieldDefinition, value: unknown): boolean {
  if (value == null) return true
  if (field.type === 'multi_select') return !Array.isArray(value) || value.length === 0
  if (field.type === 'boolean') return false
  return !String(value).trim()
}

export function collectMissingRequiredProfileFields(
  config: UserProfileFieldsConfig | null | undefined,
  profile: Record<string, unknown> | null | undefined,
  options?: {
    enforceOnRegisterOnly?: boolean
  },
) {
  const normalized = normalizeUserProfileFieldsConfig(config)
  if (!normalized.enabled) return []
  if (options?.enforceOnRegisterOnly && !normalized.enforceOnRegister) return []

  const profileSource = profile || {}
  return getEnabledUserProfileFields(normalized).filter(
    (field) => field.required && profileValueMissing(field, profileSource[field.key]),
  )
}

export function parseFieldOptionsText(value: string): UserProfileFieldOption[] {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [rawValue, rawLabel] = line.split('|')
      const optionValue = String(rawValue || '').trim()
      const optionLabel = String(rawLabel || rawValue || '').trim()
      return optionValue && optionLabel ? { value: optionValue, label: optionLabel } : null
    })
    .filter(Boolean) as UserProfileFieldOption[]
}

export function stringifyFieldOptions(options: UserProfileFieldOption[] | null | undefined): string {
  return (options || []).map((item) => `${item.value}|${item.label}`).join('\n')
}

export function normalizeProfileMeta(raw: unknown): UserProfileMeta {
  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
  const requiredKeysSource = Array.isArray(source.requiredKeys)
    ? source.requiredKeys
    : Array.isArray(source.required_keys)
      ? source.required_keys
      : []
  const missingRequiredKeysSource = Array.isArray(source.missingRequiredKeys)
    ? source.missingRequiredKeys
    : Array.isArray(source.missing_required_keys)
      ? source.missing_required_keys
      : []
  return {
    enabled: Boolean(source.enabled),
    schemaVersion: Number(source.schemaVersion || source.schema_version || 1),
    completed: source.completed !== false,
    requiredKeys: requiredKeysSource.map((item) => String(item)),
    missingRequiredKeys: missingRequiredKeysSource.map((item) => String(item)),
    lastCompletedAt: source.lastCompletedAt ? String(source.lastCompletedAt) : null,
    source: source.source ? String(source.source) : null,
  }
}
