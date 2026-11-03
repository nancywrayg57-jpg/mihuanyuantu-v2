'use client'

import Link from 'next/link'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/hooks/useAuth'
import { useT } from '@/lib/i18n'

export default function DashboardPage() {
  const t = useT()
  const { session } = useAuth()

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>{t('system.dashboard.title')}</CardTitle>
          <CardDescription>{t('system.dashboard.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div>
            {t('system.dashboard.currentUser')}:
            <span className="font-medium"> {session?.nickname || session?.username}</span>
          </div>
          <div>{t('system.personal.roles')}: {(session?.roles || []).join(', ') || '-'}</div>
          <div>{t('system.personal.permissionCount')}: {session?.permissions?.length ?? 0}</div>
          <div className="flex flex-wrap gap-2 pt-2">
            <Button asChild variant="secondary">
              <Link href="/welcome">{t('system.layout.home')}</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/system/user">{t('system.common.user')}</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/system/role">{t('system.role.role')}</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/system/menu">{t('system.menu.menu')}</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/schedule">{t('system.layout.schedule')}</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
