'use client'

import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { SimplePagination } from '@/components/list/simple-pagination'
import { PageHeader } from '@/components/page/page-header'
import { UserProfileForm } from '@/components/profile/user-profile-form'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ApiError, apiFetch } from '@/lib/api'
import { useT } from '@/lib/i18n'
import { normalizeProfileMeta, normalizeUserProfileFieldsConfig, type UserProfileFieldsConfig, type UserProfileMeta } from '@/lib/user-profile-fields'
import { useAuth } from '@/hooks/useAuth'
import { useTheme } from '@/hooks/useTheme'

type MineInfo = {
  avatar: string
  username: string
  nickname: string
  email: string
  phone: string
  description: string
  wechatBound?: boolean
  wechatNickname?: string
  wechatAvatar?: string
  profile?: Record<string, unknown>
  profileMeta?: UserProfileMeta
  profileSchema?: UserProfileFieldsConfig
  mustCompleteProfile?: boolean
}

type TenantFeatureSwitchesResponse = {
  featureSwitches?: {
    capabilities?: Record<string, boolean>
  }
  feature_switches?: {
    capabilities?: Record<string, boolean>
  }
}

type TenantSettingsResponse = {
  config?: {
    registration?: {
      invitation?: InvitationConfig
    }
    verification?: {
      sms?: { enabled?: boolean }
      email?: { enabled?: boolean }
    }
    featureSwitches?: {
      capabilities?: Record<string, boolean>
    }
    feature_switches?: {
      capabilities?: Record<string, boolean>
    }
  }
}

type InvitationConfig = {
  enabled?: boolean
  inviterRewardCredits?: number
  inviteeRewardCredits?: number
  rewardDelayDays?: number
  maxInvitesPerUser?: number
  inviteCodeCostCredits?: number
}

type InviteCodeItem = {
  id?: number
  inviteCode: string
  status: string
  expiresIn: number
  tenantCode: string
  tenantName: string
  maxUses: number
  usedCount: number
  remainingUses: number
  costCredits: number
  registerPath: string
  createdAt?: string | null
  expiresAt?: string | null
  lastUsedAt?: string | null
  invitedUserId?: number | null
  invitedUsername?: string | null
  invitedNickname?: string | null
  invitedAt?: string | null
  canRecycle?: boolean
  recycledAt?: string | null
  refundedCredits?: number
  refundedAt?: string | null
}

type InvitationSummaryResponse = {
  config?: InvitationConfig
  userCanInvite: boolean
  usedInviteCount: number
  activeReservedInviteQuota: number
  remainingInviteQuota: number
  totalRelatedRecords: number
  issuedInviterRewardCredits: string
  issuedInviteeRewardCredits: string
  pendingInviterRewardCredits: string
  pendingInviteeRewardCredits: string
  codes: InviteCodeItem[]
}

type MessageChannel = {
  id: number
  channelType: 'wechat' | 'feishu' | 'webhook' | string
  name: string
  target?: string | null
  status: 'pending' | 'active' | 'disabled' | string
  isDefault?: boolean
  externalUserId?: string | null
  conversationId?: string | null
  displayName?: string | null
  avatar?: string | null
  messageTypes?: string[]
  boundAt?: string | null
  lastInboundAt?: string | null
  lastSentAt?: string | null
  lastError?: string | null
  extra?: Record<string, unknown>
  createdAt?: string | null
  updatedAt?: string | null
  secretConfigured?: boolean
}

type MessageChannelBindResult = {
  channelId: number
  bindToken: string
  bindingCode: string
  qrText: string
  qrUrl?: string | null
  qrImageUrl?: string | null
  qrPayload?: string | null
  verificationUriComplete?: string | null
  expiresAt?: string | null
  instructions?: string[]
  gatewayReady?: boolean
  status: string
  channelType: 'wechat' | 'feishu'
}

type MessageChannelForm = {
  channelType: 'webhook'
  name: string
  target: string
  secret: string
  status: 'pending' | 'active' | 'disabled'
  isDefault: boolean
  messageTypes: string[]
}

type InvitationRecord = {
  id: number
  relation?: string | null
  inviteCode?: string | null
  inviteCodeStatus?: string | null
  inviterNickname?: string | null
  inviterUsername?: string | null
  invitedNickname?: string | null
  invitedUsername?: string | null
  inviterRewardCredits: string
  inviteeRewardCredits: string
  rewardDelayDays: number
  availableAt?: string | null
  inviterRewardStatus: string
  inviteeRewardStatus: string
  createdAt?: string | null
}

type PageResponse<T> = {
  list: T[]
  total: number
  pageSize: number
  currentPage: number
}

type TFunction = ReturnType<typeof useT>

function readVerificationCapabilities(settings: TenantSettingsResponse | null) {
  const capabilities =
    settings?.config?.featureSwitches?.capabilities || settings?.config?.feature_switches?.capabilities || {}
  const smsSwitch = capabilities.verification_sms
  const emailSwitch = capabilities.verification_email
  const smsEnabled = typeof smsSwitch === 'boolean' ? smsSwitch : settings?.config?.verification?.sms?.enabled
  const emailEnabled =
    typeof emailSwitch === 'boolean' ? emailSwitch : settings?.config?.verification?.email?.enabled

  return {
    sms: typeof smsEnabled === 'boolean' ? smsEnabled : true,
    email: typeof emailEnabled === 'boolean' ? emailEnabled : true,
  }
}

