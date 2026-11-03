'use client'

import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { CollapsibleFilters } from '@/components/list/collapsible-filters'
import { SimplePagination } from '@/components/list/simple-pagination'
import { PageHeader } from '@/components/page/page-header'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, apiFetch } from '@/lib/api'
import { hasAnyPermission } from '@/lib/auth'
import { parseIdList } from '@/lib/parsers'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'
import { useT } from '@/lib/i18n'

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

type BulkSendResponse = {
  requested: number
  sent: number
}

export default function NotificationsPage() {
  const t = useT()
  const { session } = useAuth()
  const { targetTenant, targetTenantId } = useTenant()

  const [page, setPage] = useState(1)
  const [data, setData] = useState<PageResponse<NotificationListItem> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [markAllLoading, setMarkAllLoading] = useState(false)

  const canSendTenant = useMemo(
    () => hasAnyPermission(session, ['notifications:send']),
    [session],
  )

  const isSuperuser = Boolean(session?.isSuperuser)

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

  const [bulkTitle, setBulkTitle] = useState('')
  const [bulkContent, setBulkContent] = useState('')
  const [bulkUserIds, setBulkUserIds] = useState('')
  const [bulkTeamIds, setBulkTeamIds] = useState('')
  const [bulkIncludeChildren, setBulkIncludeChildren] = useState(true)
  const [bulkResult, setBulkResult] = useState<string | null>(null)
  const [bulkSending, setBulkSending] = useState(false)

  const [broadcastTitle, setBroadcastTitle] = useState('')
  const [broadcastContent, setBroadcastContent] = useState('')
  const [broadcastResult, setBroadcastResult] = useState<string | null>(null)
  const [broadcastSending, setBroadcastSending] = useState(false)

  return (
    <div className="grid gap-4">
      <PageHeader
            title={t('system.notifications.title')}
            description={t('system.notifications.description')}
            actions={
              data ? (
                <Badge variant="outline">
                  {t('system.common.pageTotal')
                    .replace('{page}', String(data.currentPage))
                    .replace('{total}', String(data.total))}
                </Badge>
              ) : null
            }
      />
      <Card>
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
                setMarkAllLoading(true)
                const id = toast.loading(t('system.notifications.marking'))
                try {
                  await apiFetch('/api/v1/notifications/read-all', {
                    method: 'PUT',
                    session,
                  })
                  await load()
                  toast.success(t('system.notifications.markAllSuccess'), { id })
                } catch (err) {
                  const message = err instanceof ApiError ? err.message : t('system.common.operationFailed')
                  setError(message)
                  toast.error(message, { id })
                } finally {
                  setMarkAllLoading(false)
                }
              }}
              disabled={loading || markAllLoading}
            >
              {t('system.notifications.markAllRead')}
            </Button>
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
              <div className="p-3 text-sm text-muted-foreground">
                {loading ? t('common.loading') : t('system.common.noNotifications')}
              </div>
            )}
          </div>

          <SimplePagination
            total={data?.total ?? 0}
            currentPage={data?.currentPage ?? page}
            pageSize={data?.pageSize ?? 10}
            onChange={(p) => setPage(p)}
            disabled={loading}
          />
        </CardContent>
      </Card>

      {canSendTenant ? (
        <>
        <PageHeader
              title={t('system.notifications.bulkTitle')}
              description={
                <>
                  <code>/api/v1/notifications/bulk</code>{t('system.notifications.bulkDescription')}
                  {session?.isSuperuser && targetTenant ? (
                    <span className="ml-2 text-xs text-muted-foreground">
                      {t('system.common.targetTenant')
                        .replace('{name}', targetTenant.name)
                        .replace('{code}', targetTenant.code)}
                    </span>
                  ) : null}
                </>
              }
        />
        <Card>
          <CardContent className="grid gap-4">
            <CollapsibleFilters title={t('system.notifications.sendParams')}>
              <div className="grid gap-2 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="bulk-title">{t('system.common.title')}</Label>
                  <Input
                    id="bulk-title"
                    value={bulkTitle}
                    onChange={(e) => setBulkTitle(e.target.value)}
                    placeholder={t('system.common.enterTitle')}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="bulk-user-ids">{t('system.notifications.userIds')}</Label>
                  <Input
                    id="bulk-user-ids"
                    value={bulkUserIds}
                    onChange={(e) => setBulkUserIds(e.target.value)}
                    placeholder={t('system.common.exampleIds').replace('{ids}', '1,2,3')}
                  />
                </div>
                <div className="grid gap-2 md:col-span-2">
                  <Label htmlFor="bulk-content">{t('system.common.content')}</Label>
                  <Textarea
                    id="bulk-content"
                    value={bulkContent}
                    onChange={(e) => setBulkContent(e.target.value)}
                    placeholder={t('system.common.enterContent')}
                    rows={4}
                  />
                </div>
                <div className="grid gap-2 md:col-span-2">
                  <Label htmlFor="bulk-team-ids">{t('system.notifications.teamIds')}</Label>
                  <Input
                    id="bulk-team-ids"
                    value={bulkTeamIds}
                    onChange={(e) => setBulkTeamIds(e.target.value)}
                    placeholder={t('system.common.exampleIds').replace('{ids}', '10,11')}
                  />
                </div>
                <label className="flex items-center gap-2 text-sm md:col-span-2">
                  <Checkbox
                    checked={bulkIncludeChildren}
                    onCheckedChange={(v) => setBulkIncludeChildren(Boolean(v))}
                  />
                  {t('system.notifications.includeChildren')}
                </label>
              </div>
            </CollapsibleFilters>

            {bulkResult ? <div className="text-sm text-emerald-700">{bulkResult}</div> : null}
            <Button
              disabled={bulkSending}
              onClick={async () => {
                if (!session) return
                setBulkResult(null)
                setError(null)
                setBulkSending(true)
                const id = toast.loading(t('system.notifications.bulkSending'))
                try {
                  const userIds = parseIdList(bulkUserIds)
                  const teamIds = parseIdList(bulkTeamIds)
                  const res = await apiFetch<BulkSendResponse>('/api/v1/notifications/bulk', {
                    method: 'POST',
                    session,
                    tenantId: targetTenantId,
                    body: JSON.stringify({
                      userIds,
                      teamIds,
                      includeChildren: bulkIncludeChildren,
                      category: 'notification',
                      title: bulkTitle,
                      content: bulkContent,
                    }),
                  })
                  setBulkResult(t('system.common.sentCount').replace('{sent}', String(res.sent)).replace('{requested}', String(res.requested)))
                  toast.success(
                    t('system.notifications.bulkSent').replace('{sent}', String(res.sent)).replace('{requested}', String(res.requested)),
                    { id },
                  )
                } catch (err) {
                  const message = err instanceof ApiError ? err.message : t('system.common.sendFailed')
                  setError(message)
                  toast.error(message, { id })
                } finally {
                  setBulkSending(false)
                }
              }}
            >
              {bulkSending ? t('system.common.sending') : t('system.notifications.bulkSend')}
            </Button>
          </CardContent>
        </Card>
        </>
      ) : null}

      {isSuperuser ? (
        <>
        <PageHeader
              title={t('system.notifications.broadcastTitle')}
              description={
                <>
                  <code>/api/v1/notifications/broadcast</code>: {t('system.notifications.broadcastDescription')}
                </>
              }
        />
        <Card>
          <CardContent className="grid gap-4">
            <CollapsibleFilters title={t('system.notifications.sendParams')}>
              <div className="grid gap-2">
                <div className="grid gap-2">
                  <Label htmlFor="broadcast-title">{t('system.common.title')}</Label>
                  <Input
                    id="broadcast-title"
                    value={broadcastTitle}
                    onChange={(e) => setBroadcastTitle(e.target.value)}
                    placeholder={t('system.common.enterTitle')}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="broadcast-content">{t('system.common.content')}</Label>
                  <Textarea
                    id="broadcast-content"
                    value={broadcastContent}
                    onChange={(e) => setBroadcastContent(e.target.value)}
                    placeholder={t('system.common.enterContent')}
                    rows={4}
                  />
                </div>
              </div>
            </CollapsibleFilters>

            {broadcastResult ? <div className="text-sm text-emerald-700">{broadcastResult}</div> : null}
            <Button
              variant="secondary"
              disabled={broadcastSending}
              onClick={async () => {
                if (!session) return
                setBroadcastResult(null)
                setError(null)
                setBroadcastSending(true)
                const id = toast.loading(t('system.notifications.broadcastSending'))
                try {
                  const res = await apiFetch<BulkSendResponse>('/api/v1/notifications/broadcast', {
                    method: 'POST',
                    session,
                    body: JSON.stringify({
                      category: 'notification',
                      title: broadcastTitle,
                      content: broadcastContent,
                    }),
                  })
                  setBroadcastResult(t('system.common.sentCount').replace('{sent}', String(res.sent)).replace('{requested}', String(res.requested)))
                  toast.success(
                    t('system.notifications.broadcastSent').replace('{sent}', String(res.sent)).replace('{requested}', String(res.requested)),
                    { id },
                  )
                } catch (err) {
                  const message = err instanceof ApiError ? err.message : t('system.common.sendFailed')
                  setError(message)
                  toast.error(message, { id })
                } finally {
                  setBroadcastSending(false)
                }
              }}
            >
              {broadcastSending ? t('system.common.sending') : t('system.notifications.broadcastSend')}
            </Button>
          </CardContent>
        </Card>
        </>
      ) : null}
    </div>
  )
}
