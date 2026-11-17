'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

import { PageHeader } from '@/components/page/page-header'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/hooks/useAuth'
import { useT } from '@/lib/i18n'
import { REALPHOTOS_HOME, isRealphotosSession } from '@/lib/realphotos-session'

export default function WelcomePage() {
  const t = useT()
  const router = useRouter()
  const { session } = useAuth()

  // 2026-11-17：蜜獾原图账号不再停留在平台欢迎页，直接进业务工作台。
  useEffect(() => {
    if (isRealphotosSession(session)) router.replace(REALPHOTOS_HOME)
  }, [router, session])

  return (
    <div className="grid gap-4">
      <PageHeader
        title={t('system.welcome.title')}
        description={t('system.welcome.description')}
        actions={<Badge variant="outline">{t('system.welcome.badge')}</Badge>}
      />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t('system.welcome.cardTitle')}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm leading-6 text-muted-foreground">
          {t('system.welcome.cardBody')}
        </CardContent>
      </Card>
    </div>
  )
}
