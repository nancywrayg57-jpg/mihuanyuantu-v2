'use client'

import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'

import { PageHeader } from '@/components/page/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ApiError } from '@/lib/api'
import { fetchLoginChallenge, loginByPassword } from '@/lib/auth-api'
import { demoAccounts } from '@/lib/demo-accounts'
import { useT } from '@/lib/i18n'
import { useAuth } from '@/hooks/useAuth'

export default function PermissionPage() {
  const t = useT()
  const { session, setSession } = useAuth()
  const router = useRouter()

  const accountOptions = useMemo(() => demoAccounts.map((a) => ({ value: a.username, label: t(a.labelKey) })), [t])
  const [selectedUsername, setSelectedUsername] = useState(session?.username || accountOptions[0]?.value || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedAccount = useMemo(
    () => demoAccounts.find((a) => a.username === selectedUsername) || null,
    [selectedUsername],
  )

  return (
    <div className="grid gap-4">
      <PageHeader
        title={t('system.permission.pageTitle')}
        description={t('system.permission.pageDescription')}
      />
      <Card>
        <CardContent className="grid gap-4 md:max-w-2xl">
          <div className="text-sm text-muted-foreground">
            {t('system.permission.currentAccount')}: <span className="font-medium text-foreground">{session?.nickname || session?.username}</span>
            <span className="mx-2 text-muted-foreground">/</span>
            {t('system.permission.roles')}: <span className="font-medium text-foreground">{(session?.roles || []).join(', ') || '-'}</span>
          </div>

          <div className="grid gap-2 md:grid-cols-[220px_1fr] md:items-center">
            <div className="text-sm font-medium">{t('system.permission.switchTo')}</div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <div className="w-full sm:w-64">
                <Select value={selectedUsername} onValueChange={setSelectedUsername}>
                  <SelectTrigger>
                    <SelectValue placeholder={t('system.permission.selectDemoAccount')} />
                  </SelectTrigger>
                  <SelectContent>
                    {accountOptions.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}（{o.value}）
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <Button
                disabled={!selectedAccount || loading}
                onClick={async () => {
                  if (!selectedAccount) return
                  setError(null)
                  setLoading(true)
                  try {
                    // Demo switch still goes through realphotos login (FR-001 captcha).
                    const challenge = await fetchLoginChallenge()
                    const code = String(challenge.devCode || '').trim()
                    if (!code) {
                      throw new Error(
                        '演示账号切换需要开发验证码（REALPHOTOS_ALLOW_DEV_CAPTCHA）；请改用登录页图形验证码',
                      )
                    }
                    const nextSession = await loginByPassword(
                      selectedAccount.username,
                      selectedAccount.password,
                      challenge.challengeId,
                      code,
                    )
                    setSession(nextSession)
                    router.refresh()
                  } catch (err) {
                    setError(
                      err instanceof ApiError
                        ? err.message
                        : err instanceof Error
                          ? err.message
                          : t('system.permission.switchFailed'),
                    )
                  } finally {
                    setLoading(false)
                  }
                }}
              >
                {loading ? t('system.permission.switching') : t('system.permission.switchAccount')}
              </Button>
            </div>
          </div>

          {error ? <div className="text-sm text-destructive">{error}</div> : null}

          <div className="text-xs text-muted-foreground">
            {t('system.permission.demoAccountHint')}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