function readVerificationCapabilitiesFromRuntime(data: TenantFeatureSwitchesResponse | null) {
  const capabilities = data?.featureSwitches?.capabilities || data?.feature_switches?.capabilities || {}

  return {
    sms: typeof capabilities.verification_sms === 'boolean' ? capabilities.verification_sms : true,
    email: typeof capabilities.verification_email === 'boolean' ? capabilities.verification_email : true,
  }
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

function invitationStatusLabel(status: string | null | undefined, t: TFunction): string {
  switch (String(status || '').trim().toLowerCase()) {
    case 'issued':
      return t('system.invitations.statusIssued')
    case 'pending':
      return t('system.invitations.statusPending')
    case 'skipped':
      return t('system.invitations.statusSkipped')
    case 'active':
      return t('system.invitations.statusActive')
    case 'exhausted':
      return t('system.invitations.statusExhausted')
    case 'expired':
      return t('system.invitations.statusExpired')
    case 'disabled':
      return t('system.invitations.statusDisabled')
    case 'sent':
      return t('system.personal.invitationSent')
    case 'received':
      return t('system.personal.invitationReceived')
    default:
      return status || '-'
  }
}

function resolveInviteUrl(registerPath: string | null | undefined, inviteCode: string): string {
  const path = registerPath || `/register?invite=${encodeURIComponent(inviteCode)}`
  if (typeof window === 'undefined') return path
  return new URL(path, window.location.origin).toString()
}

function resolveInviteeLabel(code: InviteCodeItem): string {
  return code.invitedNickname || code.invitedUsername || ''
}

function describeInviteCodeUsage(code: InviteCodeItem, t: TFunction): string {
  const inviteeLabel = resolveInviteeLabel(code)
  if ((code.usedCount || 0) <= 0) return t('system.personal.inviteCodeUnused')
  if ((code.maxUses || 1) <= 1) {
    return inviteeLabel
      ? t('system.personal.inviteCodeUsedBy').replace('{name}', inviteeLabel)
      : t('system.personal.inviteCodeUsed')
  }
  return inviteeLabel
    ? t('system.personal.inviteCodeUsageWithRecent')
        .replace('{used}', String(code.usedCount))
        .replace('{max}', String(code.maxUses))
        .replace('{name}', inviteeLabel)
    : t('system.personal.inviteCodeUsage')
        .replace('{used}', String(code.usedCount))
        .replace('{max}', String(code.maxUses))
}

function describeInviteCodeRecovery(code: InviteCodeItem, t: TFunction): string {
  const refundedCredits = Number(code.refundedCredits || 0)
  if (refundedCredits > 0) return t('system.personal.inviteCodeRefunded').replace('{credits}', String(refundedCredits))
  if (code.recycledAt) return t('system.personal.inviteCodeRecycled')
  if (code.canRecycle) {
    return Number(code.costCredits || 0) > 0
      ? t('system.personal.inviteCodeCanRecycleWithRefund').replace('{credits}', String(code.costCredits))
      : t('system.personal.inviteCodeCanRecycle')
  }
  return ''
}

function formatDateTime(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString() : '-'
}

function resolveInvitationRecordPeerLabel(record: InvitationRecord): string {
  return record.relation === 'sent'
    ? record.invitedNickname || record.invitedUsername || '-'
    : record.inviterNickname || record.inviterUsername || '-'
}

function resolveInvitationRewardProgress(record: InvitationRecord, t: TFunction): string {
  const isSent = record.relation === 'sent'
  const credits = isSent ? record.inviterRewardCredits : record.inviteeRewardCredits
  const status = isSent ? record.inviterRewardStatus : record.inviteeRewardStatus
  const normalizedCredits = String(credits || '0').trim()

  if (!normalizedCredits || normalizedCredits === '0' || status === 'skipped') return t('system.personal.noCredits')
  if (status === 'issued') return t('system.personal.creditsIssued').replace('{credits}', normalizedCredits)
  if (status === 'pending') return t('system.personal.creditsPending').replace('{credits}', normalizedCredits)
  return `${invitationStatusLabel(status, t)} +${normalizedCredits}`
}

type PersonalSettingsTab = 'account' | 'profile' | 'invite' | 'notifications' | 'contact' | 'security'

function normalizePersonalSettingsTab(
  value: string | null | undefined,
  fallback: PersonalSettingsTab = 'account',
): PersonalSettingsTab {
  switch (String(value || '').trim().toLowerCase()) {
    case 'account':
    case 'profile':
    case 'invite':
    case 'contact':
    case 'notifications':
    case 'security':
      return String(value).trim().toLowerCase() as PersonalSettingsTab
    default:
      return fallback
  }
}

function defaultMessageChannelForm(t: TFunction): MessageChannelForm {
  return {
    channelType: 'webhook',
    name: t('system.personal.webhookChannel'),
    target: '',
    secret: '',
    status: 'active',
    isDefault: false,
    messageTypes: ['notification'],
  }
}

function messageChannelTypeLabel(type: string, t: TFunction): string {
  switch (type) {
    case 'feishu':
      return t('system.personal.feishu')
    case 'wechat':
      return t('system.personal.wechat')
    case 'webhook':
      return t('system.personal.webhook')
    default:
      return type || '-'
  }
}

function messageChannelBindStatusLabel(status: string, t: TFunction): string {
  switch (status) {
    case 'pending':
      return t('system.personal.channelPending')
    case 'active':
      return t('system.personal.channelBound')
    case 'disabled':
      return t('system.personal.channelDisabled')
    case 'expired':
      return t('system.invitations.statusExpired')
    default:
      return status || '-'
  }
}

function messageChannelBindFallbackInstructions(result: MessageChannelBindResult, t: TFunction): string[] {
  const provider = messageChannelTypeLabel(result.channelType, t)
  return [
    t('system.personal.bindInstructionScan').replace('{provider}', provider),
    t('system.personal.bindInstructionCode'),
    t('system.personal.bindInstructionSuccess'),
  ]
}

function buildMessageChannelPayload(form: MessageChannelForm) {
  const extra: Record<string, unknown> = {}
  return {
    channelType: form.channelType,
    name: form.name.trim(),
    target: form.target.trim() || null,
    secret: form.secret.trim() || null,
    status: form.status,
    isDefault: form.isDefault,
    messageTypes: form.messageTypes,
    extra,
  }
}

function mapChannelToForm(channel: MessageChannel): MessageChannelForm {
  return {
    channelType: 'webhook',
    name: channel.name || '',
    target: channel.target || '',
    secret: '',
    status: channel.status === 'disabled' ? 'disabled' : 'active',
    isDefault: Boolean(channel.isDefault),
    messageTypes: channel.messageTypes || ['notification'],
  }
}

function mapMissingProfileLabels(meta: UserProfileMeta, schema: UserProfileFieldsConfig): string[] {
  const fieldLabelMap = new Map(
    (schema.fields || []).map((field) => [field.key, field.label || field.key]),
  )
  return (meta.missingRequiredKeys || []).map((key) => fieldLabelMap.get(key) || key)
}

export default function PersonalSettingsPage() {
  const t = useT()
  const { session, logout, setSession } = useAuth()
  const { theme, setTheme } = useTheme()
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  const [mineInfo, setMineInfo] = useState<MineInfo | null>(null)
  const [profileSchema, setProfileSchema] = useState<UserProfileFieldsConfig>(normalizeUserProfileFieldsConfig(null))
  const [profileMeta, setProfileMeta] = useState<UserProfileMeta>(normalizeProfileMeta(null))
  const [profileForm, setProfileForm] = useState<Record<string, unknown>>({})
  const [profileSaving, setProfileSaving] = useState(false)
  const [verificationCapabilities, setVerificationCapabilities] = useState({ sms: true, email: true })
  const [contactLoading, setContactLoading] = useState(false)
  const [phoneSending, setPhoneSending] = useState(false)
  const [phoneBinding, setPhoneBinding] = useState(false)
  const [emailSending, setEmailSending] = useState(false)
  const [emailBinding, setEmailBinding] = useState(false)
  const [phoneCooldown, setPhoneCooldown] = useState(0)
  const [emailCooldown, setEmailCooldown] = useState(0)
  const [invitationSummary, setInvitationSummary] = useState<InvitationSummaryResponse | null>(null)
  const [invitationRecords, setInvitationRecords] = useState<PageResponse<InvitationRecord> | null>(null)
  const [invitationLoading, setInvitationLoading] = useState(false)
  const [invitationRecordsLoading, setInvitationRecordsLoading] = useState(false)
  const [inviteExpiresIn, setInviteExpiresIn] = useState(7)
  const [inviteSubmitting, setInviteSubmitting] = useState(false)
  const [recyclingInviteCodeId, setRecyclingInviteCodeId] = useState<number | null>(null)
  const [phoneForm, setPhoneForm] = useState({ phone: '', code: '' })
  const [emailForm, setEmailForm] = useState({ email: '', code: '' })
  const [messageChannels, setMessageChannels] = useState<MessageChannel[]>([])
  const [messageChannelsLoading, setMessageChannelsLoading] = useState(false)
  const [messageChannelSaving, setMessageChannelSaving] = useState(false)
  const [messageChannelBinding, setMessageChannelBinding] = useState(false)
  const [messageChannelBindResult, setMessageChannelBindResult] =
    useState<MessageChannelBindResult | null>(null)
  const [testingMessageChannelId, setTestingMessageChannelId] = useState<number | null>(null)
  const [editingMessageChannelId, setEditingMessageChannelId] = useState<number | null>(null)
  const [messageChannelForm, setMessageChannelForm] = useState<MessageChannelForm>(() =>
    defaultMessageChannelForm(t),
  )

  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [savingPassword, setSavingPassword] = useState(false)

  const passwordMismatch = useMemo(() => {
    if (!newPassword || !confirmPassword) return false
    return newPassword !== confirmPassword
  }, [confirmPassword, newPassword])

  const canSubmitPassword = Boolean(oldPassword && newPassword && confirmPassword && !passwordMismatch)
  const defaultTab: PersonalSettingsTab = mineInfo?.mustCompleteProfile ? 'profile' : 'account'
  const activeTab = useMemo(
    () => normalizePersonalSettingsTab(searchParams?.get('tab'), defaultTab),
    [defaultTab, searchParams],
  )
  const missingProfileLabels = useMemo(
    () => mapMissingProfileLabels(profileMeta, profileSchema),
    [profileMeta, profileSchema],
  )

  const loadMessageChannels = useCallback(
    async (options?: { silent?: boolean }): Promise<MessageChannel[] | null> => {
      if (!session) return null
      if (!options?.silent) setMessageChannelsLoading(true)
      try {
        const channels = await apiFetch<MessageChannel[]>('/api/v1/message-channels', { session })
        const nextChannels = channels || []
        setMessageChannels(nextChannels)
        return nextChannels
      } catch (err) {
        if (!options?.silent) toast.error(err instanceof ApiError ? err.message : t('system.personal.messageChannelsLoadFailed'))
        return null
      } finally {
        if (!options?.silent) setMessageChannelsLoading(false)
      }
    },
    [session, t],
  )

  useEffect(() => {
    if (phoneCooldown <= 0) return
    const timer = window.setInterval(() => {
      setPhoneCooldown((prev) => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [phoneCooldown])

  useEffect(() => {
    if (emailCooldown <= 0) return
    const timer = window.setInterval(() => {
      setEmailCooldown((prev) => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [emailCooldown])

  useEffect(() => {
    if (!session) return
    let ignore = false

    const loadPersonalContext = async () => {
      setContactLoading(true)
      setInvitationLoading(true)
      try {
        const verificationCapabilitiesRequest = apiFetch<TenantFeatureSwitchesResponse>(
          '/api/v1/tenant/profile/feature-switches',
          { session },
        )
          .then((runtime) => readVerificationCapabilitiesFromRuntime(runtime))
          .catch(async () => {
            const tenantSettings = await apiFetch<TenantSettingsResponse>('/api/v1/tenant/profile/settings', {
              session,
            }).catch(() => null)
            return readVerificationCapabilities(tenantSettings)
          })

        const [mineRes, verificationCapabilitiesResult, summaryRes, recordsRes] = await Promise.all([
          apiFetch<MineInfo>('/api/v1/auth/mine', { session }),
          verificationCapabilitiesRequest,
          apiFetch<InvitationSummaryResponse>('/api/v1/invitations/my/summary', { session }).catch(() => null),
          apiFetch<PageResponse<InvitationRecord>>('/api/v1/invitations/my/records?currentPage=1&pageSize=10', {
            session,
          }).catch(() => null),
        ])
        if (ignore) return
        setMineInfo(mineRes)
        setProfileForm(mineRes.profile || {})
        setProfileMeta(normalizeProfileMeta(mineRes.profileMeta))
        setProfileSchema(normalizeUserProfileFieldsConfig(mineRes.profileSchema))
        setPhoneForm((prev) => ({ ...prev, phone: mineRes.phone || prev.phone }))
        setEmailForm((prev) => ({ ...prev, email: mineRes.email || prev.email }))
        setVerificationCapabilities(verificationCapabilitiesResult)
        setInvitationSummary(
          summaryRes
            ? {
                ...summaryRes,
                config: normalizeInvitationConfig(summaryRes.config),
                codes: summaryRes.codes || [],
              }
            : null,
        )
        setInvitationRecords(recordsRes)
        void loadMessageChannels()
      } catch {
        if (!ignore) {
          setVerificationCapabilities({ sms: true, email: true })
        }
      } finally {
        if (!ignore) setContactLoading(false)
        if (!ignore) setInvitationLoading(false)
      }
    }

    void loadPersonalContext()
    return () => {
      ignore = true
    }
  }, [loadMessageChannels, session])

  useEffect(() => {
    const channelId = messageChannelBindResult?.channelId
    const channelType = messageChannelBindResult?.channelType
    const bindStatus = messageChannelBindResult?.status
    const bindExpiresAt = messageChannelBindResult?.expiresAt
    if (!session || !channelId || !channelType || bindStatus !== 'pending') return

    const expiresAtMs = bindExpiresAt ? new Date(bindExpiresAt).getTime() : 0
    let stopped = false
    let notified = false

    const pollBindStatus = async () => {
      if (stopped) return
      if (expiresAtMs && Number.isFinite(expiresAtMs) && Date.now() > expiresAtMs) {
        setMessageChannelBindResult((prev) =>
          prev && prev.channelId === channelId && prev.status === 'pending' ? { ...prev, status: 'expired' } : prev,
        )
        await loadMessageChannels({ silent: true })
        return
      }

      const channels = await loadMessageChannels({ silent: true })
      if (stopped || !channels) return

      const channel = channels.find((item) => item.id === channelId)
      if (!channel) {
        setMessageChannelBindResult((prev) =>
          prev && prev.channelId === channelId ? { ...prev, status: 'expired' } : prev,
        )
        return
      }

      const qrExtra =
        channel.extra?.qr && typeof channel.extra.qr === 'object'
          ? (channel.extra.qr as Record<string, unknown>)
          : {}
      const gatewayReady = typeof qrExtra.gatewayReady === 'boolean' ? qrExtra.gatewayReady : undefined
      setMessageChannelBindResult((prev) => {
        if (!prev || prev.channelId !== channelId) return prev
        return {
          ...prev,
          status: channel.status || prev.status,
          gatewayReady: Boolean(prev.gatewayReady || gatewayReady),
        }
      })

      if (channel.status === 'active' && !notified) {
        notified = true
        toast.success(t('system.personal.channelBoundToast').replace('{type}', messageChannelTypeLabel(channelType, t)))
      } else if (channel.status === 'disabled' && !notified) {
        notified = true
        toast.error(channel.lastError || t('system.personal.channelBindIncomplete'))
      }
    }

    void pollBindStatus()
    const timer = window.setInterval(() => {
      void pollBindStatus()
    }, 3000)
    return () => {
      stopped = true
      window.clearInterval(timer)
    }
  }, [
    loadMessageChannels,
    messageChannelBindResult?.channelId,
    messageChannelBindResult?.channelType,
    messageChannelBindResult?.expiresAt,
    messageChannelBindResult?.status,
    session,
    t,
  ])

  async function saveMessageChannel() {
    if (!session) return
    if (!messageChannelForm.name.trim()) {
      toast.error(t('system.personal.enterChannelName'))
      return
    }
    if (!messageChannelForm.target.trim()) {
      toast.error(t('system.personal.enterWebhookUrl'))
      return
    }
    setMessageChannelSaving(true)
    const id = toast.loading(
      editingMessageChannelId ? t('system.personal.savingMessageChannel') : t('system.personal.creatingMessageChannel'),
    )
    try {
      const payload = buildMessageChannelPayload(messageChannelForm)
      await apiFetch<MessageChannel>(
        editingMessageChannelId
          ? `/api/v1/message-channels/${editingMessageChannelId}`
          : '/api/v1/message-channels/manual',
        {
          method: editingMessageChannelId ? 'PUT' : 'POST',
          session,
          body: JSON.stringify(payload),
        },
      )
      setEditingMessageChannelId(null)
      setMessageChannelForm(defaultMessageChannelForm(t))
      await loadMessageChannels()
      toast.success(t('system.personal.messageChannelSaved'), { id })
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t('system.common.saveFailed'), { id })
    } finally {
      setMessageChannelSaving(false)
    }
  }

  async function startMessageChannelBind(channelType: 'wechat' | 'feishu') {
    if (!session) return
    setMessageChannelBinding(true)
    const id = toast.loading(t('system.personal.generatingBindInfo'))
    try {
      const res = await apiFetch<Omit<MessageChannelBindResult, 'channelType'>>(
        '/api/v1/message-channels/bind/start',
        {
          method: 'POST',
          session,
          body: JSON.stringify({
            channelType,
            name: channelType === 'wechat' ? t('system.personal.wechatChannel') : t('system.personal.feishuChannel'),
            messageTypes: ['notification'],
          }),
        },
      )
      setMessageChannelBindResult({ ...res, channelType })
      await loadMessageChannels()
      toast.success(t('system.personal.bindInfoGenerated'), { id })
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t('system.personal.generateBindInfoFailed'), { id })
    } finally {
      setMessageChannelBinding(false)
    }
  }

  async function testMessageChannel(channel: MessageChannel) {
    if (!session) return
    setTestingMessageChannelId(channel.id)
    const id = toast.loading(t('system.personal.sendingTestMessage'))
    try {
      await apiFetch(`/api/v1/message-channels/${channel.id}/test`, {
        method: 'POST',
        session,
        body: JSON.stringify({
          title: t('system.personal.testMessageTitle'),
          content: t('system.personal.testMessageContent').replace('{name}', channel.name),
        }),
      })
      await loadMessageChannels()
      toast.success(t('system.personal.testMessageSent'), { id })
    } catch (err) {
      await loadMessageChannels()
      toast.error(err instanceof ApiError ? err.message : t('system.common.sendFailed'), { id })
    } finally {
      setTestingMessageChannelId(null)
    }
  }

  async function deleteMessageChannel(channel: MessageChannel) {
    // 确认由 AlertDialog 承担：原生 window.confirm 的按钮文字跟随系统语言、改不了，
    // 多语言直接失效（见 guide_docs/FRONTEND_PAGE_SCAFFOLD_GUIDE.md §5）。
    if (!session) return
    const id = toast.loading(t('system.personal.deletingMessageChannel'))
    try {
      await apiFetch(`/api/v1/message-channels/${channel.id}`, { method: 'DELETE', session })
      if (editingMessageChannelId === channel.id) {
        setEditingMessageChannelId(null)
        setMessageChannelForm(defaultMessageChannelForm(t))
      }
      await loadMessageChannels()
      toast.success(t('system.personal.messageChannelDeleted'), { id })
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t('system.common.deleteFailed'), { id })
    }
  }

  async function loadInvitationRecords(page = 1) {
    if (!session) return
    setInvitationRecordsLoading(true)
    try {
      const res = await apiFetch<PageResponse<InvitationRecord>>(
        `/api/v1/invitations/my/records?currentPage=${page}&pageSize=10`,
        { session },
      )
      setInvitationRecords(res)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t('system.personal.invitationRecordsLoadFailed'))
    } finally {
      setInvitationRecordsLoading(false)
    }
  }

  async function refreshInvitationData() {
    if (!session) return
    const currentPage = invitationRecords?.currentPage || 1
    const pageSize = invitationRecords?.pageSize || 10
    const [summary, records] = await Promise.all([
      apiFetch<InvitationSummaryResponse>('/api/v1/invitations/my/summary', { session }),
      apiFetch<PageResponse<InvitationRecord>>(
        `/api/v1/invitations/my/records?currentPage=${currentPage}&pageSize=${pageSize}`,
        { session },
      ).catch(() => invitationRecords),
    ])
    setInvitationSummary({
      ...summary,
      config: normalizeInvitationConfig(summary.config),
      codes: summary.codes || [],
    })
    if (records) setInvitationRecords(records)
  }

  async function handleGenerateInviteCode() {
    if (!session) return
    setInviteSubmitting(true)
    try {
      await apiFetch<InviteCodeItem>(
        `/api/v1/invitations/my/code?expires_days=${encodeURIComponent(String(inviteExpiresIn))}`,
        {
          method: 'POST',
          session,
        },
      )
      toast.success(t('system.personal.inviteCodeGenerated'))
      await refreshInvitationData()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t('system.personal.generateFailed'))
    } finally {
      setInviteSubmitting(false)
    }
  }

  async function handleRecycleInviteCode(code: InviteCodeItem) {
    if (!session || !code.id) return
    setRecyclingInviteCodeId(code.id)
    try {
      await apiFetch<InviteCodeItem>(`/api/v1/invitations/my/codes/${code.id}/recycle`, {
        method: 'POST',
        session,
      })
      toast.success(
        Number(code.costCredits || 0) > 0
          ? t('system.personal.inviteCodeRecycledWithRefund').replace('{credits}', String(code.costCredits))
          : t('system.personal.inviteCodeRecycled'),
      )
      await refreshInvitationData()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t('system.personal.recycleFailed'))
    } finally {
      setRecyclingInviteCodeId(null)
    }
  }

  async function handleCopyInviteUrl(code: InviteCodeItem) {
    try {
      await navigator.clipboard.writeText(resolveInviteUrl(code.registerPath, code.inviteCode))
      toast.success(t('system.tenantSettings.inviteLinkCopied'))
    } catch {
      toast.error(t('system.tenantSettings.copyInviteLinkFailed'))
    }
  }

  function handleTabChange(nextValue: string) {
    const nextTab = normalizePersonalSettingsTab(nextValue, defaultTab)
    const params = new URLSearchParams(searchParams?.toString() || '')
    if (nextTab === defaultTab) {
      params.delete('tab')
    } else {
      params.set('tab', nextTab)
    }
    const query = params.toString()
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false })
  }

  if (!session) return null

  const accountSummaryItems = [
    { label: t('auth.username'), value: mineInfo?.username || session.username },
    { label: t('system.auth.nickname'), value: mineInfo?.nickname || session.nickname || '-' },
    { label: t('system.personal.roles'), value: (session.roles || []).join(', ') || '-' },
    { label: t('system.personal.permissionCount'), value: String(session.permissions?.length ?? 0) },
    { label: t('system.personal.boundPhone'), value: mineInfo?.phone || '-' },
    { label: t('system.personal.boundEmail'), value: mineInfo?.email || '-' },
  ]

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader className="gap-4">
          <PageHeader title={t('system.personal.settingsTitle')} description={t('system.personal.settingsDescription')} />
          <div className="flex flex-wrap gap-2 text-xs">
            <div className="rounded-full border bg-background px-3 py-1 font-medium">
              {mineInfo?.username || session.username}
            </div>
            <div className="rounded-full border bg-background px-3 py-1 text-muted-foreground">
              {(session.roles || []).join(', ') || t('system.personal.noRoles')}
            </div>
            <div
              className={`rounded-full border px-3 py-1 ${
                mineInfo?.mustCompleteProfile
                  ? 'border-destructive/30 bg-destructive/5 text-destructive'
                  : 'border-emerald-500/20 bg-emerald-500/5 text-emerald-700 dark:text-emerald-300'
              }`}
            >
              {mineInfo?.mustCompleteProfile ? t('system.personal.profileIncomplete') : t('system.personal.profileComplete')}
            </div>
          </div>
        </CardHeader>
      </Card>

      <Tabs value={activeTab} onValueChange={handleTabChange} className="grid gap-4">
        <div className="overflow-x-auto">
          <TabsList className="flex h-auto min-w-max items-center justify-start gap-1 rounded-xl bg-muted/70 p-1">
            <TabsTrigger value="account">{t('system.personal.tabAccount')}</TabsTrigger>
            <TabsTrigger value="profile">{t('system.personal.tabProfile')}</TabsTrigger>
            <TabsTrigger value="invite">{t('system.personal.tabInvite')}</TabsTrigger>
            <TabsTrigger value="notifications">{t('system.personal.tabNotifications')}</TabsTrigger>
            <TabsTrigger value="contact">{t('system.personal.tabContact')}</TabsTrigger>
            <TabsTrigger value="security">{t('system.personal.tabSecurity')}</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="account">
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)]">
            <Card>
              <CardHeader>
                <PageHeader title={t('system.personal.accountInfo')} />
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {accountSummaryItems.map((item) => (
                  <div key={item.label} className="rounded-xl border bg-background/80 px-4 py-3">
                    <div className="text-xs text-muted-foreground">{item.label}</div>
                    <div className="mt-1 break-all text-sm font-medium">{item.value}</div>
                  </div>
                ))}
                <div className="sm:col-span-2 xl:col-span-3">
                  <Button
                    variant="secondary"
                    className="w-full sm:w-auto"
                    onClick={() => {
                      logout()
                      window.location.href = '/login'
                    }}
                  >
                    {t('system.personal.logout')}
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <PageHeader title={t('system.personal.appearance')} />
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="grid gap-2">
                  <Label>{t('system.personal.theme')}</Label>
                  <Select value={theme} onValueChange={(v) => setTheme(v as 'light' | 'dark')}>
                    <SelectTrigger className="w-full sm:max-w-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="light">{t('system.personal.themeLight')}</SelectItem>
                      <SelectItem value="dark">{t('system.personal.themeDark')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="text-sm text-muted-foreground">{t('system.personal.themeHint')}</div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <PageHeader title={t('system.personal.customProfile')} />
            </CardHeader>
            <CardContent className="grid gap-4">
              {mineInfo?.mustCompleteProfile ? (
                <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                  {t('system.personal.missingFields').replace(
                    '{fields}',
                    missingProfileLabels.join(t('system.personal.listSeparator')) || t('system.personal.checkRequiredProfile'),
                  )}
                </div>
              ) : null}

              {(profileSchema.fields || []).length > 0 ? (
                <>
                  <UserProfileForm
                    config={profileSchema}
                    value={profileForm}
                    onChange={setProfileForm}
                    disabled={profileSaving}
                    showHelpText={false}
                    className="grid-cols-1 gap-3"
                  />
                  <div className="flex flex-col gap-2 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      {profileMeta.lastCompletedAt
                        ? t('system.personal.lastCompletedAt').replace('{time}', new Date(profileMeta.lastCompletedAt).toLocaleString())
                        : t('system.personal.noProfileCompletionRecord')}
                    </div>
                    <div>{t('system.personal.configVersion').replace('{version}', String(profileSchema.version || 1))}</div>
                  </div>
                  <div>
                    <Button
                      className="w-full sm:w-auto"
                      disabled={profileSaving}
                      onClick={async () => {
                        if (!session) return
                        setProfileSaving(true)
                        try {
                          const res = await apiFetch<{
                            profile?: Record<string, unknown>
                            profileMeta?: UserProfileMeta
                            profileSchema?: UserProfileFieldsConfig
                            mustCompleteProfile?: boolean
                          }>('/api/v1/auth/profile', {
                            method: 'PUT',
                            session,
                            body: JSON.stringify({
                              profile: profileForm,
                            }),
                          })
                          setProfileForm(res.profile || {})
                          setProfileMeta(normalizeProfileMeta(res.profileMeta))
                          setProfileSchema(normalizeUserProfileFieldsConfig(res.profileSchema))
                          setMineInfo((current) =>
                            current
                              ? {
                                  ...current,
                                  profile: res.profile || {},
                                  profileMeta: normalizeProfileMeta(res.profileMeta),
                                  profileSchema: normalizeUserProfileFieldsConfig(res.profileSchema),
                                  mustCompleteProfile: Boolean(res.mustCompleteProfile),
                                }
                              : current,
                          )
                          setSession({
                            ...session,
                            mustCompleteProfile: Boolean(res.mustCompleteProfile),
                          })
                          toast.success(
                            res.mustCompleteProfile
                              ? t('system.personal.profileSavedContinue')
                              : t('system.personal.profileSaved'),
                          )
                        } catch (err) {
                          toast.error(err instanceof ApiError ? err.message : t('system.personal.profileSaveFailed'))
                        } finally {
                          setProfileSaving(false)
                        }
                      }}
                    >
                      {profileSaving ? t('system.common.saving') : t('system.personal.saveProfile')}
                    </Button>
                  </div>
                </>
              ) : (
                <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                  {t('system.personal.noCustomProfileFields')}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="invite">
          <div className="grid gap-4">
            <Card>
              <CardHeader>
                <PageHeader title={t('system.personal.myInvitations')} />
              </CardHeader>
              <CardContent className="grid gap-4">
                {invitationLoading ? <div className="text-xs text-muted-foreground">{t('system.personal.loadingInvitations')}</div> : null}

                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-xl border px-4 py-3 text-sm">
                    <div className="text-muted-foreground">{t('system.personal.completedInvites')}</div>
                    <div className="mt-1 text-xl font-semibold">{invitationSummary?.usedInviteCount || 0}</div>
                  </div>
                  <div className="rounded-xl border px-4 py-3 text-sm">
                    <div className="text-muted-foreground">{t('system.personal.pendingInviteQuota')}</div>
                    <div className="mt-1 text-xl font-semibold">{invitationSummary?.activeReservedInviteQuota || 0}</div>
                  </div>
                  <div className="rounded-xl border px-4 py-3 text-sm">
                    <div className="text-muted-foreground">{t('system.personal.remainingInviteQuota')}</div>
                    <div className="mt-1 text-xl font-semibold">{invitationSummary?.remainingInviteQuota || 0}</div>
                  </div>
                  <div className="rounded-xl border px-4 py-3 text-sm">
                    <div className="text-muted-foreground">{t('system.personal.pendingInviteCredits')}</div>
                    <div className="mt-1 text-xl font-semibold">{invitationSummary?.pendingInviterRewardCredits || '0'}</div>
                  </div>
                </div>

                <div className="grid gap-3 rounded-xl border p-4 lg:grid-cols-[160px_minmax(0,1fr)_auto] lg:items-center">
                  <div className="grid gap-2">
                    <Label>{t('system.tenantSettings.inviteExpiresDays')}</Label>
                    <Input
                      type="number"
                      min={1}
                      max={365}
                      value={inviteExpiresIn}
                      onChange={(e) => setInviteExpiresIn(Math.max(1, Math.min(365, Number(e.target.value || 7))))}
                    />
                    <div className="text-xs text-muted-foreground">
                      {t('system.personal.inviteCodeCostHint').replace(
                        '{credits}',
                        String(invitationSummary?.config?.inviteCodeCostCredits || 0),
                      )}
                    </div>
                  </div>
                  <div className="grid gap-2">
                    <div className="flex flex-wrap gap-2 text-sm">
                      <span className="rounded-full border px-3 py-1">
                        {t('system.personal.inviterRewardBadge').replace(
                          '{credits}',
                          String(invitationSummary?.config?.inviterRewardCredits || 0),
                        )}
                      </span>
                      <span className="rounded-full border px-3 py-1">
                        {t('system.personal.inviteeRewardBadge').replace(
                          '{credits}',
                          String(invitationSummary?.config?.inviteeRewardCredits || 0),
                        )}
                      </span>
                      <span className="rounded-full border px-3 py-1">
                        {t('system.personal.rewardDelayBadge').replace(
                          '{days}',
                          String(invitationSummary?.config?.rewardDelayDays || 0),
                        )}
                      </span>
                      <span className="rounded-full border px-3 py-1">
                        {t('system.personal.maxInvitesBadge').replace(
                          '{n}',
                          String(invitationSummary?.config?.maxInvitesPerUser || 0),
                        )}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {t('system.personal.inviteCodeHint')}
                    </div>
                    {!invitationSummary?.userCanInvite ? (
                      <div className="text-xs text-muted-foreground">
                        {t('system.personal.noMoreInviteCodes')}
                      </div>
                    ) : null}
                  </div>
                  <div className="flex items-center justify-start lg:justify-end">
                    <Button
                      className="w-full sm:w-auto"
                      disabled={!invitationSummary?.userCanInvite || inviteSubmitting || recyclingInviteCodeId !== null}
                      onClick={() => {
                        void handleGenerateInviteCode()
                      }}
                    >
                      {inviteSubmitting ? t('system.personal.generating') : t('system.personal.generateInviteCode')}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <PageHeader title={t('system.personal.myInviteCodes')} />
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="grid gap-3 md:hidden">
                  {(invitationSummary?.codes || []).map((code) => (
                    <div key={code.inviteCode} className="rounded-xl border p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-sm font-medium">{invitationStatusLabel(code.status, t)}</div>
                          <div className="mt-1 break-all font-mono text-xs text-muted-foreground">{code.inviteCode}</div>
                        </div>
                        <div className="flex shrink-0 flex-col gap-1">
                          {code.canRecycle ? (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={inviteSubmitting || recyclingInviteCodeId === code.id}
                              onClick={() => {
                                void handleRecycleInviteCode(code)
                              }}
                            >
                              {recyclingInviteCodeId === code.id ? t('system.personal.recycling') : t('system.personal.recycle')}
                            </Button>
                          ) : null}
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={recyclingInviteCodeId !== null}
                            onClick={() => {
                              void handleCopyInviteUrl(code)
                            }}
                          >
                            {t('system.tenantSettings.copyLink')}
                          </Button>
                        </div>
                      </div>
                      <div className="mt-3 grid gap-1 text-xs text-muted-foreground">
                        <div>{t('system.personal.expiresAtLabel').replace('{time}', formatDateTime(code.expiresAt))}</div>
                        <div>{t('system.personal.usageLabel').replace('{usage}', describeInviteCodeUsage(code, t))}</div>
                        <div>
                          {(code.invitedAt || code.lastUsedAt)
                            ? t('system.personal.usedAtLabel').replace('{time}', formatDateTime(code.invitedAt || code.lastUsedAt))
                            : t('system.personal.remainingUsesLabel')
                                .replace('{remaining}', String(code.remainingUses))
                                .replace('{max}', String(code.maxUses))}
                        </div>
                        {describeInviteCodeRecovery(code, t) ? (
                          <div>{t('system.personal.recoveryLabel').replace('{recovery}', describeInviteCodeRecovery(code, t))}</div>
                        ) : null}
                      </div>
                    </div>
                  ))}
                  {!invitationLoading && (invitationSummary?.codes || []).length === 0 ? (
                    <div className="rounded-xl border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
                      {t('system.personal.noInviteCodes')}
                    </div>
                  ) : null}
                </div>

                <div className="hidden overflow-x-auto rounded-md border md:block">
                  <Table className="min-w-[760px]">
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('common.status')}</TableHead>
                        <TableHead>{t('system.invitations.inviteCode')}</TableHead>
                        <TableHead>{t('system.personal.expiresAt')}</TableHead>
                        <TableHead>{t('system.personal.usage')}</TableHead>
                        <TableHead>{t('system.personal.recovery')}</TableHead>
                        <TableHead>{t('common.actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(invitationSummary?.codes || []).map((code) => (
                        <TableRow key={code.inviteCode}>
                          <TableCell className="text-xs">{invitationStatusLabel(code.status, t)}</TableCell>
                          <TableCell className="font-mono text-xs">{code.inviteCode}</TableCell>
                          <TableCell className="text-xs">{formatDateTime(code.expiresAt)}</TableCell>
                          <TableCell className="text-xs">
                            <div className="text-sm">{describeInviteCodeUsage(code, t)}</div>
                            {(code.invitedAt || code.lastUsedAt) ? (
                              <div className="text-xs text-muted-foreground">
                                {formatDateTime(code.invitedAt || code.lastUsedAt)}
                              </div>
                            ) : (
                              <div className="text-xs text-muted-foreground">
                                {t('system.personal.remainingUsesLabel')
                                  .replace('{remaining}', String(code.remainingUses))
                                  .replace('{max}', String(code.maxUses))}
                              </div>
                            )}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {describeInviteCodeRecovery(code, t) || '-'}
                          </TableCell>
                          <TableCell>
                            <div className="flex flex-wrap items-center gap-1.5">
                              {code.canRecycle ? (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={inviteSubmitting || recyclingInviteCodeId === code.id}
                                  onClick={() => {
                                    void handleRecycleInviteCode(code)
                                  }}
                                >
                                  {recyclingInviteCodeId === code.id ? t('system.personal.recycling') : t('system.personal.recycle')}
                                </Button>
                              ) : null}
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={recyclingInviteCodeId !== null}
                                onClick={() => {
                                  void handleCopyInviteUrl(code)
                                }}
                              >
                                {t('system.tenantSettings.copyLink')}
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                      {!invitationLoading && (invitationSummary?.codes || []).length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={6} className="py-6 text-center text-muted-foreground">
                            {t('system.personal.noInviteCodes')}
                          </TableCell>
                        </TableRow>
                      ) : null}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <PageHeader title={t('system.invitations.title')} />
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="grid gap-3 md:hidden">
                  {(invitationRecords?.list || []).map((record) => (
                    <div key={record.id} className="rounded-xl border p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="text-sm font-medium">{invitationStatusLabel(record.relation, t)}</div>
                        <div className="text-xs text-muted-foreground">{formatDateTime(record.createdAt)}</div>
                      </div>
                      <div className="mt-3 grid gap-1 text-xs text-muted-foreground">
                        <div>{t('system.personal.peerLabel').replace('{name}', resolveInvitationRecordPeerLabel(record))}</div>
                        <div className="break-all font-mono">
                          {t('system.personal.inviteCodeLabel').replace('{code}', record.inviteCode || '-')}
                        </div>
                        <div>{t('system.personal.creditIncreaseLabel').replace('{value}', resolveInvitationRewardProgress(record, t))}</div>
                        <div>
                          {t('system.personal.rewardStatusLabel')
                            .replace('{inviter}', invitationStatusLabel(record.inviterRewardStatus, t))
                            .replace('{invitee}', invitationStatusLabel(record.inviteeRewardStatus, t))}
                        </div>
                      </div>
                    </div>
                  ))}
                  {!invitationRecordsLoading && (invitationRecords?.list || []).length === 0 ? (
                    <div className="rounded-xl border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
                      {t('system.invitations.emptyRecords')}
                    </div>
                  ) : null}
                </div>

                <div className="hidden overflow-x-auto rounded-md border md:block">
                  <Table className="min-w-[760px]">
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('system.personal.relation')}</TableHead>
                        <TableHead>{t('system.common.time')}</TableHead>
                        <TableHead>{t('system.personal.peer')}</TableHead>
                        <TableHead>{t('system.invitations.inviteCode')}</TableHead>
                        <TableHead>{t('system.personal.creditIncrease')}</TableHead>
                        <TableHead>{t('system.invitations.rewardStatus')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(invitationRecords?.list || []).map((record) => (
                        <TableRow key={record.id}>
                          <TableCell>{invitationStatusLabel(record.relation, t)}</TableCell>
                          <TableCell>{formatDateTime(record.createdAt)}</TableCell>
                          <TableCell>{resolveInvitationRecordPeerLabel(record)}</TableCell>
                          <TableCell className="font-mono text-xs">{record.inviteCode || '-'}</TableCell>
                          <TableCell className="text-xs">{resolveInvitationRewardProgress(record, t)}</TableCell>
                          <TableCell className="text-xs">
                            {t('system.personal.rewardStatusLabel')
                              .replace('{inviter}', invitationStatusLabel(record.inviterRewardStatus, t))
                              .replace('{invitee}', invitationStatusLabel(record.inviteeRewardStatus, t))}
                          </TableCell>
                        </TableRow>
                      ))}
                      {!invitationRecordsLoading && (invitationRecords?.list || []).length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={6} className="py-6 text-center text-muted-foreground">
                            {t('system.invitations.emptyRecords')}
                          </TableCell>
                        </TableRow>
                      ) : null}
                    </TableBody>
                  </Table>
                </div>
                <SimplePagination
                  total={invitationRecords?.total || 0}
                  currentPage={invitationRecords?.currentPage || 1}
                  pageSize={invitationRecords?.pageSize || 10}
                  disabled={invitationRecordsLoading}
                  onChange={(page) => {
                    void loadInvitationRecords(page)
                  }}
                />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="notifications">
          <div className="grid gap-4">
            <PageHeader
                  title={t('system.personal.systemChannelBinding')}
                  description={t('system.personal.systemChannelBindingDescription')}
            />
            <Card>
              <CardContent className="grid gap-3 lg:grid-cols-2">
                <div className="rounded-xl border p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium">{t('system.personal.wechatChannel')}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {t('system.personal.wechatChannelDescription')}
                      </div>
                    </div>
                    <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                      {t('system.personal.scanToBind')}
                    </span>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    className="mt-4 w-full sm:w-auto"
                    disabled={messageChannelBinding}
                    onClick={() => {
                      void startMessageChannelBind('wechat')
                    }}
                  >
                    {t('system.personal.getWechatQr')}
                  </Button>
                </div>

                <div className="rounded-xl border p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium">{t('system.personal.feishuChannel')}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {t('system.personal.feishuChannelDescription')}
                      </div>
                    </div>
                    <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                      {t('system.personal.scanToBind')}
                    </span>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    className="mt-4 w-full sm:w-auto"
                    disabled={messageChannelBinding}
                    onClick={() => {
                      void startMessageChannelBind('feishu')
                    }}
                  >
                    {t('system.personal.getFeishuQr')}
                  </Button>
                </div>

                {messageChannelBindResult ? (
                  <div className="grid gap-4 rounded-xl border bg-muted/30 p-4 lg:col-span-2 md:grid-cols-[240px_minmax(0,1fr)]">
                    <div className="grid gap-2">
                      <div className="text-sm font-medium">
                        {t('system.personal.scanEntry').replace(
                          '{type}',
                          messageChannelTypeLabel(messageChannelBindResult.channelType, t),
                        )}
                      </div>
                      <div className="flex min-h-[236px] items-center justify-center rounded-xl border bg-background p-3">
                        {messageChannelBindResult.qrImageUrl ? (
                          <img
                            src={messageChannelBindResult.qrImageUrl}
                            alt={t('system.personal.bindQrAlt').replace(
                              '{type}',
                              messageChannelTypeLabel(messageChannelBindResult.channelType, t),
                            )}
                            className="h-[220px] w-[220px] rounded-md object-contain"
                          />
                        ) : (
                          <div className="text-center text-xs text-muted-foreground">{t('system.personal.noQrReturned')}</div>
                        )}
                      </div>
                      {messageChannelBindResult.qrUrl ? (
                        <a
                          href={messageChannelBindResult.qrUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="break-all text-xs text-primary underline-offset-4 hover:underline"
                        >
                          {t('system.personal.openQrLink')}
                        </a>
                      ) : null}
                    </div>
                    <div className="grid content-start gap-3">
                      <div>
                        <div className="text-sm font-medium">{t('system.personal.bindingCode')}</div>
                        <div className="mt-2 inline-flex rounded-xl border bg-background px-5 py-3 font-mono text-3xl font-semibold tracking-[0.35em]">
                          {messageChannelBindResult.bindingCode ||
                            messageChannelBindResult.qrText ||
                            messageChannelBindResult.bindToken}
                        </div>
                      </div>
                      <div className="rounded-xl border bg-background p-3 text-xs text-muted-foreground">
                        {(messageChannelBindResult.instructions?.length
                          ? messageChannelBindResult.instructions
                          : messageChannelBindFallbackInstructions(messageChannelBindResult, t)
                        ).map((item, index) => (
                          <div key={`${index}-${item}`} className="flex gap-2 py-1">
                            <span className="font-mono text-xs">{index + 1}.</span>
                            <span>{item}</span>
                          </div>
                        ))}
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs">
                        <span className="rounded-full border bg-background px-2 py-0.5">
                          {t('system.personal.statusLabel').replace(
                            '{status}',
                            messageChannelBindStatusLabel(messageChannelBindResult.status, t),
                          )}
                        </span>
                        <span className="rounded-full border bg-background px-2 py-0.5">
                          {t('system.personal.gatewayLabel').replace(
                            '{status}',
                            messageChannelBindResult.gatewayReady
                              ? t('system.personal.gatewayReady')
                              : t('system.personal.gatewayWaiting'),
                          )}
                        </span>
                        {messageChannelBindResult.expiresAt ? (
                          <span className="rounded-full border bg-background px-2 py-0.5">
                            {t('system.personal.validUntilLabel').replace(
                              '{time}',
                              formatDateTime(messageChannelBindResult.expiresAt),
                            )}
                          </span>
                        ) : null}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {t('system.personal.bindingAutoCheckHint')}
                      </div>
                    </div>
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
              <Card>
                <CardHeader>
                  <PageHeader title={t('system.personal.myChannels')} description={t('system.personal.myChannelsDescription')} />
                </CardHeader>
                <CardContent className="grid gap-3">
                  {messageChannelsLoading ? <div className="text-xs text-muted-foreground">{t('system.personal.loadingChannels')}</div> : null}
                  {(messageChannels || []).map((channel) => (
                    <div key={channel.id} className="rounded-xl border p-4">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="grid gap-1 text-sm">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium">{channel.name}</span>
                            <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                              {messageChannelTypeLabel(channel.channelType, t)}
                            </span>
                            {channel.isDefault ? (
                              <span className="rounded-full border px-2 py-0.5 text-xs">{t('system.personal.defaultChannel')}</span>
                            ) : null}
                            <span className="rounded-full border px-2 py-0.5 text-xs">
                              {messageChannelBindStatusLabel(channel.status, t)}
                            </span>
                          </div>
                          <div className="break-all text-xs text-muted-foreground">
                            {t('system.personal.externalUserLabel').replace(
                              '{value}',
                              channel.displayName || channel.externalUserId || channel.target || '-',
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {t('system.personal.channelTimeline')
                              .replace('{boundAt}', formatDateTime(channel.boundAt))
                              .replace('{lastInboundAt}', formatDateTime(channel.lastInboundAt))
                              .replace('{lastSentAt}', formatDateTime(channel.lastSentAt))}
                            {channel.secretConfigured ? t('system.personal.secretConfiguredSuffix') : ''}
                          </div>
                          {channel.lastError ? (
                            <div className="break-all text-xs text-destructive">
                              {t('system.personal.lastErrorLabel').replace('{error}', channel.lastError)}
                            </div>
                          ) : null}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={testingMessageChannelId === channel.id || channel.status !== 'active'}
                            onClick={() => {
                              void testMessageChannel(channel)
                            }}
                          >
                            {testingMessageChannelId === channel.id ? t('system.personal.testing') : t('system.personal.test')}
                          </Button>
                          {channel.channelType === 'webhook' ? (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setEditingMessageChannelId(channel.id)
                                setMessageChannelForm(mapChannelToForm(channel))
                              }}
                            >
                              {t('common.edit')}
                            </Button>
                          ) : null}
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button size="sm" variant="outline">
                                {t('system.personal.unbindDelete')}
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>{t('system.personal.unbindDelete')}</AlertDialogTitle>
                                <AlertDialogDescription>
                                  {t('system.personal.confirmDeleteChannel').replace('{name}', channel.name)}
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                                <AlertDialogAction
                                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                  onClick={() => {
                                    void deleteMessageChannel(channel)
                                  }}
                                >
                                  {t('common.delete')}
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </div>
                    </div>
                  ))}
                  {!messageChannelsLoading && messageChannels.length === 0 ? (
                    <div className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                      {t('system.personal.noChannels')}
                    </div>
                  ) : null}
                </CardContent>
              </Card>

              <PageHeader
                    title={
                      editingMessageChannelId
                        ? t('system.personal.editAdvancedWebhook')
                        : t('system.personal.addAdvancedWebhook')
                    }
                    description={t('system.personal.advancedWebhookDescription')}
              />
              <Card>
                <CardContent className="grid gap-4">
                  <div className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
                    {t('system.personal.advancedWebhookHint')}
                  </div>

                  <div className="grid gap-2">
                    <Label>{t('system.personal.channelType')}</Label>
                    <Select value={messageChannelForm.channelType}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="webhook">{t('system.personal.genericWebhook')}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid gap-2">
                    <Label>{t('system.personal.channelName')}</Label>
                    <Input
                      value={messageChannelForm.name}
                      disabled={messageChannelSaving}
                      onChange={(e) => setMessageChannelForm((prev) => ({ ...prev, name: e.target.value }))}
                      placeholder={t('system.personal.channelNamePlaceholder')}
                    />
                  </div>

                  <div className="grid gap-2">
                    <Label>{t('system.personal.webhookUrl')}</Label>
                    <Textarea
                      value={messageChannelForm.target}
                      disabled={messageChannelSaving}
                      onChange={(e) => setMessageChannelForm((prev) => ({ ...prev, target: e.target.value }))}
                      placeholder="https://example.com/webhook"
                    />
                  </div>

                  <div className="grid gap-2">
                    <Label>{t('system.personal.secretTokenOptional')}</Label>
                    <Input
                      type="password"
                      value={messageChannelForm.secret}
                      disabled={messageChannelSaving}
                      onChange={(e) => setMessageChannelForm((prev) => ({ ...prev, secret: e.target.value }))}
                      placeholder={
                        editingMessageChannelId
                          ? t('system.personal.keepSecretPlaceholder')
                          : t('system.personal.bearerTokenPlaceholder')
                      }
                    />
                  </div>

                  <div className="flex flex-wrap items-center gap-4 rounded-xl border p-3 text-sm">
                    <label className="flex items-center gap-2">
                      <Switch
                        checked={messageChannelForm.status === 'active'}
                        onCheckedChange={(checked) =>
                          setMessageChannelForm((prev) => ({ ...prev, status: checked ? 'active' : 'disabled' }))
                        }
                      />
                      {t('common.enabled')}
                    </label>
                    <label className="flex items-center gap-2">
                      <Switch
                        checked={messageChannelForm.isDefault}
                        onCheckedChange={(checked) =>
                          setMessageChannelForm((prev) => ({ ...prev, isDefault: Boolean(checked) }))
                        }
                      />
                      {t('system.personal.setDefault')}
                    </label>
                  </div>

                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Button
                      className="w-full sm:w-auto"
                      disabled={messageChannelSaving}
                      onClick={() => {
                        void saveMessageChannel()
                      }}
                    >
                      {messageChannelSaving
                        ? t('system.common.saving')
                        : editingMessageChannelId
                          ? t('system.personal.saveWebhook')
                          : t('system.personal.addWebhook')}
                    </Button>
                    {editingMessageChannelId ? (
                      <Button
                        type="button"
                        variant="outline"
                        className="w-full sm:w-auto"
                        disabled={messageChannelSaving}
                        onClick={() => {
                          setEditingMessageChannelId(null)
                          setMessageChannelForm(defaultMessageChannelForm(t))
                        }}
                      >
                        {t('system.personal.cancelEdit')}
                      </Button>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="contact">
          <Card>
            <CardHeader>
              <PageHeader title={t('system.personal.contactVerification')} />
            </CardHeader>
            <CardContent className="grid gap-4">
              {contactLoading ? <div className="text-xs text-muted-foreground">{t('system.personal.loadingContactInfo')}</div> : null}

              <div className="grid gap-4 xl:grid-cols-2">
                {verificationCapabilities.sms ? (
                  <div className="grid gap-3 rounded-xl border p-4">
                    <div className="text-sm font-medium">{t('system.personal.phoneCodeBinding')}</div>
                    <div className="text-xs text-muted-foreground">
                      {t('system.personal.currentBindingLabel').replace(
                        '{value}',
                        mineInfo?.phone || t('system.personal.notBound'),
                      )}
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="bindPhone">{t('system.auth.phone')}</Label>
                      <Input
                        id="bindPhone"
                        value={phoneForm.phone}
                        disabled={contactLoading || phoneBinding || phoneSending}
                        onChange={(e) => setPhoneForm((prev) => ({ ...prev, phone: e.target.value }))}
                        placeholder={t('system.auth.registerPhoneRequired')}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="bindPhoneCode">{t('system.personal.verificationCode')}</Label>
                      <div className="flex flex-col gap-2 sm:flex-row">
                        <Input
                          id="bindPhoneCode"
                          className="sm:flex-1"
                          value={phoneForm.code}
                          disabled={contactLoading || phoneBinding}
                          onChange={(e) => setPhoneForm((prev) => ({ ...prev, code: e.target.value }))}
                          placeholder={t('system.personal.smsCodePlaceholder')}
                        />
                        <Button
                          variant="outline"
                          className="w-full sm:w-auto sm:shrink-0"
                          disabled={phoneCooldown > 0 || !phoneForm.phone.trim() || phoneSending}
                          onClick={async () => {
                            if (!session) return
                            const phone = phoneForm.phone.trim()
                            if (!phone) {
                              toast.error(t('system.auth.registerPhoneRequired'))
                              return
                            }
                            setPhoneSending(true)
                            const id = toast.loading(t('system.personal.sendingCode'))
                            try {
                              const data = await apiFetch<{ cooldownSeconds?: number; debugCode?: string }>(
                                '/api/v1/auth/phone/send-code',
                                {
                                  method: 'POST',
                                  session,
                                  body: JSON.stringify({ phone }),
                                },
                              )
                              const cooldown = Number(data.cooldownSeconds || 60)
                              setPhoneCooldown(Number.isFinite(cooldown) && cooldown > 0 ? cooldown : 60)
                              if (data.debugCode) {
                                setPhoneForm((prev) => ({ ...prev, code: String(data.debugCode) }))
                                toast.success(t('system.personal.codeSentWithDebug').replace('{code}', String(data.debugCode)), { id })
                              } else {
                                toast.success(t('system.personal.codeSent'), { id })
                              }
                            } catch (err) {
                              const message = err instanceof ApiError ? err.message : t('system.common.sendFailed')
                              toast.error(message, { id })
                            } finally {
                              setPhoneSending(false)
                            }
                          }}
                        >
                          {phoneSending ? t('system.common.sending') : phoneCooldown > 0 ? `${phoneCooldown}s` : t('system.personal.sendCode')}
                        </Button>
                      </div>
                    </div>
                    <div>
                      <Button
                        className="w-full sm:w-auto"
                        disabled={phoneBinding || !phoneForm.phone.trim() || !phoneForm.code.trim() || contactLoading}
                        onClick={async () => {
                          if (!session) return
                          const phone = phoneForm.phone.trim()
                          const code = phoneForm.code.trim()
                          if (!phone || !code) return
                          setPhoneBinding(true)
                          const id = toast.loading(t('system.personal.bindingPhone'))
                          try {
                            const data = await apiFetch<{ phone?: string }>('/api/v1/auth/phone/bind', {
                              method: 'POST',
                              session,
                              body: JSON.stringify({ phone, code }),
                            })
                            setMineInfo((prev) => (prev ? { ...prev, phone: data.phone || phone } : prev))
                            setPhoneForm((prev) => ({ ...prev, code: '' }))
                            toast.success(t('system.personal.phoneBound'), { id })
                          } catch (err) {
                            const message = err instanceof ApiError ? err.message : t('system.personal.bindFailed')
                            toast.error(message, { id })
                          } finally {
                            setPhoneBinding(false)
                          }
                        }}
                      >
                        {phoneBinding ? t('system.personal.binding') : t('system.personal.bindPhone')}
                      </Button>
                    </div>
                  </div>
                ) : null}

                {verificationCapabilities.email ? (
                  <div className="grid gap-3 rounded-xl border p-4">
                    <div className="text-sm font-medium">{t('system.personal.emailCodeBinding')}</div>
                    <div className="text-xs text-muted-foreground">
                      {t('system.personal.currentBindingLabel').replace(
                        '{value}',
                        mineInfo?.email || t('system.personal.notBound'),
                      )}
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="bindEmail">{t('system.auth.email')}</Label>
                      <Input
                        id="bindEmail"
                        value={emailForm.email}
                        disabled={contactLoading || emailBinding || emailSending}
                        onChange={(e) => setEmailForm((prev) => ({ ...prev, email: e.target.value }))}
                        placeholder={t('system.auth.registerEmailRequired')}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="bindEmailCode">{t('system.personal.verificationCode')}</Label>
                      <div className="flex flex-col gap-2 sm:flex-row">
                        <Input
                          id="bindEmailCode"
                          className="sm:flex-1"
                          value={emailForm.code}
                          disabled={contactLoading || emailBinding}
                          onChange={(e) => setEmailForm((prev) => ({ ...prev, code: e.target.value }))}
                          placeholder={t('system.personal.emailCodePlaceholder')}
                        />
                        <Button
                          variant="outline"
                          className="w-full sm:w-auto sm:shrink-0"
                          disabled={emailCooldown > 0 || !emailForm.email.trim() || emailSending}
                          onClick={async () => {
                            if (!session) return
                            const email = emailForm.email.trim()
                            if (!email) {
                              toast.error(t('system.auth.registerEmailRequired'))
                              return
                            }
                            setEmailSending(true)
                            const id = toast.loading(t('system.personal.sendingCode'))
                            try {
                              const data = await apiFetch<{ cooldownSeconds?: number; debugCode?: string }>(
                                '/api/v1/auth/email/send-code',
                                {
                                  method: 'POST',
                                  session,
                                  body: JSON.stringify({ email }),
                                },
                              )
                              const cooldown = Number(data.cooldownSeconds || 60)
                              setEmailCooldown(Number.isFinite(cooldown) && cooldown > 0 ? cooldown : 60)
                              if (data.debugCode) {
                                setEmailForm((prev) => ({ ...prev, code: String(data.debugCode) }))
                                toast.success(t('system.personal.codeSentWithDebug').replace('{code}', String(data.debugCode)), { id })
                              } else {
                                toast.success(t('system.personal.codeSent'), { id })
                              }
                            } catch (err) {
                              const message = err instanceof ApiError ? err.message : t('system.common.sendFailed')
                              toast.error(message, { id })
                            } finally {
                              setEmailSending(false)
                            }
                          }}
                        >
                          {emailSending ? t('system.common.sending') : emailCooldown > 0 ? `${emailCooldown}s` : t('system.personal.sendCode')}
                        </Button>
                      </div>
                    </div>
                    <div>
                      <Button
                        className="w-full sm:w-auto"
                        disabled={emailBinding || !emailForm.email.trim() || !emailForm.code.trim() || contactLoading}
                        onClick={async () => {
                          if (!session) return
                          const email = emailForm.email.trim()
                          const code = emailForm.code.trim()
                          if (!email || !code) return
                          setEmailBinding(true)
                          const id = toast.loading(t('system.personal.bindingEmail'))
                          try {
                            const data = await apiFetch<{ email?: string }>('/api/v1/auth/email/bind', {
                              method: 'POST',
                              session,
                              body: JSON.stringify({ email, code }),
                            })
                            setMineInfo((prev) => (prev ? { ...prev, email: data.email || email } : prev))
                            setEmailForm((prev) => ({ ...prev, code: '' }))
                            toast.success(t('system.personal.emailBound'), { id })
                          } catch (err) {
                            const message = err instanceof ApiError ? err.message : t('system.personal.bindFailed')
                            toast.error(message, { id })
                          } finally {
                            setEmailBinding(false)
                          }
                        }}
                      >
                        {emailBinding ? t('system.personal.binding') : t('system.personal.bindEmail')}
                      </Button>
                    </div>
                  </div>
                ) : null}
              </div>

              {!verificationCapabilities.sms && !verificationCapabilities.email ? (
                <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                  {t('system.personal.verificationDisabledHint')}
                </div>
              ) : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security">
          <Card>
            <CardHeader>
              <PageHeader title={t('system.personal.changePassword')} />
            </CardHeader>
            <CardContent className="grid gap-4 lg:grid-cols-3">
              <div className="grid gap-2">
                <Label htmlFor="oldPassword">{t('system.personal.currentPassword')}</Label>
                <Input
                  id="oldPassword"
                  type="password"
                  autoComplete="current-password"
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="newPassword">{t('system.user.newPassword')}</Label>
                <Input
                  id="newPassword"
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="confirmPassword">{t('system.personal.confirmNewPassword')}</Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
                {passwordMismatch ? <div className="text-xs text-destructive">{t('system.personal.passwordMismatch')}</div> : null}
              </div>

              <div className="lg:col-span-3">
                <Button
                  className="w-full sm:w-auto"
                  disabled={!canSubmitPassword || savingPassword}
                  onClick={async () => {
                    if (!session) return
                    setSavingPassword(true)
                    const id = toast.loading(t('system.personal.changingPassword'))
                    try {
                      await apiFetch('/api/v1/users/change-password', {
                        method: 'POST',
                        session,
                        body: JSON.stringify({
                          oldPassword,
                          newPassword,
                        }),
                      })
                      toast.success(t('system.personal.passwordChanged'), { id })
                      logout()
                      window.location.href = '/login'
                    } catch (err) {
                      const message = err instanceof ApiError ? err.message : t('system.personal.changeFailed')
                      toast.error(message, { id })
                    } finally {
                      setSavingPassword(false)
                    }
                  }}
                >
                  {savingPassword ? t('system.common.submitting') : t('system.personal.saveNewPassword')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
