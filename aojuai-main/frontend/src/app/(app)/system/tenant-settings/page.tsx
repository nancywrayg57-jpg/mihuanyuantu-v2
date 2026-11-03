'use client'
import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, RefreshCcw } from 'lucide-react'
import { toast } from 'sonner'

import { SpeechSettingsShell } from '@/components/speech/speech-settings-shell'
import { AIRedactionCard } from '@/components/tenant/ai-redaction-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, apiFetch } from '@/lib/api'
import { useT } from '@/lib/i18n'
import { normalizeSpeechSettingsPanel } from '@/lib/system-settings-routes'
import {
  normalizeProfileFieldKey,
  normalizeUserProfileFieldsConfig,
  parseFieldOptionsText,
  stringifyFieldOptions,
  type UserProfileFieldDefinition,
  type UserProfileFieldsConfig,
} from '@/lib/user-profile-fields'
import { applySiteSeo } from '@/lib/seo'
import {
  FALLBACK_FEATURE_CATALOG,
  normalizeFeatureSwitches,
} from '@/lib/feature-switches'
import { DEFAULT_THEME_PRESET_KEY, THEME_PRESETS, applyThemePreset, resolveThemePreset } from '@/lib/theme-presets'
import {
  normalizeRegistrationBasicFieldsConfig,
  registrationFieldConfigFromMode,
  registrationFieldMode,
  type RegistrationBasicFieldsConfig,
} from '@/lib/registration-fields'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'

type VerificationConfig = {
  sms?: { enabled?: boolean }
  email?: { enabled?: boolean }
}

type FeatureSwitches = {
  modules: Record<string, boolean>
  capabilities: Record<string, boolean>
}

type TenantSettingsTab = 'profile' | 'registration' | 'invite' | 'features' | 'ai' | 'speech' | 'seo'

type TenantConfig = {
  theme?: string
  logo?: string | null
  timezone?: string
  seo?: {
    title?: string | null
    keywords?: string | null
    description?: string | null
  }
  appearance?: {
    primaryColor?: string | null
    defaultLocale?: string | null
  }
  registration?: {
    enabled?: boolean
    requireAudit?: boolean
    defaultRole?: string
    basicFields?: RegistrationBasicFieldsConfig
    invitation?: InvitationConfig
    userProfileFields?: UserProfileFieldsConfig
  }
  verification?: VerificationConfig
  featureSwitches?: FeatureSwitches
  feature_switches?: FeatureSwitches
}

type TenantProfile = {
  id: number
  name: string
  code: string
  description?: string | null
  contactName?: string | null
  contactPhone?: string | null
  contactEmail?: string | null
  config?: TenantConfig
  quota?: Record<string, unknown>
}

type TenantSettingsResponse = {
  config?: TenantConfig
  quota?: Record<string, unknown>
}

type InvitationConfig = {
  enabled?: boolean
  inviterRewardCredits?: number
  inviteeRewardCredits?: number
  rewardDelayDays?: number
  maxInvitesPerUser?: number
  inviteCodeCostCredits?: number
}

type TenantInviteLinkResponse = {
  inviteCode: string
  registerPath: string
  expiresAt?: string | null
  tenantCode?: string
  tenantName?: string
}

type RegistrationBasicFieldKey = 'nickname' | 'email' | 'phone'
type TFunction = ReturnType<typeof useT>

const REGISTRATION_BASIC_FIELD_ITEMS: Array<{
  key: RegistrationBasicFieldKey
  labelKey: string
  descriptionKey: string
}> = [
  {
    key: 'nickname',
    labelKey: 'system.auth.nickname',
    descriptionKey: 'system.tenantSettings.basicFieldNicknameDescription',
  },
  {
    key: 'email',
    labelKey: 'system.auth.email',
    descriptionKey: 'system.tenantSettings.basicFieldEmailDescription',
  },
  {
    key: 'phone',
    labelKey: 'system.auth.phone',
    descriptionKey: 'system.tenantSettings.basicFieldPhoneDescription',
  },
]

type AssistantTenantConfig = {
  enabled: boolean
  deductCredits: boolean
  creditsPerCall: number
  pointsTokenRatio: number
  baseUrl: string
  model: string
  temperature: number
  maxTokens: number
  stream: boolean
  apiKey: string
  apiKeyMasked: string
  apiKeySet: boolean
  capabilities: AssistantCapabilitySettings
  moduleSkillCatalog: AssistantModuleSkillCatalogModule[]
}

type AssistantModuleSkillRule = {
  skillId: string
  enabled: boolean
  rank: number
}

type AssistantModuleSkillGovernanceModule = {
  moduleCode: string
  skillRules: AssistantModuleSkillRule[]
}

type AssistantModuleSkillGovernance = {
  modules: AssistantModuleSkillGovernanceModule[]
}

type AssistantCapabilitySettings = {
  moduleSkillGovernance: AssistantModuleSkillGovernance
}

type AssistantModuleSkillCatalogItem = {
  skillId: string
  label: string
  description: string
  defaultRank: number
  scopeIds: string[]
}

