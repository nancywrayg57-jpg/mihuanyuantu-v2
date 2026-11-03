'use client'

import Link from 'next/link'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Moon, Sun } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { UserProfileForm } from '@/components/profile/user-profile-form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError, apiFetch } from '@/lib/api'
import {
  normalizeRegistrationBasicFieldsConfig,
  registrationFieldMode,
  type RegistrationBasicFieldsConfig,
} from '@/lib/registration-fields'
import {
  collectMissingRequiredProfileFields,
  normalizeUserProfileFieldsConfig,
  type UserProfileFieldsConfig,
} from '@/lib/user-profile-fields'
import { NeuralBackground } from '@/components/login/neural-background'
import { useAuth } from '@/hooks/useAuth'
import { useSiteBranding } from '@/hooks/useSiteBranding'
import { useTheme } from '@/hooks/useTheme'
import { useT } from '@/lib/i18n'

import styles from '../login/login.module.css'

type InvitationConfig = {
  enabled?: boolean
  inviterRewardCredits?: number
  inviteeRewardCredits?: number
  rewardDelayDays?: number
  maxInvitesPerUser?: number
  inviteCodeCostCredits?: number
}

type RegistrationConfigResponse = {
  enabled: boolean
  requireAudit: boolean
  defaultRole: string
  tenantCode?: string
  tenantName?: string
  inviterUsername?: string
  inviterNickname?: string
  basicFields?: RegistrationBasicFieldsConfig
  invitation?: InvitationConfig
  userProfileFields?: UserProfileFieldsConfig
  tenantBound?: boolean
  tenantSource?: 'invite' | 'query' | 'domain' | 'default' | 'none'
}

