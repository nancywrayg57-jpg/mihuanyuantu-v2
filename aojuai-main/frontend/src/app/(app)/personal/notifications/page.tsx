'use client'

import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ApiError, apiFetch } from '@/lib/api'
import { useT } from '@/lib/i18n'
import { useAuth } from '@/hooks/useAuth'

type PageResponse<T> = {
  list: T[]
  total: number
  pageSize: number
  currentPage: number
}

type NotificationListItem = {
  id: number
  category: string
  title: string
  content?: string | null
  isRead: boolean
  createdAt?: string | null
}

export default function MyNotificationsPage() {
  const t = useT()
  const { session } = useAuth()

  const [page, setPage] = useState(1)
  const [data, setData] = useState<PageResponse<NotificationListItem> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch<PageResponse<NotificationListItem>>(
        `/api/v1/notifications?currentPage=${page}&pageSize=10`,
        { session },
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
  }, [page, session?.accessToken])

  if (!session) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('system.personal.notificationsTitle')}</CardTitle>
        <CardDescription>{t('system.personal.notificationsDescription')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={load} disabled={loading}>
            {t('common.refresh')}
          </Button>
          <Button
            variant="secondary"
            onClick={async () => {
              if (!session) return
              setError(null)
              try {
                await apiFetch('/api/v1/notifications/read-all', {
                  method: 'PUT',
                  session,
                })
                await load()
              } catch (err) {
                setError(err instanceof ApiError ? err.message : t('system.common.operationFailed'))
              }
            }}
            disabled={loading}
          >
            {t('system.notifications.markAllRead')}
          </Button>
          <div className="ml-auto text-sm text-muted-foreground">
            {data ? t('system.common.pageTotal').replace('{page}', String(data.currentPage)).replace('{total}', String(data.total)) : null}
          </div>
        </div>

        {error ? <div className="text-sm text-destructive">{error}</div> : null}

        <div className="divide-y rounded-md border">
          {(data?.list || []).length ? (
            data?.list.map((item) => (
              <div key={item.id} className="p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-medium">
                    {item.title}
                    {!item.isRead ? (
                      <span className="ml-2 rounded bg-destructive px-1.5 py-0.5 text-xs text-destructive-foreground">
                        {t('system.notifications.unread')}
                      </span>
                    ) : null}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {item.createdAt ? new Date(item.createdAt).toLocaleString() : ''}
                  </div>
                </div>
                {item.content ? (
                  <div className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">
                    {item.content}
                  </div>
                ) : null}
              </div>
            ))
          ) : (
            <div className="p-3 text-sm text-muted-foreground">{loading ? t('common.loading') : t('system.personal.noMessages')}</div>
          )}
        </div>

        <div className="flex justify-between">
          <Button
            variant="outline"
            disabled={page <= 1 || loading}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            {t('common.prevPage')}
          </Button>
          <Button
            variant="outline"
            disabled={loading || (data ? data.currentPage * data.pageSize >= data.total : true)}
            onClick={() => setPage((p) => p + 1)}
          >
            {t('common.nextPage')}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
