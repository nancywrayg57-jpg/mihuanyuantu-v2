'use client'

export type RegistrationBasicFieldConfig = {
  enabled?: boolean
  required?: boolean
}

export type RegistrationBasicFieldsConfig = {
  nickname?: RegistrationBasicFieldConfig
  email?: RegistrationBasicFieldConfig
  phone?: RegistrationBasicFieldConfig
}

function normalizeBasicField(raw: unknown, defaults: RegistrationBasicFieldConfig): RegistrationBasicFieldConfig {
  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
  const enabled = source.enabled === undefined ? defaults.enabled !== false : source.enabled !== false
  const required = Boolean(source.required)
  return {
    enabled: required ? true : enabled,
    required,
  }
}

export function normalizeRegistrationBasicFieldsConfig(raw: unknown): RegistrationBasicFieldsConfig {
  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
  return {
    nickname: normalizeBasicField(source.nickname, { enabled: false, required: false }),
    email: normalizeBasicField(source.email, { enabled: true, required: false }),
    phone: normalizeBasicField(source.phone, { enabled: true, required: false }),
  }
}

export function registrationFieldMode(field: RegistrationBasicFieldConfig | null | undefined): 'hidden' | 'optional' | 'required' {
  if (!field?.enabled) return 'hidden'
  return field.required ? 'required' : 'optional'
}

export function registrationFieldConfigFromMode(mode: 'hidden' | 'optional' | 'required'): RegistrationBasicFieldConfig {
  if (mode === 'hidden') return { enabled: false, required: false }
  if (mode === 'required') return { enabled: true, required: true }
  return { enabled: true, required: false }
}