type ParseInviteResponse = {
  tenantCode: string
  tenantName: string
  requireAudit: boolean
  inviterUsername?: string
  inviterNickname?: string
  basicFields?: RegistrationBasicFieldsConfig
  invitation?: InvitationConfig
  userProfileFields?: UserProfileFieldsConfig
  tenantBound?: boolean
  tenantSource?: 'invite' | 'query' | 'domain' | 'default' | 'none'
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

export function RegisterClient() {
  const t = useT()
  const { session } = useAuth()
  const { theme, toggleTheme, mounted } = useTheme()
  const router = useRouter()
  const searchParams = useSearchParams()

  const inviteCode = String(searchParams.get('invite') || '').trim()
  const tenantCodeFromUrl = String(searchParams.get('tenantCode') || '').trim()

  const [tenantCodeInput, setTenantCodeInput] = useState(tenantCodeFromUrl)
  const [tenantName, setTenantName] = useState('')
  const [requireAudit, setRequireAudit] = useState(true)
  const [registrationEnabled, setRegistrationEnabled] = useState(true)
  const [tenantContextLocked, setTenantContextLocked] = useState(Boolean(inviteCode || tenantCodeFromUrl))
  const [, setTenantSource] = useState<'invite' | 'query' | 'domain' | 'default' | 'none'>('none')
  const [inviterLabel, setInviterLabel] = useState('')
  const [invitationConfig, setInvitationConfig] = useState<InvitationConfig>(normalizeInvitationConfig(null))
  const [basicFieldsConfig, setBasicFieldsConfig] = useState<RegistrationBasicFieldsConfig>(
    normalizeRegistrationBasicFieldsConfig(null),
  )
  const [profileConfig, setProfileConfig] = useState<UserProfileFieldsConfig>(normalizeUserProfileFieldsConfig(null))
  const [profile, setProfile] = useState<Record<string, unknown>>({})
  const [loadingContext, setLoadingContext] = useState(false)
  const [contextInitialized, setContextInitialized] = useState(false)
  const [lastResolvedTenantQuery, setLastResolvedTenantQuery] = useState<string | null>(null)
  const [contextError, setContextError] = useState<string | null>(null)

  const [username, setUsername] = useState('')
  const [nickname, setNickname] = useState('')
  const [password, setPassword] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const nicknameMode = registrationFieldMode(basicFieldsConfig.nickname)
  const emailMode = registrationFieldMode(basicFieldsConfig.email)
  const phoneMode = registrationFieldMode(basicFieldsConfig.phone)
  const showTenantCodeInput = !inviteCode && !tenantContextLocked
  const inviteOnlyMode = !inviteCode && !registrationEnabled && Boolean(invitationConfig.enabled)
  const canRenderRegistrationFields = !contextError && (Boolean(inviteCode) || registrationEnabled)
  const inviteRewardSummary =
    invitationConfig.inviterRewardCredits || invitationConfig.inviteeRewardCredits
      ? t('system.auth.registerRewardSummary')
          .replace('{inviter}', String(invitationConfig.inviterRewardCredits || 0))
          .replace('{invitee}', String(invitationConfig.inviteeRewardCredits || 0))
      : ''

  function applyRegistrationContext(
    config: RegistrationConfigResponse | ParseInviteResponse,
    options?: {
      nextTenantCodeInput?: string
      lockTenantContext?: boolean
    },
  ) {
    if (typeof options?.nextTenantCodeInput === 'string') {
      setTenantCodeInput(options.nextTenantCodeInput)
    }
    if (typeof options?.lockTenantContext === 'boolean') {
      setTenantContextLocked(options.lockTenantContext)
    }
    setTenantSource(config.tenantSource || 'none')
    setTenantName(config.tenantName || '')
    setRequireAudit(Boolean(config.requireAudit))
    setRegistrationEnabled('enabled' in config ? Boolean(config.enabled) : true)
    setInvitationConfig(normalizeInvitationConfig(config.invitation))
    setBasicFieldsConfig(normalizeRegistrationBasicFieldsConfig(config.basicFields))
    setProfileConfig(normalizeUserProfileFieldsConfig(config.userProfileFields))
    setInviterLabel(
      'inviterNickname' in config
        ? config.inviterNickname || config.inviterUsername || ''
        : '',
    )
  }

  useEffect(() => {
    if (!session) return
    router.replace(session.mustCompleteProfile ? '/personal/profile-required' : '/welcome')
  }, [router, session])

  useEffect(() => {
    let ignore = false

    async function loadContext() {
      setLoadingContext(true)
      setContextError(null)
      setSubmitError(null)
      try {
        if (inviteCode) {
          const parsed = await apiFetch<ParseInviteResponse>(
            `/api/v1/auth/parse-invite?code=${encodeURIComponent(inviteCode)}`,
          )
          if (ignore) return
          applyRegistrationContext(parsed, {
            nextTenantCodeInput: parsed.tenantCode || '',
            lockTenantContext: true,
          })
          setLastResolvedTenantQuery(parsed.tenantCode || '')
          setContextInitialized(true)
          return
        }

        if (tenantCodeFromUrl) {
          const query = `?tenant_code=${encodeURIComponent(tenantCodeFromUrl)}`
          const config = await apiFetch<RegistrationConfigResponse>(`/api/v1/auth/registration-config${query}`)
          if (ignore) return
          applyRegistrationContext(config, {
            nextTenantCodeInput: config.tenantCode || tenantCodeFromUrl,
            lockTenantContext: true,
          })
          setLastResolvedTenantQuery(tenantCodeFromUrl)
          setContextInitialized(true)
          return
        }

        const config = await apiFetch<RegistrationConfigResponse>('/api/v1/auth/registration-config')
        if (ignore) return
        const domainLocked = Boolean(config.tenantBound && config.tenantSource === 'domain')
        applyRegistrationContext(config, {
          nextTenantCodeInput: domainLocked ? config.tenantCode || '' : '',
          lockTenantContext: domainLocked,
        })
        setLastResolvedTenantQuery('')
        setContextInitialized(true)
      } catch (err) {
        if (!ignore) {
          const message = err instanceof ApiError ? err.message : t('system.auth.registerConfigLoadFailed')
          setContextError(message)
          setRegistrationEnabled(false)
          setContextInitialized(true)
        }
      } finally {
        if (!ignore) setLoadingContext(false)
      }
    }

    void loadContext()
    return () => {
      ignore = true
    }
  }, [inviteCode, tenantCodeFromUrl, t])

  useEffect(() => {
    if (!contextInitialized || inviteCode || tenantContextLocked) return

    const normalizedTenantCode = tenantCodeInput.trim()
    if (lastResolvedTenantQuery === normalizedTenantCode) return

    let ignore = false
    const timer = window.setTimeout(async () => {
      setLoadingContext(true)
      setContextError(null)
      try {
        const query = normalizedTenantCode ? `?tenant_code=${encodeURIComponent(normalizedTenantCode)}` : ''
        const config = await apiFetch<RegistrationConfigResponse>(`/api/v1/auth/registration-config${query}`)
        if (ignore) return
        applyRegistrationContext(config, {
          nextTenantCodeInput: normalizedTenantCode,
          lockTenantContext: false,
        })
        setLastResolvedTenantQuery(normalizedTenantCode)
      } catch (err) {
        if (!ignore) {
          const message = err instanceof ApiError ? err.message : t('system.auth.registerConfigLoadFailed')
          setContextError(message)
        }
      } finally {
        if (!ignore) setLoadingContext(false)
      }
    }, normalizedTenantCode ? 350 : 0)

    return () => {
      ignore = true
      window.clearTimeout(timer)
    }
  }, [contextInitialized, inviteCode, lastResolvedTenantQuery, tenantCodeInput, tenantContextLocked, t])

  useEffect(() => {
    if (nicknameMode === 'hidden') setNickname('')
  }, [nicknameMode])

  useEffect(() => {
    if (emailMode === 'hidden') setEmail('')
  }, [emailMode])

  useEffect(() => {
    if (phoneMode === 'hidden') setPhone('')
  }, [phoneMode])

  if (session) return null

  return (
    <AuthShell isDark={theme === 'dark'} mounted={mounted} onToggleTheme={toggleTheme}>
      <form
        className={`${styles.loginForm} ${styles.registerForm}`}
        onSubmit={async (e) => {
          e.preventDefault()
          setSubmitError(null)
          if (!registrationEnabled) {
            setSubmitError(t('system.auth.registrationClosed'))
            return
          }
          if (showTenantCodeInput && !tenantCodeInput.trim()) {
            setSubmitError(t('system.auth.registerTenantRequired'))
            return
          }
          if (!username.trim()) {
            setSubmitError(t('system.auth.registerUsernameRequired'))
            return
          }
          if (nicknameMode === 'required' && !nickname.trim()) {
            setSubmitError(t('system.auth.registerNicknameRequired'))
            return
          }
          if (emailMode === 'required' && !email.trim()) {
            setSubmitError(t('system.auth.registerEmailRequired'))
            return
          }
          if (phoneMode === 'required' && !phone.trim()) {
            setSubmitError(t('system.auth.registerPhoneRequired'))
            return
          }

          const missingRequiredFields = collectMissingRequiredProfileFields(profileConfig, profile, {
            enforceOnRegisterOnly: true,
          })
          if (missingRequiredFields.length > 0) {
            setSubmitError(t('system.auth.registerProfileRequired').replace('{fields}', missingRequiredFields.map((field) => field.label).join('、')))
            return
          }

          setSubmitting(true)
          setSubmitError(null)
          try {
            const response = await apiFetch<{ requireAudit: boolean }>('/api/v1/auth/register', {
              method: 'POST',
              body: JSON.stringify({
                username: username.trim(),
                nickname: nicknameMode === 'hidden' ? undefined : nickname.trim() || undefined,
                password,
                email: emailMode === 'hidden' ? undefined : email.trim() || undefined,
                phone: phoneMode === 'hidden' ? undefined : phone.trim() || undefined,
                profile,
                tenantCode: inviteCode ? undefined : tenantCodeInput.trim() || undefined,
                inviteCode: inviteCode || undefined,
              }),
            })
            toast.success(response.requireAudit ? t('system.auth.registerSuccessAudit') : t('system.auth.registerSuccessLogin'))
            router.replace('/login')
          } catch (err) {
            const message = err instanceof ApiError ? err.message : t('system.auth.registerFailed')
            setSubmitError(message)
            toast.error(message)
          } finally {
            setSubmitting(false)
          }
        }}
      >
        <div className="grid gap-1">
          <div className={styles.formEyebrow}>{inviteCode ? 'INVITE' : 'REGISTER'}</div>
          <div className={styles.formTitle}>{inviteCode ? t('system.auth.acceptInvite') : t('system.auth.registerAccount')}</div>
          <div className={styles.formSubtitle}>
            {inviteCode
              ? t('system.auth.joinTenant').replace('{tenant}', tenantName || t('system.auth.currentTenant'))
              : tenantName
                ? t('system.auth.rulesFromTenant').replace('{tenant}', tenantName)
                : t('system.auth.continueAfterAccount')}
          </div>
        </div>

        <div className="grid gap-3">
          <div className="flex flex-wrap gap-2">
            {tenantName ? <Badge variant="outline">{tenantName}</Badge> : null}
            <Badge variant={registrationEnabled || inviteCode ? 'default' : 'secondary'}>
              {inviteOnlyMode
                ? t('system.auth.inviteOnly')
                : registrationEnabled || inviteCode
                  ? requireAudit
                    ? t('system.auth.auditAfterRegister')
                    : t('system.auth.loginAfterRegister')
                  : t('system.auth.registrationPaused')}
            </Badge>
            {inviteCode ? <Badge variant="outline">{t('system.auth.inviteJoin')}</Badge> : null}
          </div>

          {inviteCode ? (
            <div className="rounded-xl border border-white/20 bg-card/10 p-4 text-sm">
              <div className="flex items-center justify-between gap-3">
                <div className="font-medium">{tenantName || tenantCodeInput || t('system.auth.currentTenant')}</div>
                {inviterLabel ? <span className="text-xs text-muted-foreground">{t('system.auth.inviter').replace('{name}', inviterLabel)}</span> : null}
              </div>
              <div className="mt-2 text-xs text-muted-foreground">
                {requireAudit ? t('system.auth.auditFlowHint') : t('system.auth.loginAfterSuccessHint')}
                {inviteRewardSummary ? ` ${inviteRewardSummary}。` : ''}
              </div>
            </div>
          ) : null}

          {loadingContext ? <div className="text-xs text-muted-foreground">{t('system.auth.loadingRegisterConfig')}</div> : null}
          {contextError ? <div className="text-sm text-destructive">{contextError}</div> : null}
          {!loadingContext && !inviteCode && !registrationEnabled && !contextError ? (
            <div className="rounded-xl border border-dashed bg-muted/10 p-4 text-sm text-muted-foreground">
              {invitationConfig.enabled
                ? t('system.auth.inviteOnlyClosedHint')
                : t('system.auth.registrationClosedHint')}
            </div>
          ) : null}
        </div>

        {canRenderRegistrationFields ? (
        <div className="grid gap-3">
          {showTenantCodeInput ? (
            <div className="grid gap-2">
              <Label htmlFor="tenantCode">{t('system.auth.tenantCode')}</Label>
              <Input
                id="tenantCode"
                value={tenantCodeInput}
                onChange={(e) => {
                  setTenantCodeInput(e.target.value)
                  setSubmitError(null)
                }}
                placeholder={t('system.auth.tenantCodePlaceholder')}
                autoComplete="organization"
              />
              <div className="text-xs text-muted-foreground">
                {t('system.auth.tenantCodeHint')}
              </div>
            </div>
          ) : null}

          <div className="grid gap-2">
            <Label htmlFor="username">{t('auth.username')}</Label>
            <Input
              id="username"
              value={username}
              onChange={(e) => {
                setUsername(e.target.value)
                setSubmitError(null)
              }}
              placeholder={t('system.auth.usernamePatternPlaceholder')}
              required
            />
          </div>

          {nicknameMode !== 'hidden' ? (
            <div className="grid gap-2">
              <Label htmlFor="nickname">{t('system.auth.nickname')}{nicknameMode === 'required' ? ' *' : ''}</Label>
              <Input
                id="nickname"
                value={nickname}
                onChange={(e) => {
                  setNickname(e.target.value)
                  setSubmitError(null)
                }}
                placeholder={nicknameMode === 'required' ? t('system.auth.registerNicknameRequired') : t('system.auth.nicknameOptionalPlaceholder')}
                required={nicknameMode === 'required'}
              />
            </div>
          ) : null}

          {emailMode !== 'hidden' ? (
            <div className="grid gap-2">
              <Label htmlFor="email">{t('system.auth.email')}{emailMode === 'required' ? ' *' : ''}</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  setSubmitError(null)
                }}
                placeholder={emailMode === 'required' ? t('system.auth.registerEmailRequired') : t('system.auth.optional')}
                required={emailMode === 'required'}
              />
            </div>
          ) : null}

          {phoneMode !== 'hidden' ? (
            <div className="grid gap-2">
              <Label htmlFor="phone">{t('system.auth.phone')}{phoneMode === 'required' ? ' *' : ''}</Label>
              <Input
                id="phone"
                value={phone}
                onChange={(e) => {
                  setPhone(e.target.value)
                  setSubmitError(null)
                }}
                placeholder={phoneMode === 'required' ? t('system.auth.registerPhoneRequired') : t('system.auth.optional')}
                required={phoneMode === 'required'}
              />
            </div>
          ) : null}

          <div className="grid gap-2">
            <Label htmlFor="password">{t('auth.password')}</Label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value)
                setSubmitError(null)
              }}
              placeholder={t('system.auth.passwordStrengthPlaceholder')}
              required
            />
            <div className="text-xs text-muted-foreground">{t('system.auth.passwordRule')}</div>
          </div>

          {profileConfig.enabled ? (
            <div className="grid gap-3 rounded-xl border border-white/20 bg-card/10 p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium">{t('system.auth.profileSectionTitle')}</div>
                <div className="text-xs text-muted-foreground">
                  {t('system.auth.profileSectionHint')}
                </div>
              </div>
              <UserProfileForm
                config={profileConfig}
                value={profile}
                onChange={setProfile}
                disabled={submitting}
                className="grid-cols-1 md:grid-cols-1"
                showHelpText={false}
              />
            </div>
          ) : null}
        </div>
        ) : null}

        {submitError ? <div className="text-sm text-destructive">{submitError}</div> : null}

        <div className="grid gap-2">
          {canRenderRegistrationFields ? (
            <Button type="submit" disabled={submitting || loadingContext || (!registrationEnabled && !inviteCode)}>
              {submitting
                ? t('system.common.submitting')
                : inviteCode
                  ? t('system.auth.createAndJoin')
                  : requireAudit
                    ? t('system.auth.submitRegistration')
                    : t('system.auth.createAccount')}
            </Button>
          ) : null}
          <Button type="button" variant="outline" asChild>
            <Link href="/login">{t('system.auth.backToLogin')}</Link>
          </Button>
        </div>
      </form>
    </AuthShell>
  )
}

