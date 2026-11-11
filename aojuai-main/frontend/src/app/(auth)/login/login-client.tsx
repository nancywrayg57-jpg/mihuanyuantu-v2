'use client'

import Link from 'next/link'
import type { ReactNode } from 'react'
import { useEffect, useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Moon, Sun } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { fetchLoginChallenge, loginByPassword, type LoginChallenge } from '@/lib/auth-api'
import { demoAccounts } from '@/lib/demo-accounts'
import { NeuralBackground } from '@/components/login/neural-background'
import { useAuth } from '@/hooks/useAuth'
import { useSiteBranding } from '@/hooks/useSiteBranding'
import { useTheme } from '@/hooks/useTheme'
import { useT } from '@/lib/i18n'
import { sanitizeNextPath } from '@/lib/sanitize-next-path'

import styles from './login.module.css'

export function LoginClient() {
  const t = useT()
  const { session, setSession } = useAuth()
  const { theme, toggleTheme, mounted } = useTheme()
  const router = useRouter()
  const searchParams = useSearchParams()

  const nextPath = useMemo(
    () => sanitizeNextPath(searchParams.get('next'), '/welcome'),
    [searchParams],
  )

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [captcha, setCaptcha] = useState('')
  const [challenge, setChallenge] = useState<LoginChallenge | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function refreshChallenge() {
    try {
      const next = await fetchLoginChallenge('web-login')
      if (!next.challengeId) {
        throw new Error('验证码挑战未返回')
      }
      if (!next.imageBase64) {
        throw new Error(
          '验证码图片未返回：请重启后端 API（加载含 imageBase64 的版本）后再点刷新',
        )
      }
      setChallenge(next)
      // 生产不得预填；开发态仅展示提示码，仍须看图/手输
      setCaptcha('')
      setError(null)
    } catch (err) {
      setChallenge(null)
      setError(err instanceof Error ? err.message : '验证码加载失败')
    }
  }

  useEffect(() => {
    void refreshChallenge()
  }, [])

  useEffect(() => {
    if (!session) return
    router.replace(
      session.mustCompleteProfile ? '/personal/profile-required' : nextPath,
    )
  }, [nextPath, router, session])

  const fillDemoAccount = (account: { username: string; password: string }) => {
    setUsername(account.username)
    setPassword(account.password)
    void refreshChallenge()
  }

  if (session) return null

  return (
    <LoginShell
      isDark={theme === 'dark'}
      mounted={mounted}
      onToggleTheme={toggleTheme}
      onSubmit={async () => {
        setError(null)
        setSubmitting(true)
        try {
          if (!challenge?.challengeId) {
            throw new Error('请先获取验证码')
          }
          if (!captcha.trim()) {
            throw new Error('请输入验证码')
          }
          const nextSession = await loginByPassword(
            username,
            password,
            challenge.challengeId,
            captcha.trim(),
          )
          setSession(nextSession)
          toast.success(t('system.auth.loginSuccess'))
          router.replace(nextSession.mustCompleteProfile ? '/personal/profile-required' : nextPath)
        } catch (err) {
          const message = err instanceof Error ? err.message : t('system.auth.loginFailed')
          setError(message)
          toast.error(message)
          void refreshChallenge()
        } finally {
          setSubmitting(false)
        }
      }}
    >
      <div className="grid gap-3">
        <div className="grid gap-2">
          <Label htmlFor="username">{t('auth.username')}</Label>
          <Input
            id="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="admin"
            required
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="password">{t('auth.password')}</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="captcha">验证码</Label>
          <div className="flex items-center gap-2">
            {challenge?.imageBase64 ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={challenge.imageBase64}
                alt="登录验证码"
                width={160}
                height={52}
                className="h-[52px] w-[160px] shrink-0 rounded border bg-white object-contain"
              />
            ) : (
              <div className="flex h-[52px] w-[160px] shrink-0 items-center justify-center rounded border text-xs text-muted-foreground">
                加载中…
              </div>
            )}
            <Button type="button" variant="outline" onClick={() => void refreshChallenge()}>
              刷新
            </Button>
          </div>
          <Input
            id="captcha"
            autoComplete="one-time-code"
            value={captcha}
            onChange={(e) => setCaptcha(e.target.value)}
            placeholder="请输入图中 6 位数字"
            required
          />
          {challenge?.devCode ? (
            <p className="text-xs text-muted-foreground">
              开发提示码：{challenge.devCode}（仅 DEBUG/测试开关；正式环境不返回）
            </p>
          ) : null}
        </div>
        {error ? <div className="text-sm text-destructive">{error}</div> : null}
        <Button type="submit" disabled={submitting || !challenge}>
          {submitting ? t('auth.loggingIn') : t('auth.login')}
        </Button>
        <Button type="button" variant="outline" asChild>
          <Link href="/register">{t('auth.register')}</Link>
        </Button>

        <div className="space-y-2 pt-1">
          <div className="text-xs text-muted-foreground">{t('system.auth.loginDemoAccounts')}</div>
          <div className="flex flex-wrap gap-2">
            {demoAccounts.map((account) => (
              <Badge
                key={account.username}
                variant="outline"
                className="cursor-pointer hover:bg-accent"
                onClick={() => fillDemoAccount(account)}
              >
                {t(account.labelKey)}: {account.username}
              </Badge>
            ))}
          </div>
        </div>
      </div>
    </LoginShell>
  )
}

function LoginShell({
  isDark,
  mounted,
  onToggleTheme,
  onSubmit,
  children,
}: {
  isDark: boolean
  mounted: boolean
  onToggleTheme: () => void
  onSubmit: () => Promise<void>
  children: ReactNode
}) {
  const t = useT()
  const branding = useSiteBranding()
  const techTags = [
    'NEURAL NETWORKS',
    'GENERATIVE AI',
    'DEEP LEARNING',
    'COGNITIVE COMPUTING',
    'LLM',
    'TRANSFORMER',
  ]

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
              {branding.letters.map((letter, index) => (
                <span
                  key={`${letter}-${index}`}
                  className={styles.logoLetter}
                  style={{ animationDelay: `${index * 0.15}s` }}
                >
                  {letter}
                </span>
              ))}
            </div>
          </div>

          <div className={styles.subtitle}>Artificial Intelligence Frontier</div>

          <div className={styles.glassCard}>
            <div className={styles.glassCardInner}>
              <div className={styles.cardTitle}>{t('system.auth.loginHeroTitle')}</div>
              <div className={styles.cardDivider} />
              <div className={styles.cardDescription}>
                {t('system.auth.loginHeroLines').split('|').map((line, index, lines) => (
                  <span key={line}>
                    {line}
                    {index < lines.length - 1 ? <br /> : null}
                  </span>
                ))}
              </div>
            </div>
            <div className={styles.glassCardFooter}>
              <span>System Status: Optimal</span>
              <span className={styles.statusIndicator}>
                <span className={styles.statusDot} />
                Live Connected
              </span>
            </div>
          </div>
        </div>

        <div className={styles.loginBox}>
          <form
            className={styles.loginForm}
            onSubmit={async (e) => {
              e.preventDefault()
              await onSubmit()
            }}
          >
            <div className={styles.formTitle}>{t('system.auth.loginFormTitle')}</div>
            {children}
          </form>
        </div>
      </div>

      <footer className={styles.footer}>{branding.footerText}</footer>
    </div>
  )
}
