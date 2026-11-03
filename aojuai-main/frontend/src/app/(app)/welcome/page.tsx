'use client'

import { PageHeader } from '@/components/page/page-header'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useT } from '@/lib/i18n'

export default function WelcomePage() {
  const t = useT()

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