function AuthShell({
  isDark,
  mounted,
  onToggleTheme,
  children,
}: {
  isDark: boolean
  mounted: boolean
  onToggleTheme: () => void
  children: ReactNode
}) {
  const t = useT()
  const branding = useSiteBranding()
  const techTags = [t('system.auth.registerTagUnified'), t('system.auth.registerTagInvite')]

  return (
    <div className={styles.loginPage}>
      <NeuralBackground isDark={isDark} />
      <div className={styles.gradientOverlay} />
      <div className={styles.vignetteOverlay} />

      <div className={styles.themeSwitchContainer}>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={onToggleTheme}
          aria-label={t('system.auth.toggleTheme')}
          disabled={!mounted}
        >
          {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>

      <div className={styles.loginContainer}>
        <div className={styles.heroSection}>
          <div className={styles.techTags}>
            {techTags.map((t) => (
              <span key={t} className={styles.techTag}>
                {t}
              </span>
            ))}
          </div>

          <div className={styles.logoSection}>
            <div className={styles.logoGlow} />
            <div className={styles.logoText}>
              {['A', 'O', 'J', 'U'].map((letter, index) => (
                <span
                  key={letter}
                  className={styles.logoLetter}
                  style={{ animationDelay: `${index * 0.15}s` }}
                >
                  {letter}
                </span>
              ))}
            </div>
          </div>

          <div className={styles.subtitle}>Tenant Registration</div>

          <div className={styles.glassCard}>
            <div className={styles.glassCardInner}>
              <div className={styles.cardTitle}>{t('system.auth.registerHeroTitle')}</div>
              <div className={styles.cardDivider} />
              <div className={styles.cardDescription}>
                {t('system.auth.registerHeroLines').split('|').map((line, index, lines) => (
                  <span key={line}>
                    {line}
                    {index < lines.length - 1 ? <br /> : null}
                  </span>
                ))}
              </div>
            </div>
            <div className={styles.glassCardFooter}>
              <span>{t('system.auth.autoTenant')}</span>
              <span className={styles.statusIndicator}>
                <span className={styles.statusDot} />
                {t('system.auth.registerByTenantRules')}
              </span>
            </div>
          </div>
        </div>

        <div className={styles.loginBox}>{children}</div>
      </div>

      <footer className={styles.footer}>{branding.footerText}</footer>
    </div>
  )
}
