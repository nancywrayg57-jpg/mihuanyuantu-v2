'use client'

import { useEffect, useState } from 'react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ApiError, apiFetch } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'
import { useT } from '@/lib/i18n'

type PageResponse<T> = {
  list: T[]
  total: number
  pageSize: number
  currentPage: number
}

type OperationLogListItem = {
  id: number
  username?: string | null
  module: string
  action: string
  status: string
  method?: string | null
  path?: string | null
  createdAt?: string | null
}

export default function OperationLogsPage() {
  const t = useT()
  const { session } = useAuth()
  const { targetTenant, targetTenantId } = useTenant()
  const [data, setData] = useState<PageResponse<OperationLogListItem> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch<PageResponse<OperationLogListItem>>(
        '/api/v1/operation-logs?currentPage=1&pageSize=20',
        { session, tenantId: targetTenantId },
      )
      setData(res)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('system.common.loadFailed'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('system.operationLogs.title')}</CardTitle>
        <CardDescription>
          {t('system.operationLogs.description')}
          {session?.isSuperuser && targetTenant ? (
            <span className="ml-2 text-xs text-muted-foreground">
              {t('system.common.targetTenant')
                .replace('{name}', targetTenant.name)
                .replace('{code}', targetTenant.code)}
            </span>
          ) : null}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={load} disabled={loading}>
            {t('common.refresh')}
          </Button>
          <div className="ml-auto text-sm text-muted-foreground">
            {data ? t('common.totalItems').replace('{n}', String(data.total)) : null}
          </div>
        </div>
        {error ? <div className="text-sm text-destructive">{error}</div> : null}
        <div className="overflow-x-auto rounded-md border">
          <table className="min-w-full text-sm">
            <thead className="bg-muted text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left">{t('system.common.time')}</th>
                <th className="px-3 py-2 text-left">{t('system.common.user')}</th>
                <th className="px-3 py-2 text-left">{t('system.common.module')}</th>
                <th className="px-3 py-2 text-left">{t('system.common.action')}</th>
                <th className="px-3 py-2 text-left">{t('common.status')}</th>
                <th className="px-3 py-2 text-left">{t('system.common.path')}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {(data?.list || []).map((row) => (
                <tr key={row.id}>
                  <td className="px-3 py-2">
                    {row.createdAt ? new Date(row.createdAt).toLocaleString() : ''}
                  </td>
                  <td className="px-3 py-2">{row.username || '-'}</td>
                  <td className="px-3 py-2">{row.module}</td>
                  <td className="px-3 py-2">{row.action}</td>
                  <td className="px-3 py-2">{row.status}</td>
                  <td className="px-3 py-2">{row.method ? `${row.method} ${row.path || ''}` : row.path || ''}</td>
                </tr>
              ))}
              {!loading && (data?.list || []).length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-center text-muted-foreground" colSpan={6}>
                    {t('common.empty')}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}
