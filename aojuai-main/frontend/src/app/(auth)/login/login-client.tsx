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
import { ApiError } from '@/lib/api'
import { loginByPassword } from '@/lib/auth-api'
import { demoAccounts } from '@/lib/demo-accounts'
import { NeuralBackground } from '@/components/login/neural-background'
import { useAuth } from '@/hooks/useAuth'
import { useSiteBranding } from '@/hooks/useSiteBranding'
import { useTheme } from '@/hooks/useTheme'
import { useT } from '@/lib/i18n'

import styles from './login.module.css'

export function LoginClient() {
  const t = useT()
  const { session, setSession } = useAuth()
  const { theme, toggleTheme, mounted } = useTheme()
  const router = useRouter()
  const searchParams = useSearchParams()

  const nextPath = useMemo(() => {
    const next = searchParams.get('next')
    if (!next) return '/welcome'
    return next.startsWith('/') ? next : '/'
  }, [searchParams])

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!session) return
    router.replace(session.mustCompleteProfile ? '/personal/profile-required' : '/welcome')
  }, [router, session])

  const fillDemoAccount = (account: { username: string; password: string }) => {
    setUsername(account.username)
    setPassword(account.password)
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
          const nextSession = await loginByPassword(username, password)
          setSession(nextSession)
          toast.success(t('system.auth.loginSuccess'))
          router.replace(nextSession.mustCompleteProfile ? '/personal/profile-required' : nextPath)
        } catch (err) {
          const message = err instanceof ApiError ? err.message : t('system.auth.loginFailed')
          setError(message)
          toast.error(message)
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
        {error ? <div className="text-sm text-destructive">{error}</div> : null}
        <Button type="submit" disabled={submitting}>
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
