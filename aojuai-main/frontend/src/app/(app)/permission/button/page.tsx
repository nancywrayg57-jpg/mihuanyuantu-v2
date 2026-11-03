'use client'

import { useMemo } from 'react'

import { RequirePermission } from '@/components/auth/require-permission'
import { PageHeader } from '@/components/page/page-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { hasAnyPermission } from '@/lib/auth'
import { useT } from '@/lib/i18n'
import { useAuth } from '@/hooks/useAuth'

export default function PermissionButtonPage() {
  const t = useT()
  const { session } = useAuth()

  const permsText = useMemo(() => {
    const perms = session?.permissions || []
    if (session?.isSuperuser) return t('system.permission.superuserAllPermissions')
    if (perms.length === 0) return t('system.permission.noPermissionCodes')
    return perms.join('\n')
  }, [session?.isSuperuser, session?.permissions, t])

  return (
    <div className="grid gap-4">
      <PageHeader
        title={t('system.permission.buttonTitle')}
        description={t('system.permission.buttonDescription')}
        actions={
          session?.isSuperuser ? (
            <Badge variant="secondary">Superuser</Badge>
          ) : (
            <Badge variant="outline">User</Badge>
          )
        }
      />
      <Card>
        <CardContent className="grid gap-4">
          <div className="grid gap-2">
            <div className="text-sm font-medium">{t('system.permission.currentPermissionCodes')}</div>
            <pre className="max-h-56 overflow-auto rounded-md border bg-muted p-3 text-xs leading-5">{permsText}</pre>
          </div>

          <Card>
            <CardHeader>
              <PageHeader title={t('system.permission.componentMode')} description={t('system.permission.componentModeDescription')} />
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <RequirePermission anyOf={['permission:btn:add']}>
                <Button variant="secondary">{t('system.permission.visibleWithAddCode')}</Button>
              </RequirePermission>
              <RequirePermission anyOf={['permission:btn:edit']}>
                <Button>{t('system.permission.visibleWithEditCode')}</Button>
              </RequirePermission>
              <RequirePermission anyOf={['permission:btn:add', 'permission:btn:edit', 'permission:btn:delete']}>
                <Button variant="destructive">{t('system.permission.visibleWithAnyCode')}</Button>
              </RequirePermission>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <PageHeader title={t('system.permission.functionMode')} description={t('system.permission.functionModeDescription')} />
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {hasAnyPermission(session, ['permission:btn:add']) ? <Button variant="secondary">{t('system.permission.addVisible')}</Button> : null}
              {hasAnyPermission(session, ['permission:btn:edit']) ? <Button>{t('system.permission.editVisible')}</Button> : null}
              {hasAnyPermission(session, ['permission:btn:delete']) ? (
                <Button variant="destructive">{t('system.permission.deleteVisible')}</Button>
              ) : null}
            </CardContent>
          </Card>
        </CardContent>
      </Card>
    </div>
  )
}
