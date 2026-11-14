'use client'

import Link from 'next/link'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Moon, Sun } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { fetchLoginChallenge, registerMerchant, type LoginChallenge } from '@/lib/auth-api'
import { NeuralBackground } from '@/components/login/neural-background'
import { useAuth } from '@/hooks/useAuth'
import { useSiteBranding } from '@/hooks/useSiteBranding'
import { useTheme } from '@/hooks/useTheme'
import { useT } from '@/lib/i18n'

import styles from '../login/login.module.css'

export function RegisterClient() {
  const t = useT()
  const { session } = useAuth()
  const { theme, toggleTheme, mounted } = useTheme()
  const router = useRouter()

  const [username, setUsername] = useState('')
  const [nickname, setNickname] = useState('')
  const [password, setPassword] = useState('')
  const [captcha, setCaptcha] = useState('')
  const [challenge, setChallenge] = useState<LoginChallenge | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function refreshChallenge() {
    try {
      const next = await fetchLoginChallenge('web-register')
      if (!next.challengeId) {
        throw new Error('验证码挑战未返回')
      }
      if (!next.imageBase64) {
        throw new Error('验证码图片未返回：请重启后端 API 后再点刷新')
      }
      setChallenge(next)
      setCaptcha('')
      setError(null)
    } catch (err) {
      setChallenge(null)
      setError(err instanceof Error ? err.message : t('system.auth.registerConfigLoadFailed'))
    }
  }

  useEffect(() => {
    void refreshChallenge()
  }, [])

  useEffect(() => {
    if (!session) return
    router.replace(session.mustCompleteProfile ? '/personal/profile-required' : '/welcome')
  }, [router, session])

  if (session) return null

  return (
    <AuthShell isDark={theme === 'dark'} mounted={mounted} onToggleTheme={toggleTheme}>
      <form
        className={`${styles.loginForm} ${styles.registerForm}`}
        onSubmit={async (e) => {
          e.preventDefault()
          setError(null)
          if (!username.trim()) {
            setError(t('system.auth.registerUsernameRequired'))
            return
          }
          if (!password) {
            setError(t('system.auth.passwordRule'))
            return
          }
          if (!challenge?.challengeId) {
            setError('请先获取验证码')
            return
          }
          if (!captcha.trim()) {
            setError('请输入验证码')
            return
          }

          setSubmitting(true)
          try {
            await registerMerchant(
              username.trim(),
              password,
              nickname.trim() || undefined,
              challenge.challengeId,
              captcha.trim(),
            )
            toast.success(t('system.auth.registerSuccessLogin'))
            router.replace('/login')
          } catch (err) {
            const message = err instanceof Error ? err.message : t('system.auth.registerFailed')
            setError(message)
            toast.error(message)
            void refreshChallenge()
          } finally {
            setSubmitting(false)
          }
        }}
      >
        <div className="grid gap-1">
          <div className={styles.formEyebrow}>REGISTER</div>
          <div className={styles.formTitle}>{t('system.auth.registerAccount')}</div>
          <div className={styles.formSubtitle}>{t('system.auth.registerMerchantHint')}</div>
        </div>

        <div className="grid gap-3">
          <div className="grid gap-2">
            <Label htmlFor="username">{t('auth.username')}</Label>
            <Input
              id="username"
              value={username}
              onChange={(e) => {
                setUsername(e.target.value)
                setError(null)
              }}
              placeholder={t('system.auth.usernamePatternPlaceholder')}
              autoComplete="username"
              required
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="nickname">{t('system.auth.nickname')}</Label>
            <Input
              id="nickname"
              value={nickname}
              onChange={(e) => {
                setNickname(e.target.value)
                setError(null)
              }}
              placeholder={t('system.auth.nicknameOptionalPlaceholder')}
              autoComplete="nickname"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="password">{t('auth.password')}</Label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value)
                setError(null)
              }}
              placeholder={t('system.auth.passwordStrengthPlaceholder')}
              required
            />
            <div className="text-xs text-muted-foreground">{t('system.auth.passwordRule')}</div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="captcha">验证码</Label>
            <div className="flex items-center gap-2">
              {challenge?.imageBase64 ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={challenge.imageBase64}
                  alt="注册验证码"
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
          </div>

          {error ? <div className="text-sm text-destructive">{error}</div> : null}

          <Button type="submit" disabled={submitting || !challenge}>
            {submitting ? t('system.common.submitting') : t('system.auth.createAccount')}
          </Button>
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
            {techTags.map((tag) => (
              <span key={tag} className={styles.techTag}>
                {tag}
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

          <div className={styles.subtitle}>Merchant Registration</div>

          <div className={styles.glassCard}>
            <div className={styles.glassCardInner}>
              <div className={styles.cardTitle}>{t('system.auth.registerHeroTitleMerchant')}</div>
              <div className={styles.cardDivider} />
              <div className={styles.cardDescription}>
                {t('system.auth.registerHeroLinesMerchant').split('|').map((line, index, lines) => (
                  <span key={line}>
                    {line}
                    {index < lines.length - 1 ? <br /> : null}
                  </span>
                ))}
              </div>
            </div>
            <div className={styles.glassCardFooter}>
              <span>{t('system.auth.registerCreatesTenant')}</span>
              <span className={styles.statusIndicator}>
                <span className={styles.statusDot} />
                {t('system.auth.loginAfterRegister')}
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