type AssistantModuleSkillCatalogModule = {
  moduleCode: string
  moduleName: string
  skills: AssistantModuleSkillCatalogItem[]
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function normalizeAssistantModuleSkillCatalog(raw: unknown): AssistantModuleSkillCatalogModule[] {
  if (!Array.isArray(raw)) return []
  return raw
    .filter((item): item is Record<string, unknown> => isObjectRecord(item))
    .map((module) => {
      const skillsRaw = Array.isArray(module.skills) ? module.skills : []
      const skills = skillsRaw
        .filter((item): item is Record<string, unknown> => isObjectRecord(item))
        .map((skill, index) => ({
          skillId: String(skill.skillId || '').trim(),
          label: String(skill.label || skill.skillId || '').trim(),
          description: String(skill.description || '').trim(),
          defaultRank: Number(skill.defaultRank ?? index + 1) || index + 1,
          scopeIds: Array.isArray(skill.scopeIds)
            ? skill.scopeIds.map((item) => String(item || '').trim()).filter(Boolean)
            : [],
        }))
        .filter((skill) => skill.skillId)
        .sort((left, right) => left.defaultRank - right.defaultRank || left.label.localeCompare(right.label))
      return {
        moduleCode: String(module.moduleCode || '').trim(),
        moduleName: String(module.moduleName || module.moduleCode || '').trim(),
        skills,
      }
    })
    .filter((module) => module.moduleCode)
}

function buildDefaultAssistantModuleSkillGovernance(
  catalog: AssistantModuleSkillCatalogModule[],
): AssistantModuleSkillGovernance {
  return {
    modules: catalog.map((module) => ({
      moduleCode: module.moduleCode,
      skillRules: module.skills.map((skill, index) => ({
        skillId: skill.skillId,
        enabled: true,
        rank: skill.defaultRank || index + 1,
      })),
    })),
  }
}

function normalizeAssistantModuleSkillGovernance(
  raw: unknown,
  catalog: AssistantModuleSkillCatalogModule[],
): AssistantModuleSkillGovernance {
  const defaults = buildDefaultAssistantModuleSkillGovernance(catalog)
  if (!isObjectRecord(raw) || !Array.isArray(raw.modules)) {
    return defaults
  }

  const rawModuleMap = new Map<string, AssistantModuleSkillGovernanceModule>()
  raw.modules
    .filter((item): item is Record<string, unknown> => isObjectRecord(item))
    .forEach((module) => {
      const moduleCode = String(module.moduleCode || '').trim()
      if (!moduleCode || !Array.isArray(module.skillRules)) return
      const skillRules = module.skillRules
        .filter((item): item is Record<string, unknown> => isObjectRecord(item))
        .map((rule, index) => ({
          skillId: String(rule.skillId || '').trim(),
          enabled: rule.enabled !== false,
          rank: Number(rule.rank ?? index + 1) || index + 1,
        }))
        .filter((rule) => rule.skillId)
      rawModuleMap.set(moduleCode, {
        moduleCode,
        skillRules,
      })
    })

  return {
    modules: defaults.modules.map((module) => {
      const incomingModule = rawModuleMap.get(module.moduleCode)
      if (!incomingModule) return module
      const incomingRuleMap = new Map(incomingModule.skillRules.map((rule) => [rule.skillId, rule]))
      return {
        moduleCode: module.moduleCode,
        skillRules: module.skillRules.map((rule) => {
          const incomingRule = incomingRuleMap.get(rule.skillId)
          if (!incomingRule) return rule
          return {
            skillId: rule.skillId,
            enabled: incomingRule.enabled,
            rank: incomingRule.rank,
          }
        }),
      }
    }),
  }
}

const USER_PROFILE_FIELD_TYPE_OPTIONS: Array<{ value: UserProfileFieldDefinition['type']; labelKey: string }> = [
  { value: 'text', labelKey: 'system.tenantSettings.fieldTypeText' },
  { value: 'textarea', labelKey: 'system.tenantSettings.fieldTypeTextarea' },
  { value: 'number', labelKey: 'system.tenantSettings.fieldTypeNumber' },
  { value: 'select', labelKey: 'system.tenantSettings.fieldTypeSelect' },
  { value: 'multi_select', labelKey: 'system.tenantSettings.fieldTypeMultiSelect' },
  { value: 'date', labelKey: 'system.tenantSettings.fieldTypeDate' },
  { value: 'boolean', labelKey: 'system.tenantSettings.fieldTypeBoolean' },
]

function resolveTenantSettingsTab(value: string | null, options: { speechEnabled: boolean }): TenantSettingsTab {
  const normalized = String(value || '').trim().toLowerCase()
  if (normalized === 'registration') return 'registration'
  if (normalized === 'invite') return 'invite'
  if (normalized === 'features') return 'features'
  if (normalized === 'ai') return 'ai'
  if (normalized === 'speech' && options.speechEnabled) return 'speech'
  if (normalized === 'seo') return 'seo'
  return 'profile'
}

function isI18nKey(value: string) {
  return value.startsWith('common.') || value.startsWith('system.') || value.startsWith('auth.')
}

function resolveMaybeI18n(value: string, t: TFunction) {
  return isI18nKey(value) ? t(value) : value
}

function formatPrefixPreview(prefixes: string[] | undefined, t: TFunction, limit = 3): string {
  if (!Array.isArray(prefixes) || prefixes.length === 0) return ''
  const normalized = prefixes
    .map((item) => {
      const value = String(item || '').trim()
      if (value === '/speech' || value === '/system/speech-settings') {
        return '/system/tenant-settings?tab=speech'
      }
      if (value === '/system/ai-settings') {
        return '/system/tenant-settings?tab=ai'
      }
      return value
    })
    .filter(Boolean)
    .filter((item, index, items) => items.indexOf(item) === index)
  if (!normalized.length) return ''
  const visible = normalized.slice(0, limit)
  const suffix = normalized.length > limit
    ? t('system.tenantSettings.moreItems').replace('{n}', String(normalized.length - limit))
    : ''
  return `${visible.join(', ')}${suffix}`
}

function normalizeInvitationConfig(raw: unknown): InvitationConfig {
  const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
  return {
    enabled: Boolean(source.enabled),
    inviterRewardCredits: Number(source.inviterRewardCredits || source.inviter_reward_credits || 0),
    inviteeRewardCredits: Number(source.inviteeRewardCredits || source.invitee_reward_credits || 0),
    rewardDelayDays: Number(source.rewardDelayDays || source.reward_delay_days || 0),
    maxInvitesPerUser: Number(source.maxInvitesPerUser ?? source.max_invites_per_user ?? 50),
    inviteCodeCostCredits: Number(source.inviteCodeCostCredits || source.invite_code_cost_credits || 0),
  }
}

function resolveInviteUrl(registerPath: string | null | undefined, inviteCode: string): string {
  const path = registerPath || `/register?invite=${encodeURIComponent(inviteCode)}`
  if (typeof window === 'undefined') return path
  return new URL(path, window.location.origin).toString()
}

function createEmptyProfileField(index: number, t: TFunction): UserProfileFieldDefinition {
  return {
    key: `field_${index}`,
    label: t('system.tenantSettings.fieldNumber').replace('{n}', String(index)),
    type: 'text',
    required: false,
    enabled: true,
    placeholder: '',
    helpText: '',
    options: [],
    listVisible: false,
    filterable: false,
    sort: index * 10,
  }
}

function createStarterProfileField(t: TFunction): UserProfileFieldDefinition {
  return {
    key: 'company',
    label: t('system.tenantSettings.company'),
    type: 'text',
    required: true,
    enabled: true,
    placeholder: t('system.tenantSettings.companyPlaceholder'),
    helpText: t('system.tenantSettings.companyHelp'),
    options: [],
    listVisible: true,
    filterable: true,
    sort: 10,
  }
}

function createBasicProfileFieldPreset(t: TFunction): UserProfileFieldDefinition[] {
  return [
    createStarterProfileField(t),
    {
      key: 'department',
      label: t('system.tenantSettings.department'),
      type: 'text',
      required: true,
      enabled: true,
      placeholder: t('system.tenantSettings.departmentPlaceholder'),
      helpText: t('system.tenantSettings.departmentHelp'),
      options: [],
      listVisible: true,
      filterable: true,
      sort: 20,
    },
    {
      key: 'job_title',
      label: t('system.tenantSettings.jobTitle'),
      type: 'text',
      required: false,
      enabled: true,
      placeholder: t('system.tenantSettings.jobTitlePlaceholder'),
      helpText: t('system.tenantSettings.jobTitleHelp'),
      options: [],
      listVisible: true,
      filterable: true,
      sort: 30,
    },
  ]
}

function getUserProfileFieldTypeLabel(type: UserProfileFieldDefinition['type'], t: TFunction): string {
  const option = USER_PROFILE_FIELD_TYPE_OPTIONS.find((item) => item.value === type)
  return option ? t(option.labelKey) : type
}

export default function TenantSettingsPage() {
  const t = useT()
  const { session } = useAuth()
  const { featureCatalog } = useTenant()
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const browserTimezone =
    typeof Intl !== 'undefined' ? Intl.DateTimeFormat().resolvedOptions().timeZone || '' : ''

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tenantInviteExpiresIn, setTenantInviteExpiresIn] = useState(7)
  const [generatedTenantInvite, setGeneratedTenantInvite] = useState<TenantInviteLinkResponse | null>(null)
  const [profile, setProfile] = useState<TenantProfile | null>(null)
  const [settings, setSettings] = useState<TenantSettingsResponse | null>(null)
  const [activeTab, setActiveTab] = useState<TenantSettingsTab>('profile')
  const [assistantConfig, setAssistantConfig] = useState<AssistantTenantConfig>({
    enabled: false,
    deductCredits: false,
    creditsPerCall: 1,
    pointsTokenRatio: 1000,
    baseUrl: '',
    model: '',
    temperature: 0.7,
    maxTokens: 2048,
    stream: true,
    apiKey: '',
    apiKeyMasked: '',
    apiKeySet: false,
    capabilities: {
      moduleSkillGovernance: {
        modules: [],
      },
    },
    moduleSkillCatalog: [],
  })
  const [assistantSaving, setAssistantSaving] = useState(false)

  const activeCatalog = useMemo(() => featureCatalog || FALLBACK_FEATURE_CATALOG, [featureCatalog])
  const speechModuleEnabled = useMemo(
    () => activeCatalog.modules.some((item) => item.code === 'speech'),
    [activeCatalog],
  )
  const registrationBasicFields = useMemo(
    () => normalizeRegistrationBasicFieldsConfig(settings?.config?.registration?.basicFields),
    [settings],
  )
  const profileFieldsConfig = useMemo(
    () => normalizeUserProfileFieldsConfig(settings?.config?.registration?.userProfileFields),
    [settings],
  )
  const configuredProfileFields = profileFieldsConfig.fields || []
  const [expandedProfileFieldIndex, setExpandedProfileFieldIndex] = useState<number | null>(null)

  useEffect(() => {
    setExpandedProfileFieldIndex((current) => {
      if (configuredProfileFields.length === 0) return null
      if (current === null) return null
      return current >= configuredProfileFields.length ? configuredProfileFields.length - 1 : current
    })
  }, [configuredProfileFields.length])

  function appendProfileField() {
    setExpandedProfileFieldIndex((current) => current ?? configuredProfileFields.length)
    setSettings((s) => {
      if (!s) return s
      const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
      const nextField = createEmptyProfileField((current.fields || []).length + 1, t)
      return {
        ...s,
        config: {
          ...(s.config || {}),
          registration: {
            ...(s.config?.registration || {}),
            userProfileFields: {
              ...current,
              enabled: true,
              fields: [...(current.fields || []), nextField],
            },
          },
        },
      }
    })
  }

  function applyProfileFieldPreset() {
    setExpandedProfileFieldIndex(0)
    setSettings((s) => {
      if (!s) return s
      const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
      return {
        ...s,
        config: {
          ...(s.config || {}),
          registration: {
            ...(s.config?.registration || {}),
            userProfileFields: {
              ...current,
              enabled: true,
              fields: createBasicProfileFieldPreset(t),
            },
          },
        },
      }
    })
  }

  function handleProfileFieldsEnabledChange(checked: boolean | 'indeterminate') {
    const enabled = Boolean(checked)
    if (enabled && configuredProfileFields.length === 0) {
      setExpandedProfileFieldIndex(0)
    }
    if (!enabled) {
      setExpandedProfileFieldIndex(null)
    }
    setSettings((s) => {
      if (!s) return s
      const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
      const currentFields = current.fields || []
      return {
        ...s,
        config: {
          ...(s.config || {}),
          registration: {
            ...(s.config?.registration || {}),
            userProfileFields: {
              ...current,
              enabled,
              fields: enabled && currentFields.length === 0 ? [createStarterProfileField(t)] : currentFields,
            },
          },
        },
      }
    })
  }

  const requestedTab = searchParams.get('tab')
  const requestedSpeechPanel = searchParams.get('panel')
  const activeSpeechPanel = normalizeSpeechSettingsPanel(requestedSpeechPanel)

  useEffect(() => {
    setActiveTab(resolveTenantSettingsTab(requestedTab, { speechEnabled: speechModuleEnabled }))
  }, [requestedTab, speechModuleEnabled])

  function handleTabChange(value: string) {
    const nextTab = resolveTenantSettingsTab(value, { speechEnabled: speechModuleEnabled })
    setActiveTab(nextTab)
    const nextParams = new URLSearchParams(searchParams.toString())
    if (nextTab === 'profile') {
      nextParams.delete('tab')
    } else {
      nextParams.set('tab', nextTab)
    }
    if (nextTab !== 'speech') {
      nextParams.delete('panel')
    }
    const query = nextParams.toString()
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false })
  }

  async function loadAssistantConfig(currentSession = session) {
    if (!currentSession) return
    const data = await apiFetch<Record<string, unknown>>('/api/v1/assistant/config', {
      session: currentSession,
    }).catch(() => null)
    if (!data) return
    const moduleSkillCatalog = normalizeAssistantModuleSkillCatalog(data.moduleSkillCatalog)
    const capabilitiesRaw = isObjectRecord(data.capabilities) ? data.capabilities : {}
    const moduleSkillGovernance = normalizeAssistantModuleSkillGovernance(
      capabilitiesRaw.moduleSkillGovernance,
      moduleSkillCatalog,
    )
    setAssistantConfig({
      enabled: Boolean(data.enabled ?? false),
      deductCredits: Boolean(data.deductCredits ?? false),
      creditsPerCall: Number(data.creditsPerCall ?? 1),
      pointsTokenRatio: Number(data.pointsTokenRatio ?? 1000),
      baseUrl: String(data.baseUrl || ''),
      model: String(data.model || ''),
      temperature: Number(data.temperature ?? 0.7),
      maxTokens: Number(data.maxTokens ?? 2048),
      stream: Boolean(data.stream ?? true),
      apiKey: '',
      apiKeyMasked: String(data.apiKeyMasked || ''),
      apiKeySet: Boolean(data.apiKeySet ?? false),
      capabilities: {
        moduleSkillGovernance,
      },
      moduleSkillCatalog,
    })
  }

  async function saveAssistantConfig() {
    if (!session) return
    setAssistantSaving(true)
    const id = toast.loading(t('system.tenantSettings.savingAiConfig'))
    try {
      const baseUrl = assistantConfig.baseUrl.trim()
      const model = assistantConfig.model.trim()
      const apiKey = assistantConfig.apiKey.trim()
      const payload: Record<string, unknown> = {
        enabled: assistantConfig.enabled,
        deductCredits: assistantConfig.deductCredits,
        creditsPerCall: assistantConfig.creditsPerCall,
        pointsTokenRatio: assistantConfig.pointsTokenRatio,
        baseUrl: baseUrl || null,
        temperature: assistantConfig.temperature,
        maxTokens: assistantConfig.maxTokens,
        stream: assistantConfig.stream,
        capabilities: {
          moduleSkillGovernance: assistantConfig.capabilities.moduleSkillGovernance,
        },
      }
      if (model) {
        payload.model = model
      }
      if (apiKey) {
        payload.apiKey = apiKey
      }
      await apiFetch('/api/v1/assistant/config', {
        method: 'PUT',
        session,
        body: JSON.stringify(payload),
      })
      toast.success(t('system.tenantSettings.aiConfigSaved'), { id })
      await loadAssistantConfig(session)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t('system.tenantSettings.saveAiConfigFailed'), { id })
    } finally {
      setAssistantSaving(false)
    }
  }

  function updateAssistantModuleSkillRule(
    moduleCode: string,
    skillId: string,
    patch: Partial<AssistantModuleSkillRule>,
  ) {
    setAssistantConfig((prev) => ({
      ...prev,
      capabilities: {
        ...prev.capabilities,
        moduleSkillGovernance: {
          modules: prev.capabilities.moduleSkillGovernance.modules.map((module) => {
            if (module.moduleCode !== moduleCode) return module
            return {
              ...module,
              skillRules: module.skillRules
                .map((rule) => {
                  if (rule.skillId !== skillId) return rule
                  return {
                    ...rule,
                    ...patch,
                  }
                })
                .sort((left, right) => left.rank - right.rank || left.skillId.localeCompare(right.skillId)),
            }
          }),
        },
      },
    }))
  }

  async function load() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const [profileRes, settingsRes] = await Promise.all([
        apiFetch<TenantProfile>('/api/v1/tenant/profile', { session }),
        apiFetch<TenantSettingsResponse>('/api/v1/tenant/profile/settings', { session }),
      ])

      const catalog = featureCatalog || FALLBACK_FEATURE_CATALOG

      const normalizedFeatureSwitches = normalizeFeatureSwitches(
        catalog,
        settingsRes.config?.featureSwitches || settingsRes.config?.feature_switches,
        settingsRes.config?.verification,
      )

      const mergedSettings: TenantSettingsResponse = {
        ...settingsRes,
        config: {
          ...(settingsRes.config || {}),
          registration: {
            ...(settingsRes.config?.registration || {}),
            basicFields: normalizeRegistrationBasicFieldsConfig(settingsRes.config?.registration?.basicFields),
            invitation: normalizeInvitationConfig(settingsRes.config?.registration?.invitation),
            userProfileFields: normalizeUserProfileFieldsConfig(settingsRes.config?.registration?.userProfileFields),
          },
          featureSwitches: normalizedFeatureSwitches,
          verification: {
            ...(settingsRes.config?.verification || {}),
            sms: {
              ...(settingsRes.config?.verification?.sms || {}),
              enabled: Boolean(normalizedFeatureSwitches.capabilities.verification_sms),
            },
            email: {
              ...(settingsRes.config?.verification?.email || {}),
              enabled: Boolean(normalizedFeatureSwitches.capabilities.verification_email),
            },
          },
        },
      }

      setProfile(profileRes)
      setSettings(mergedSettings)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('system.common.loadFailed'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  useEffect(() => {
    if (!session) return
    if (activeTab !== 'ai') return
    if (!settings?.config?.featureSwitches?.modules?.assistant) return
    void loadAssistantConfig(session)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, session?.accessToken, settings?.config?.featureSwitches])

  if (!session) return null

  const moduleEnabledCount = Object.values(settings?.config?.featureSwitches?.modules || {}).filter(Boolean).length
  const moduleTotal = activeCatalog.modules.length
  const capabilityEnabledCount = Object.values(settings?.config?.featureSwitches?.capabilities || {}).filter(Boolean).length
  const capabilityTotal = activeCatalog.capabilities.length

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>{t('system.tenantSettings.title')}</CardTitle>
          <CardDescription>{t('system.tenantSettings.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={load} disabled={loading}>
              <RefreshCcw className="mr-2 h-4 w-4" />
              {t('common.refresh')}
            </Button>
            {profile ? (
              <div className="text-sm text-muted-foreground">
                {t('system.tenantSettings.currentTenant')}: <span className="font-medium text-foreground">{profile.name}</span>{' '}
                <Badge variant="outline" className="ml-2">
                  {profile.code}
                </Badge>
              </div>
            ) : null}
          </div>
          {error ? <div className="text-sm text-destructive">{error}</div> : null}
        </CardContent>
      </Card>

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList className="flex w-full flex-wrap justify-start">
          <TabsTrigger value="profile">{t('system.tenantSettings.tabProfile')}</TabsTrigger>
          <TabsTrigger value="registration">{t('system.tenantSettings.tabRegistration')}</TabsTrigger>
          <TabsTrigger value="invite">{t('system.tenantSettings.tabInvite')}</TabsTrigger>
          <TabsTrigger value="features">{t('system.tenantSettings.tabFeatures')}</TabsTrigger>
          <TabsTrigger value="ai">{t('system.tenantSettings.tabAi')}</TabsTrigger>
          {speechModuleEnabled ? <TabsTrigger value="speech">{t('system.tenantSettings.tabSpeech')}</TabsTrigger> : null}
          <TabsTrigger value="seo">{t('system.tenantSettings.tabSeo')}</TabsTrigger>
        </TabsList>

        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle>{t('system.tenantSettings.profileTitle')}</CardTitle>
              <CardDescription>{t('system.tenantSettings.profileDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2 md:col-span-2">
                <Label>{t('system.tenantSettings.tenantName')}</Label>
                <Input
                  value={profile?.name || ''}
                  onChange={(e) => setProfile((s) => (s ? { ...s, name: e.target.value } : s))}
                />
              </div>
              <div className="grid gap-2 md:col-span-2">
                <Label>{t('common.description')}</Label>
                <Textarea
                  value={profile?.description || ''}
                  onChange={(e) => setProfile((s) => (s ? { ...s, description: e.target.value } : s))}
                />
              </div>
              <div className="grid gap-2">
                <Label>{t('system.tenantSettings.contactName')}</Label>
                <Input
                  value={profile?.contactName || ''}
                  onChange={(e) => setProfile((s) => (s ? { ...s, contactName: e.target.value } : s))}
                />
              </div>
              <div className="grid gap-2">
                <Label>{t('system.tenantSettings.contactPhone')}</Label>
                <Input
                  value={profile?.contactPhone || ''}
                  onChange={(e) => setProfile((s) => (s ? { ...s, contactPhone: e.target.value } : s))}
                />
              </div>
              <div className="grid gap-2 md:col-span-2">
                <Label>{t('system.tenantSettings.contactEmail')}</Label>
                <Input
                  value={profile?.contactEmail || ''}
                  onChange={(e) => setProfile((s) => (s ? { ...s, contactEmail: e.target.value } : s))}
                />
              </div>
              <div className="grid gap-2 md:col-span-2">
                <Label>{t('system.tenantSettings.timezone')}</Label>
                <Input
                  placeholder={t('system.tenantSettings.timezonePlaceholder')}
                  value={settings?.config?.timezone || 'UTC'}
                  onChange={(e) =>
                    setSettings((s) =>
                      s
                        ? {
                            ...s,
                            config: {
                              ...(s.config || {}),
                              timezone: e.target.value,
                            },
                          }
                        : s,
                    )
                  }
                />
                <div className="text-xs text-muted-foreground">
                  {t('system.tenantSettings.timezoneHint')}
                  {browserTimezone ? (
                    <Button
                      type="button"
                      variant="link"
                      className="ml-1 h-auto p-0 text-xs"
                      onClick={() =>
                        setSettings((s) =>
                          s
                            ? {
                                ...s,
                                config: {
                                  ...(s.config || {}),
                                  timezone: browserTimezone,
                                },
                              }
                            : s,
                        )
                      }
                    >
                      {t('system.tenantSettings.useBrowserTimezone').replace('{timezone}', browserTimezone)}
                    </Button>
                  ) : null}
                </div>
              </div>

              <div className="flex items-center gap-2 md:col-span-2">
                <Button
                  onClick={async () => {
                    if (!session || !profile || !settings) return
                    setError(null)
                    const id = toast.loading(t('system.tenantSettings.savingProfile'))
                    try {
                      await Promise.all([
                        apiFetch('/api/v1/tenant/profile', {
                          method: 'PUT',
                          session,
                          body: JSON.stringify({
                            name: profile.name,
                            description: profile.description || undefined,
                            contactName: profile.contactName || undefined,
                            contactPhone: profile.contactPhone || undefined,
                            contactEmail: profile.contactEmail || undefined,
                          }),
                        }),
                        apiFetch('/api/v1/tenant/profile/settings', {
                          method: 'PUT',
                          session,
                          body: JSON.stringify({
                            timezone: settings.config?.timezone || 'UTC',
                          }),
                        }),
                      ])
                      toast.success(t('system.tenantSettings.profileSaved'), { id })
                      await load()
                    } catch (err) {
                      const message = err instanceof ApiError ? err.message : t('system.common.saveFailed')
                      setError(message)
                      toast.error(message, { id })
                    }
                  }}
                  disabled={loading || !profile || !settings}
                >
                  {t('common.save')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="registration">
          <Card>
            <CardHeader>
              <CardTitle>{t('system.tenantSettings.registrationTitle')}</CardTitle>
              <CardDescription>{t('system.tenantSettings.registrationDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={Boolean(settings?.config?.registration?.enabled)}
                  onCheckedChange={(v) =>
                    setSettings((s) =>
                      s
                        ? {
                            ...s,
                            config: {
                              ...(s.config || {}),
                              registration: {
                                ...(s.config?.registration || {}),
                                enabled: Boolean(v),
                              },
                            },
                          }
                        : s,
                    )
                  }
                />
                {t('system.tenantSettings.allowPublicRegistration')}
              </label>
              <div className="text-xs text-muted-foreground">
                {t('system.tenantSettings.publicRegistrationHint')}
              </div>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={Boolean(settings?.config?.registration?.requireAudit)}
                  onCheckedChange={(v) =>
                    setSettings((s) =>
                      s
                        ? {
                            ...s,
                            config: {
                              ...(s.config || {}),
                              registration: {
                                ...(s.config?.registration || {}),
                                requireAudit: Boolean(v),
                              },
                            },
                          }
                        : s,
                    )
                  }
                />
                {t('system.tenantSettings.requireRegistrationAudit')}
              </label>
              <div className="grid gap-2 md:max-w-md">
                <Label>{t('system.tenantSettings.defaultRole')}</Label>
                <Input
                  value={settings?.config?.registration?.defaultRole || 'user'}
                  onChange={(e) =>
                    setSettings((s) =>
                      s
                        ? {
                            ...s,
                            config: {
                              ...(s.config || {}),
                              registration: {
                                ...(s.config?.registration || {}),
                                defaultRole: e.target.value,
                              },
                            },
                          }
                        : s,
                    )
                  }
                />
              </div>

              <div className="grid gap-3 rounded-md border p-4">
                <div>
                  <div className="text-sm font-medium">{t('system.tenantSettings.basicRegistrationFields')}</div>
                  <div className="text-xs text-muted-foreground">
                    {t('system.tenantSettings.basicRegistrationFieldsHint')}
                  </div>
                </div>

                <div className="grid gap-3 rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">{t('auth.username')}</Badge>
                    <span>{t('system.tenantSettings.fixedRequiredField')}</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">{t('auth.password')}</Badge>
                    <span>{t('system.tenantSettings.fixedPasswordField')}</span>
                  </div>
                </div>

                <div className="grid gap-4">
                  {REGISTRATION_BASIC_FIELD_ITEMS.map((field) => (
                    <div
                      key={field.key}
                      className="grid gap-3 rounded-md border p-3 md:grid-cols-[120px_minmax(0,1fr)_160px] md:items-center"
                    >
                      <div className="text-sm font-medium">{t(field.labelKey)}</div>
                      <div className="text-xs text-muted-foreground">{t(field.descriptionKey)}</div>
                      <Select
                        value={registrationFieldMode(registrationBasicFields[field.key])}
                        onValueChange={(mode) =>
                          setSettings((s) =>
                            s
                              ? {
                                  ...s,
                                  config: {
                                    ...(s.config || {}),
                                    registration: {
                                      ...(s.config?.registration || {}),
                                      basicFields: {
                                        ...normalizeRegistrationBasicFieldsConfig(s.config?.registration?.basicFields),
                                        [field.key]: registrationFieldConfigFromMode(
                                          mode as 'hidden' | 'optional' | 'required',
                                        ),
                                      },
                                    },
                                  },
                                }
                              : s,
                          )
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="hidden">{t('system.tenantSettings.fieldModeHidden')}</SelectItem>
                          <SelectItem value="optional">{t('system.tenantSettings.fieldModeOptional')}</SelectItem>
                          <SelectItem value="required">{t('system.tenantSettings.fieldModeRequired')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid gap-3 rounded-md border p-4">
                <div>
                  <div className="text-sm font-medium">{t('system.tenantSettings.invitationRegistration')}</div>
                  <div className="text-xs text-muted-foreground">
                    {t('system.tenantSettings.invitationRegistrationHint')}
                  </div>
                </div>

                <label className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={Boolean(settings?.config?.registration?.invitation?.enabled)}
                    onCheckedChange={(v) =>
                      setSettings((s) =>
                        s
                          ? {
                              ...s,
                              config: {
                                ...(s.config || {}),
                                registration: {
                                  ...(s.config?.registration || {}),
                                  invitation: {
                                    ...normalizeInvitationConfig(s.config?.registration?.invitation),
                                    enabled: Boolean(v),
                                  },
                                },
                              },
                            }
                          : s,
                      )
                    }
                  />
                  {t('system.tenantSettings.enableInvitationRegistration')}
                </label>

                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  <div className="grid gap-2">
                    <Label>{t('system.tenantSettings.inviterRewardCredits')}</Label>
                    <Input
                      type="number"
                      min={0}
                      value={settings?.config?.registration?.invitation?.inviterRewardCredits || 0}
                      onChange={(e) =>
                        setSettings((s) =>
                          s
                            ? {
                                ...s,
                                config: {
                                  ...(s.config || {}),
                                  registration: {
                                    ...(s.config?.registration || {}),
                                    invitation: {
                                      ...normalizeInvitationConfig(s.config?.registration?.invitation),
                                      inviterRewardCredits: Number(e.target.value || 0),
                                    },
                                  },
                                },
                              }
                            : s,
                        )
                      }
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>{t('system.tenantSettings.inviteeRewardCredits')}</Label>
                    <Input
                      type="number"
                      min={0}
                      value={settings?.config?.registration?.invitation?.inviteeRewardCredits || 0}
                      onChange={(e) =>
                        setSettings((s) =>
                          s
                            ? {
                                ...s,
                                config: {
                                  ...(s.config || {}),
                                  registration: {
                                    ...(s.config?.registration || {}),
                                    invitation: {
                                      ...normalizeInvitationConfig(s.config?.registration?.invitation),
                                      inviteeRewardCredits: Number(e.target.value || 0),
                                    },
                                  },
                                },
                              }
                            : s,
                        )
                      }
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>{t('system.tenantSettings.rewardDelayDays')}</Label>
                    <Input
                      type="number"
                      min={0}
                      value={settings?.config?.registration?.invitation?.rewardDelayDays || 0}
                      onChange={(e) =>
                        setSettings((s) =>
                          s
                            ? {
                                ...s,
                                config: {
                                  ...(s.config || {}),
                                  registration: {
                                    ...(s.config?.registration || {}),
                                    invitation: {
                                      ...normalizeInvitationConfig(s.config?.registration?.invitation),
                                      rewardDelayDays: Number(e.target.value || 0),
                                    },
                                  },
                                },
                              }
                            : s,
                        )
                      }
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>{t('system.tenantSettings.maxInvitesPerUser')}</Label>
                    <Input
                      type="number"
                      min={0}
                      value={settings?.config?.registration?.invitation?.maxInvitesPerUser || 0}
                      onChange={(e) =>
                        setSettings((s) =>
                          s
                            ? {
                                ...s,
                                config: {
                                  ...(s.config || {}),
                                  registration: {
                                    ...(s.config?.registration || {}),
                                    invitation: {
                                      ...normalizeInvitationConfig(s.config?.registration?.invitation),
                                      maxInvitesPerUser: Number(e.target.value || 0),
                                    },
                                  },
                                },
                              }
                            : s,
                        )
                      }
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>{t('system.tenantSettings.inviteCodeCostCredits')}</Label>
                    <Input
                      type="number"
                      min={0}
                      value={settings?.config?.registration?.invitation?.inviteCodeCostCredits || 0}
                      onChange={(e) =>
                        setSettings((s) =>
                          s
                            ? {
                                ...s,
                                config: {
                                  ...(s.config || {}),
                                  registration: {
                                    ...(s.config?.registration || {}),
                                    invitation: {
                                      ...normalizeInvitationConfig(s.config?.registration?.invitation),
                                      inviteCodeCostCredits: Number(e.target.value || 0),
                                    },
                                  },
                                },
                              }
                            : s,
                        )
                      }
                    />
                  </div>
                </div>
              </div>

              <div className="grid gap-3 rounded-md border p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium">{t('system.tenantSettings.userProfileFields')}</div>
                    <div className="text-xs text-muted-foreground">
                      {t('system.tenantSettings.userProfileFieldsHint')}
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={appendProfileField}
                  >
                    {t('system.tenantSettings.addField')}
                  </Button>
                </div>

                <label className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={Boolean(profileFieldsConfig.enabled)}
                    onCheckedChange={handleProfileFieldsEnabledChange}
                  />
                  {t('system.tenantSettings.enableCustomProfileFields')}
                </label>

                <div className="grid gap-4 md:grid-cols-2">
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={Boolean(profileFieldsConfig.enforceOnRegister)}
                      onCheckedChange={(checked) =>
                        setSettings((s) =>
                          s
                            ? {
                                ...s,
                                config: {
                                  ...(s.config || {}),
                                  registration: {
                                    ...(s.config?.registration || {}),
                                    userProfileFields: {
                                      ...normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields),
                                      enforceOnRegister: Boolean(checked),
                                    },
                                  },
                                },
                              }
                            : s,
                        )
                      }
                    />
                    {t('system.tenantSettings.enforceRequiredOnRegister')}
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={Boolean(profileFieldsConfig.enforceAfterLogin)}
                      onCheckedChange={(checked) =>
                        setSettings((s) =>
                          s
                            ? {
                                ...s,
                                config: {
                                  ...(s.config || {}),
                                  registration: {
                                    ...(s.config?.registration || {}),
                                    userProfileFields: {
                                      ...normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields),
                                      enforceAfterLogin: Boolean(checked),
                                    },
                                  },
                                },
                              }
                            : s,
                        )
                      }
                    />
                    {t('system.tenantSettings.enforceRequiredAfterLogin')}
                  </label>
                </div>

                {configuredProfileFields.length === 0 ? (
                  <div className="grid gap-3 rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                    <div>
                      {t('system.tenantSettings.noProfileFieldsHint')}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" size="sm" onClick={appendProfileField}>
                        {t('system.tenantSettings.addFirstField')}
                      </Button>
                      <Button type="button" variant="outline" size="sm" onClick={applyProfileFieldPreset}>
                        {t('system.tenantSettings.insertBasicProfileTemplate')}
                      </Button>
                    </div>
                  </div>
                ) : null}

                <div className="grid gap-4">
                  {configuredProfileFields.map((field, index) => {
                    const expanded = expandedProfileFieldIndex === index
                    const fieldTitle = field.label?.trim() || t('system.tenantSettings.fieldNumber').replace('{n}', String(index + 1))
                    const fieldKey = field.key?.trim() || t('system.tenantSettings.keyUnset')
                    const helperText = field.helpText?.trim() || field.placeholder?.trim() || t('system.tenantSettings.descriptionUnset')
                    return (
                    <div key={`${field.key}:${index}`} className="grid gap-4 rounded-md border p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <button
                          type="button"
                          className="flex min-w-0 flex-1 items-start gap-3 text-left"
                          onClick={() => setExpandedProfileFieldIndex((current) => (current === index ? null : index))}
                        >
                          {expanded ? (
                            <ChevronDown className="mt-0.5 h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="mt-0.5 h-4 w-4 text-muted-foreground" />
                          )}
                          <div className="grid min-w-0 gap-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-sm font-medium">
                                {t('system.tenantSettings.fieldSummary')
                                  .replace('{n}', String(index + 1))
                                  .replace('{name}', fieldTitle)}
                              </span>
                              <Badge variant="secondary">{getUserProfileFieldTypeLabel(field.type, t)}</Badge>
                              {field.required ? <Badge variant="outline">{t('system.tenantSettings.fieldModeRequired')}</Badge> : null}
                              {field.enabled ? (
                                <Badge variant="outline">{t('system.tenantSettings.enabledBadge')}</Badge>
                              ) : (
                                <Badge variant="outline">{t('system.tenantSettings.disabledBadge')}</Badge>
                              )}
                              {field.listVisible ? <Badge variant="outline">{t('system.tenantSettings.listVisible')}</Badge> : null}
                              {field.filterable ? <Badge variant="outline">{t('system.tenantSettings.filterable')}</Badge> : null}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              Key: {fieldKey} · {helperText}
                            </div>
                          </div>
                        </button>
                        <div className="flex items-center gap-2">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setExpandedProfileFieldIndex((current) => (current === index ? null : index))}
                          >
                            {expanded ? t('system.tenantSettings.collapse') : t('system.tenantSettings.expand')}
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setExpandedProfileFieldIndex((current) => {
                                if (current === null) return null
                                if (current === index) return null
                                return current > index ? current - 1 : current
                              })
                              setSettings((s) => {
                                if (!s) return s
                                const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
                                return {
                                  ...s,
                                  config: {
                                    ...(s.config || {}),
                                    registration: {
                                      ...(s.config?.registration || {}),
                                      userProfileFields: {
                                        ...current,
                                        fields: (current.fields || []).filter((_, currentIndex) => currentIndex !== index),
                                      },
                                    },
                                  },
                                }
                              })
                            }}
                          >
                            {t('system.tenantSettings.deleteField')}
                          </Button>
                        </div>
                      </div>

                      {expanded ? (
                        <>
                      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <div className="grid gap-2">
                          <Label>{t('system.tenantSettings.fieldKey')}</Label>
                          <Input
                            value={field.key}
                            onChange={(e) =>
                              setSettings((s) => {
                                if (!s) return s
                                const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
                                const fields = [...(current.fields || [])]
                                fields[index] = {
                                  ...fields[index],
                                  key: normalizeProfileFieldKey(e.target.value),
                                }
                                return {
                                  ...s,
                                  config: {
                                    ...(s.config || {}),
                                    registration: {
                                      ...(s.config?.registration || {}),
                                      userProfileFields: {
                                        ...current,
                                        fields,
                                      },
                                    },
                                  },
                                }
                              })
                            }
                            placeholder="company"
                          />
                        </div>
                        <div className="grid gap-2">
                          <Label>{t('system.tenantSettings.fieldName')}</Label>
                          <Input
                            value={field.label}
                            onChange={(e) =>
                              setSettings((s) => {
                                if (!s) return s
                                const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
                                const fields = [...(current.fields || [])]
                                fields[index] = {
                                  ...fields[index],
                                  label: e.target.value,
                                }
                                return {
                                  ...s,
                                  config: {
                                    ...(s.config || {}),
                                    registration: {
                                      ...(s.config?.registration || {}),
                                      userProfileFields: {
                                        ...current,
                                        fields,
                                      },
                                    },
                                  },
                                }
                              })
                            }
                            placeholder={t('system.tenantSettings.company')}
                          />
                        </div>
                        <div className="grid gap-2">
                          <Label>{t('system.tenantSettings.fieldType')}</Label>
                          <Select
                            value={field.type}
                            onValueChange={(nextValue) =>
                              setSettings((s) => {
                                if (!s) return s
                                const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
                                const fields = [...(current.fields || [])]
                                fields[index] = {
                                  ...fields[index],
                                  type: nextValue as UserProfileFieldDefinition['type'],
                                  options:
                                    nextValue === 'select' || nextValue === 'multi_select'
                                      ? fields[index].options || [{ value: 'default', label: t('system.tenantSettings.defaultOption') }]
                                      : [],
                                }
                                return {
                                  ...s,
                                  config: {
                                    ...(s.config || {}),
                                    registration: {
                                      ...(s.config?.registration || {}),
                                      userProfileFields: {
                                        ...current,
                                        fields,
                                      },
                                    },
                                  },
                                }
                              })
                            }
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {USER_PROFILE_FIELD_TYPE_OPTIONS.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                  {t(option.labelKey)}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="grid gap-2">
                          <Label>{t('system.common.sort')}</Label>
                          <Input
                            type="number"
                            value={field.sort || 0}
                            onChange={(e) =>
                              setSettings((s) => {
                                if (!s) return s
                                const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
                                const fields = [...(current.fields || [])]
                                fields[index] = {
                                  ...fields[index],
                                  sort: Number(e.target.value || 0),
                                }
                                return {
                                  ...s,
                                  config: {
                                    ...(s.config || {}),
                                    registration: {
                                      ...(s.config?.registration || {}),
                                      userProfileFields: {
                                        ...current,
                                        fields,
                                      },
                                    },
                                  },
                                }
                              })
                            }
                          />
                        </div>
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="grid gap-2">
                          <Label>{t('system.tenantSettings.placeholder')}</Label>
                          <Input
                            value={field.placeholder || ''}
                            onChange={(e) =>
                              setSettings((s) => {
                                if (!s) return s
                                const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
                                const fields = [...(current.fields || [])]
                                fields[index] = {
                                  ...fields[index],
                                  placeholder: e.target.value,
                                }
                                return {
                                  ...s,
                                  config: {
                                    ...(s.config || {}),
                                    registration: {
                                      ...(s.config?.registration || {}),
                                      userProfileFields: {
                                        ...current,
                                        fields,
                                      },
                                    },
                                  },
                                }
                              })
                            }
                          />
                        </div>
                        <div className="grid gap-2">
                          <Label>{t('system.tenantSettings.helpText')}</Label>
                          <Input
                            value={field.helpText || ''}
                            onChange={(e) =>
                              setSettings((s) => {
                                if (!s) return s
                                const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
                                const fields = [...(current.fields || [])]
                                fields[index] = {
                                  ...fields[index],
                                  helpText: e.target.value,
                                }
                                return {
                                  ...s,
                                  config: {
                                    ...(s.config || {}),
                                    registration: {
                                      ...(s.config?.registration || {}),
                                      userProfileFields: {
                                        ...current,
                                        fields,
                                      },
                                    },
                                  },
                                }
                              })
                            }
                          />
                        </div>
                      </div>

                      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <label className="flex items-center gap-2 text-sm">
                          <Checkbox
                            checked={Boolean(field.enabled)}
                            onCheckedChange={(checked) =>
                              setSettings((s) => {
                                if (!s) return s
                                const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
                                const fields = [...(current.fields || [])]
                                fields[index] = { ...fields[index], enabled: Boolean(checked) }
                                return {
                                  ...s,
                                  config: {
                                    ...(s.config || {}),
                                    registration: {
                                      ...(s.config?.registration || {}),
                                      userProfileFields: {
                                        ...current,
                                        fields,
                                      },
                                    },
                                  },
                                }
                              })
                            }
                          />
                          {t('system.tenantSettings.fieldEnabled')}
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                          <Checkbox
                            checked={Boolean(field.required)}
                            onCheckedChange={(checked) =>
                              setSettings((s) => {
                                if (!s) return s
                                const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
                                const fields = [...(current.fields || [])]
                                fields[index] = { ...fields[index], required: Boolean(checked) }
                                return {
                                  ...s,
                                  config: {
                                    ...(s.config || {}),
                                    registration: {
                                      ...(s.config?.registration || {}),
                                      userProfileFields: {
                                        ...current,
                                        fields,
                                      },
                                    },
                                  },
                                }
                              })
                            }
                          />
                          {t('system.tenantSettings.fieldModeRequired')}
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                          <Checkbox
                            checked={Boolean(field.listVisible)}
                            onCheckedChange={(checked) =>
                              setSettings((s) => {
                                if (!s) return s
                                const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
                                const fields = [...(current.fields || [])]
                                fields[index] = { ...fields[index], listVisible: Boolean(checked) }
                                return {
                                  ...s,
                                  config: {
                                    ...(s.config || {}),
                                    registration: {
                                      ...(s.config?.registration || {}),
                                      userProfileFields: {
                                        ...current,
                                        fields,
                                      },
                                    },
                                  },
                                }
                              })
                            }
                          />
                          {t('system.tenantSettings.listVisible')}
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                          <Checkbox
                            checked={Boolean(field.filterable)}
                            onCheckedChange={(checked) =>
                              setSettings((s) => {
                                if (!s) return s
                                const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
                                const fields = [...(current.fields || [])]
                                fields[index] = { ...fields[index], filterable: Boolean(checked) }
                                return {
                                  ...s,
                                  config: {
                                    ...(s.config || {}),
                                    registration: {
                                      ...(s.config?.registration || {}),
                                      userProfileFields: {
                                        ...current,
                                        fields,
                                      },
                                    },
                                  },
                                }
                              })
                            }
                          />
                          {t('system.tenantSettings.filterable')}
                        </label>
                      </div>

                      {field.type === 'select' || field.type === 'multi_select' ? (
                        <div className="grid gap-2">
                          <Label>{t('system.tenantSettings.optionsTextareaLabel')}</Label>
                          <Textarea
                            value={stringifyFieldOptions(field.options)}
                            onChange={(e) =>
                              setSettings((s) => {
                                if (!s) return s
                                const current = normalizeUserProfileFieldsConfig(s.config?.registration?.userProfileFields)
                                const fields = [...(current.fields || [])]
                                fields[index] = {
                                  ...fields[index],
                                  options: parseFieldOptionsText(e.target.value),
                                }
                                return {
                                  ...s,
                                  config: {
                                    ...(s.config || {}),
                                    registration: {
                                      ...(s.config?.registration || {}),
                                      userProfileFields: {
                                        ...current,
                                        fields,
                                      },
                                    },
                                  },
                                }
                              })
                            }
                            placeholder={t('system.tenantSettings.optionsTextareaPlaceholder')}
                          />
                        </div>
                      ) : null}
                      </>
                      ) : null}
                    </div>
                  )})}
                </div>
              </div>

              <div>
                <Button
                  onClick={async () => {
                    if (!session || !settings) return
                    setError(null)
                    const id = toast.loading(t('system.tenantSettings.savingRegistration'))
                    try {
                      await apiFetch('/api/v1/tenant/profile/settings', {
                        method: 'PUT',
                        session,
                        body: JSON.stringify({
                          registration: {
                            enabled: Boolean(settings.config?.registration?.enabled),
                            requireAudit: Boolean(settings.config?.registration?.requireAudit),
                            defaultRole: settings.config?.registration?.defaultRole || 'user',
                            basicFields: normalizeRegistrationBasicFieldsConfig(
                              settings.config?.registration?.basicFields,
                            ),
                            invitation: normalizeInvitationConfig(settings.config?.registration?.invitation),
                            userProfileFields: normalizeUserProfileFieldsConfig(
                              settings.config?.registration?.userProfileFields,
                            ),
                          },
                        }),
                      })
                      toast.success(t('system.tenantSettings.registrationSaved'), { id })
                      await load()
                    } catch (err) {
                      const message = err instanceof ApiError ? err.message : t('system.common.saveFailed')
                      setError(message)
                      toast.error(message, { id })
                    }
                  }}
                  disabled={loading || !settings}
                >
                  {t('system.tenantSettings.saveRegistration')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="invite">
          <Card>
            <CardHeader>
              <CardTitle>{t('system.tenantSettings.inviteTitle')}</CardTitle>
              <CardDescription>{t('system.tenantSettings.inviteDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="rounded-xl border p-4 text-sm">
                <div className="font-medium">{t('system.tenantSettings.currentInviteMode')}</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge variant={settings?.config?.registration?.invitation?.enabled ? 'default' : 'secondary'}>
                    {settings?.config?.registration?.invitation?.enabled
                      ? t('system.tenantSettings.invitationEnabled')
                      : t('system.tenantSettings.invitationDisabled')}
                  </Badge>
                  <Badge variant={settings?.config?.registration?.enabled ? 'outline' : 'secondary'}>
                    {settings?.config?.registration?.enabled
                      ? t('system.tenantSettings.publicRegistrationEnabled')
                      : t('system.tenantSettings.inviteOnlyRegistration')}
                  </Badge>
                </div>
                {!settings?.config?.registration?.invitation?.enabled ? (
                  <div className="mt-3 text-xs text-muted-foreground">
                    {t('system.tenantSettings.enableInviteBeforeGenerate')}
                  </div>
                ) : null}
              </div>

              <div className="grid gap-4 rounded-xl border p-4 lg:grid-cols-[220px_minmax(0,1fr)]">
                <div className="grid gap-2">
                  <Label>{t('system.tenantSettings.inviteExpiresDays')}</Label>
                  <Input
                    type="number"
                    min={1}
                    max={365}
                    value={tenantInviteExpiresIn}
                    onChange={(e) =>
                      setTenantInviteExpiresIn(Math.max(1, Math.min(365, Number(e.target.value || 7))))
                    }
                  />
                  <div className="text-xs text-muted-foreground">{t('system.tenantSettings.inviteExpiresHint')}</div>
                </div>

                <div className="grid gap-3">
                  <div className="flex flex-wrap gap-2">
                    <Button
                      disabled={!session || !settings?.config?.registration?.invitation?.enabled}
                      onClick={async () => {
                        if (!session) return
                        const id = toast.loading(t('system.tenantSettings.generatingInviteLink'))
                        try {
                          const data = await apiFetch<TenantInviteLinkResponse>(
                            `/api/v1/tenant/profile/invite-link?expires_days=${encodeURIComponent(String(tenantInviteExpiresIn))}`,
                            {
                              method: 'POST',
                              session,
                            },
                          )
                          setGeneratedTenantInvite(data)
                          toast.success(t('system.tenantSettings.inviteLinkGenerated'), { id })
                        } catch (err) {
                          toast.error(err instanceof ApiError ? err.message : t('system.tenantSettings.generateInviteLinkFailed'), { id })
                        }
                      }}
                    >
                      {t('system.tenantSettings.generateInviteLink')}
                    </Button>
                    <Button type="button" variant="outline" asChild>
                      <Link href="/personal/settings?tab=invite">{t('system.tenantSettings.openPersonalInvitePage')}</Link>
                    </Button>
                    <Button type="button" variant="outline" asChild>
                      <Link href="/system/invitations">{t('system.tenantSettings.viewInvitationDetails')}</Link>
                    </Button>
                  </div>

                  {generatedTenantInvite ? (
                    <div className="grid gap-2 rounded-lg border bg-muted/20 p-3">
                      <div className="text-sm font-medium">{t('system.tenantSettings.latestInviteCode')}</div>
                      <div className="font-mono text-xs">{generatedTenantInvite.inviteCode}</div>
                      <div className="break-all text-xs text-muted-foreground">
                        {resolveInviteUrl(generatedTenantInvite.registerPath, generatedTenantInvite.inviteCode)}
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={async () => {
                            try {
                              await navigator.clipboard.writeText(
                                resolveInviteUrl(generatedTenantInvite.registerPath, generatedTenantInvite.inviteCode),
                              )
                              toast.success(t('system.tenantSettings.inviteLinkCopied'))
                            } catch {
                              toast.error(t('system.tenantSettings.copyInviteLinkFailed'))
                            }
                          }}
                        >
                          {t('system.tenantSettings.copyLink')}
                        </Button>
                        <div className="text-xs text-muted-foreground">
                          {t('system.tenantSettings.expiresAt').replace(
                            '{time}',
                            generatedTenantInvite.expiresAt ? new Date(generatedTenantInvite.expiresAt).toLocaleString() : '-',
                          )}
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="features">
          <Card>
            <CardHeader>
              <CardTitle>{t('system.tenantSettings.featuresTitle')}</CardTitle>
              <CardDescription>{t('system.tenantSettings.featuresDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">
                  {t('system.tenantSettings.moduleEnabledCount')
                    .replace('{enabled}', String(moduleEnabledCount))
                    .replace('{total}', String(moduleTotal))}
                </Badge>
                <Badge variant="outline">
                  {t('system.tenantSettings.capabilityEnabledCount')
                    .replace('{enabled}', String(capabilityEnabledCount))
                    .replace('{total}', String(capabilityTotal))}
                </Badge>
              </div>

              <div className="grid gap-3 rounded-md border p-3">
                <div className="text-sm font-medium">{t('system.tenantSettings.businessModules')}</div>
                {activeCatalog.modules.map((item) => (
                  <label key={item.code} className="flex items-start gap-3 rounded-md border p-3 text-sm">
                    <Checkbox
                      checked={Boolean(settings?.config?.featureSwitches?.modules?.[item.code])}
                      onCheckedChange={(checked) =>
                        setSettings((s) => {
                          if (!s) return s
                          const switches =
                            s.config?.featureSwitches ||
                            normalizeFeatureSwitches(
                              activeCatalog,
                              s.config?.featureSwitches || s.config?.feature_switches,
                              s.config?.verification,
                            )
                          return {
                            ...s,
                            config: {
                              ...(s.config || {}),
                              featureSwitches: {
                                modules: {
                                  ...(switches.modules || {}),
                                  [item.code]: Boolean(checked),
                                },
                                capabilities: { ...(switches.capabilities || {}) },
                              },
                            },
                          }
                        })
                      }
                    />
                    <div className="space-y-1">
                      <div className="font-medium">{resolveMaybeI18n(item.labelKey || item.label, t)}</div>
                      <div className="text-muted-foreground">{resolveMaybeI18n(item.descriptionKey || item.description, t)}</div>
                      {Array.isArray(item.apiPrefixes) && item.apiPrefixes.length > 0 ? (
                        <div className="text-xs text-primary">
                          {t('system.tenantSettings.disabledApis').replace('{prefixes}', formatPrefixPreview(item.apiPrefixes, t))}
                        </div>
                      ) : null}
                      {Array.isArray(item.routePrefixes) && item.routePrefixes.length > 0 ? (
                        <div className="text-xs text-muted-foreground">
                          {t('system.tenantSettings.relatedMenus').replace('{prefixes}', formatPrefixPreview(item.routePrefixes, t))}
                        </div>
                      ) : null}
                    </div>
                  </label>
                ))}
              </div>

              <div className="grid gap-3 rounded-md border p-3">
                <div className="text-sm font-medium">{t('system.tenantSettings.capabilities')}</div>
                {activeCatalog.capabilities.map((item) => (
                  <label key={item.code} className="flex items-start gap-3 rounded-md border p-3 text-sm">
                    <Checkbox
                      checked={Boolean(settings?.config?.featureSwitches?.capabilities?.[item.code])}
                      onCheckedChange={(checked) =>
                        setSettings((s) => {
                          if (!s) return s
                          const switches =
                            s.config?.featureSwitches ||
                            normalizeFeatureSwitches(
                              activeCatalog,
                              s.config?.featureSwitches || s.config?.feature_switches,
                              s.config?.verification,
                            )
                          return {
                            ...s,
                            config: {
                              ...(s.config || {}),
                              featureSwitches: {
                                modules: { ...(switches.modules || {}) },
                                capabilities: {
                                  ...(switches.capabilities || {}),
                                  [item.code]: Boolean(checked),
                                },
                              },
                            },
                          }
                        })
                      }
                    />
                    <div className="space-y-1">
                      <div className="font-medium">{resolveMaybeI18n(item.labelKey || item.label, t)}</div>
                      <div className="text-muted-foreground">{resolveMaybeI18n(item.descriptionKey || item.description, t)}</div>
                    </div>
                  </label>
                ))}
              </div>

              <div>
                <Button
                  onClick={async () => {
                    if (!session || !settings) return
                    const switches = normalizeFeatureSwitches(
                      activeCatalog,
                      settings.config?.featureSwitches || settings.config?.feature_switches,
                      settings.config?.verification,
                    )
                    const smsEnabled = Boolean(switches.capabilities.verification_sms)
                    const emailEnabled = Boolean(switches.capabilities.verification_email)

                    const id = toast.loading(t('system.common.saving'))
                    try {
                      await apiFetch('/api/v1/tenant/profile/settings', {
                        method: 'PUT',
                        session,
                        body: JSON.stringify({
                          featureSwitches: switches,
                          verification: {
                            sms: { enabled: smsEnabled },
                            email: { enabled: emailEnabled },
                          },
                        }),
                      })

                      toast.success(t('system.tenantSettings.featuresSaved'), { id })
                      await load()
                    } catch (err) {
                      const message = err instanceof ApiError ? err.message : t('system.common.saveFailed')
                      toast.error(message, { id })
                    }
                  }}
                  disabled={loading || !settings}
                >
                  {t('system.tenantSettings.saveFeatures')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ai" className="grid gap-4">
          <AIRedactionCard />
          <Card>
            <CardHeader>
              <CardTitle>{t('system.tenantSettings.aiTitle')}</CardTitle>
              <CardDescription>{t('system.tenantSettings.aiDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:max-w-3xl">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={assistantConfig.enabled}
                  onCheckedChange={(checked) =>
                    setAssistantConfig((prev) => ({
                      ...prev,
                      enabled: Boolean(checked),
                    }))
                  }
                />
                {t('system.tenantSettings.enableAiAssistant')}
              </label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={assistantConfig.deductCredits}
                  onCheckedChange={(checked) =>
                    setAssistantConfig((prev) => ({
                      ...prev,
                      deductCredits: Boolean(checked),
                    }))
                  }
                />
                {t('system.tenantSettings.deductCredits')}
              </label>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2 md:max-w-sm">
                  <Label>{t('system.tenantSettings.creditsPerCall')}</Label>
                  <Input
                    type="number"
                    min={0}
                    value={assistantConfig.creditsPerCall}
                    onChange={(e) =>
                      setAssistantConfig((prev) => ({
                        ...prev,
                        creditsPerCall: Number(e.target.value || 0),
                      }))
                    }
                  />
                </div>
                <div className="grid gap-2 md:max-w-sm">
                  <Label>{t('system.tenantSettings.pointsTokenRatio')}</Label>
                  <Input
                    type="number"
                    min={0}
                    value={assistantConfig.pointsTokenRatio}
                    onChange={(e) =>
                      setAssistantConfig((prev) => ({
                        ...prev,
                        pointsTokenRatio: Number(e.target.value || 0),
                      }))
                    }
                  />
                  <p className="text-xs text-muted-foreground">{t('system.tenantSettings.pointsTokenRatioHint')}</p>
                </div>
              </div>
              <div className="grid gap-2">
                <Label>Base URL</Label>
                <Input
                  value={assistantConfig.baseUrl}
                  onChange={(e) =>
                    setAssistantConfig((prev) => ({
                      ...prev,
                      baseUrl: e.target.value,
                    }))
                  }
                />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label>{t('system.speech.model')}</Label>
                  <Input
                    value={assistantConfig.model}
                    onChange={(e) =>
                      setAssistantConfig((prev) => ({
                        ...prev,
                        model: e.target.value,
                      }))
                    }
                  />
                </div>
                <div className="grid gap-2">
                  <Label>Temperature</Label>
                  <Input
                    type="number"
                    step="0.1"
                    min={0}
                    max={2}
                    value={assistantConfig.temperature}
                    onChange={(e) =>
                      setAssistantConfig((prev) => ({
                        ...prev,
                        temperature: Number(e.target.value || 0),
                      }))
                    }
                  />
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label>Max Tokens</Label>
                  <Input
                    type="number"
                    min={1}
                    value={assistantConfig.maxTokens}
                    onChange={(e) =>
                      setAssistantConfig((prev) => ({
                        ...prev,
                        maxTokens: Number(e.target.value || 1),
                      }))
                    }
                  />
                </div>
                <label className="flex items-center gap-2 text-sm md:pt-8">
                  <Checkbox
                    checked={assistantConfig.stream}
                    onCheckedChange={(checked) =>
                      setAssistantConfig((prev) => ({
                        ...prev,
                        stream: Boolean(checked),
                      }))
                    }
                />
                  {t('system.tenantSettings.streamOutput')}
                </label>
              </div>
              <div className="grid gap-2">
                <Label>
                  API Key
                  {assistantConfig.apiKeySet
                    ? t('system.tenantSettings.apiKeySavedHint').replace(
                        '{value}',
                        assistantConfig.apiKeyMasked || t('system.tenantSettings.configured'),
                      )
                    : ''}
                </Label>
                <Input
                  type="password"
                  value={assistantConfig.apiKey}
                  onChange={(e) =>
                    setAssistantConfig((prev) => ({
                      ...prev,
                      apiKey: e.target.value,
                    }))
                  }
                />
              </div>
              <Separator />
              <div className="grid gap-3">
                <div>
                  <Label>{t('system.tenantSettings.moduleSkillGovernance')}</Label>
                  <p className="text-xs text-muted-foreground">
                    {t('system.tenantSettings.moduleSkillGovernanceHint')}
                  </p>
                </div>
                {assistantConfig.moduleSkillCatalog.length > 0 ? (
                  <div className="grid gap-3">
                    {assistantConfig.moduleSkillCatalog.map((module) => {
                      const moduleGovernance = assistantConfig.capabilities.moduleSkillGovernance.modules.find(
                        (item) => item.moduleCode === module.moduleCode,
                      )
                      const moduleRuleMap = new Map(
                        (moduleGovernance?.skillRules || []).map((rule) => [rule.skillId, rule]),
                      )
                      return (
                        <div key={module.moduleCode} className="rounded-lg border p-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <div className="text-sm font-medium">{module.moduleName}</div>
                            <Badge variant="outline">{module.moduleCode}</Badge>
                          </div>
                          <div className="mt-3 grid gap-3">
                            {module.skills.map((skill) => {
                              const skillRule = moduleRuleMap.get(skill.skillId)
                              const enabled = skillRule?.enabled ?? true
                              const rank = skillRule?.rank ?? skill.defaultRank
                              return (
                                <div
                                  key={skill.skillId}
                                  className="grid gap-2 rounded-md border border-dashed p-3 md:grid-cols-[minmax(0,1fr)_88px_88px]"
                                >
                                  <div className="min-w-0">
                                    <div className="text-sm font-medium">{skill.label}</div>
                                    <div className="text-xs text-muted-foreground">{skill.description || skill.skillId}</div>
                                    {skill.scopeIds.length > 0 ? (
                                      <div className="mt-2 flex flex-wrap gap-1">
                                        {skill.scopeIds.map((scopeId) => (
                                          <Badge key={`${skill.skillId}-${scopeId}`} variant="secondary" className="text-xs">
                                            {scopeId}
                                          </Badge>
                                        ))}
                                      </div>
                                    ) : null}
                                  </div>
                                  <div className="grid gap-1">
                                    <Label className="text-xs text-muted-foreground">{t('system.common.sort')}</Label>
                                    <Input
                                      type="number"
                                      min={0}
                                      value={rank}
                                      onChange={(e) =>
                                        updateAssistantModuleSkillRule(module.moduleCode, skill.skillId, {
                                          rank: Number(e.target.value || skill.defaultRank || 0),
                                        })
                                      }
                                    />
                                  </div>
                                  <label className="flex items-end gap-2 text-sm md:justify-end">
                                    <Checkbox
                                      checked={enabled}
                                      onCheckedChange={(checked) =>
                                        updateAssistantModuleSkillRule(module.moduleCode, skill.skillId, {
                                          enabled: Boolean(checked),
                                        })
                                      }
                                    />
                                    {t('common.enabled')}
                                  </label>
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
                    {t('system.tenantSettings.noModuleSkillCatalog')}
                  </div>
                )}
              </div>
              <div>
                <Button onClick={() => void saveAssistantConfig()} disabled={assistantSaving}>
                  {t('system.tenantSettings.saveAiConfig')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {speechModuleEnabled ? (
          <TabsContent value="speech">
            {activeTab === 'speech' ? <SpeechSettingsShell initialPanel={activeSpeechPanel} embedded /> : null}
          </TabsContent>
        ) : null}

        <TabsContent value="seo">
          <Card>
            <CardHeader>
              <CardTitle>{t('system.tenantSettings.seoTitle')}</CardTitle>
              <CardDescription>{t('system.tenantSettings.seoDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:max-w-2xl">
              <div className="grid gap-2">
                <Label>{t('system.tenantSettings.siteTitleSuffix')}</Label>
                <Input
                  placeholder={t('system.tenantSettings.siteTitlePlaceholder')}
                  value={settings?.config?.seo?.title || ''}
                  onChange={(e) =>
                    setSettings((s) =>
                      s
                        ? {
                            ...s,
                            config: {
                              ...(s.config || {}),
                              seo: {
                                ...(s.config?.seo || {}),
                                title: e.target.value,
                              },
                            },
                          }
                        : s,
                    )
                  }
                />
                <p className="text-xs text-muted-foreground">{t('system.tenantSettings.siteTitleHint')}</p>
              </div>
              <div className="grid gap-2">
                <Label>{t('system.tenantSettings.keywords')}</Label>
                <Input
                  placeholder={t('system.tenantSettings.keywordsPlaceholder')}
                  value={settings?.config?.seo?.keywords || ''}
                  onChange={(e) =>
                    setSettings((s) =>
                      s
                        ? {
                            ...s,
                            config: {
                              ...(s.config || {}),
                              seo: {
                                ...(s.config?.seo || {}),
                                keywords: e.target.value,
                              },
                            },
                          }
                        : s,
                    )
                  }
                />
              </div>
              <div className="grid gap-2">
                <Label>{t('system.tenantSettings.metaDescription')}</Label>
                <Textarea
                  placeholder={t('system.tenantSettings.metaDescriptionPlaceholder')}
                  value={settings?.config?.seo?.description || ''}
                  onChange={(e) =>
                    setSettings((s) =>
                      s
                        ? {
                            ...s,
                            config: {
                              ...(s.config || {}),
                              seo: {
                                ...(s.config?.seo || {}),
                                description: e.target.value,
                              },
                            },
                          }
                        : s,
                    )
                  }
                />
              </div>

              <div className="flex items-center gap-2">
                <Button
                  onClick={async () => {
                    if (!session || !settings) return
                    setError(null)
                    const id = toast.loading(t('system.common.saving'))
                    try {
                      const title = settings.config?.seo?.title || ''
                      const keywords = settings.config?.seo?.keywords || ''
                      const description = settings.config?.seo?.description || ''

                      await apiFetch('/api/v1/tenant/profile/settings', {
                        method: 'PUT',
                        session,
                        body: JSON.stringify({
                          seo: { title, keywords, description },
                        }),
                      })

                      applySiteSeo({
                        title: title.trim() ? title : profile?.name || '',
                        keywords,
                        description,
                      })
                      toast.success(t('system.tenantSettings.saveSuccess'), { id })
                      await load()
                    } catch (err) {
                      const message = err instanceof ApiError ? err.message : t('system.common.saveFailed')
                      toast.error(message, { id })
                    }
                  }}
                  disabled={loading || !settings}
                >
                  {t('system.tenantSettings.saveSeo')}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="mt-4">
            <CardHeader>
              <CardTitle>{t('system.tenantSettings.brandLanguageTitle')}</CardTitle>
              <CardDescription>{t('system.tenantSettings.brandLanguageDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:max-w-2xl">
              <div className="flex flex-wrap gap-2">
                {Object.values(THEME_PRESETS).map((preset) => {
                  const selected = (settings?.config?.appearance?.primaryColor || DEFAULT_THEME_PRESET_KEY) === preset.key
                  return (
                    <button
                      key={preset.key}
                      type="button"
                      onClick={() => {
                        setSettings((s) =>
                          s
                            ? {
                                ...s,
                                config: {
                                  ...(s.config || {}),
                                  appearance: {
                                    ...(s.config?.appearance || {}),
                                    primaryColor: preset.key,
                                  },
                                },
                              }
                            : s,
                        )
                        applyThemePreset(preset)
                      }}
                      className={
                        selected
                          ? 'flex items-center gap-2 rounded-md border-2 border-primary px-2.5 py-1.5 text-[13px] font-medium'
                          : 'flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-[13px] text-muted-foreground hover:border-foreground/30'
                      }
                    >
                      <span
                        className="h-4 w-4 rounded-full border"
                        style={{ backgroundColor: `hsl(${preset.light})` }}
                      />
                      {t(preset.labelKey)}
                    </button>
                  )
                })}
              </div>
              <div className="grid gap-2 md:max-w-xs">
                <Label>{t('system.tenantSettings.defaultLocale')}</Label>
                <Select
                  value={settings?.config?.appearance?.defaultLocale || 'zh-CN'}
                  onValueChange={(value) =>
                    setSettings((s) =>
                      s
                        ? {
                            ...s,
                            config: {
                              ...(s.config || {}),
                              appearance: { ...(s.config?.appearance || {}), defaultLocale: value },
                            },
                          }
                        : s,
                    )
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="zh-CN">{t('system.tenantSettings.localeZhCN')}</SelectItem>
                    <SelectItem value="en-US">English</SelectItem>
                    <SelectItem value="es-ES">Español</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  onClick={async () => {
                    if (!session || !settings) return
                    setError(null)
                    const id = toast.loading(t('system.common.saving'))
                    try {
                      const primaryColor = settings.config?.appearance?.primaryColor || DEFAULT_THEME_PRESET_KEY
                      const defaultLocale = settings.config?.appearance?.defaultLocale || 'zh-CN'
                      await apiFetch('/api/v1/tenant/profile/settings', {
                        method: 'PUT',
                        session,
                        body: JSON.stringify({ appearance: { primaryColor, defaultLocale } }),
                      })
                      applyThemePreset(resolveThemePreset(primaryColor))
                      toast.success(t('system.tenantSettings.saveSuccess'), { id })
                      await load()
                    } catch (err) {
                      const message = err instanceof ApiError ? err.message : t('system.common.saveFailed')
                      toast.error(message, { id })
                    }
                  }}
                  disabled={loading || !settings}
                >
                  {t('system.tenantSettings.saveAppearance')}
                </Button>
                <p className="text-xs text-muted-foreground">{t('system.tenantSettings.appearanceRefreshHint')}</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
