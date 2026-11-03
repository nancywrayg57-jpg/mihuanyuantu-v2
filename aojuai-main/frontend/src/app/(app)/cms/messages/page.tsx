'use client'

import { Mail } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { PageHeader } from '@/components/page/page-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useAuth } from '@/hooks/useAuth'
import { hasAnyPermission } from '@/lib/auth'
import { useLocale, useT } from '@/lib/i18n'
import { listSubmissions, updateSubmission, type SubmissionItem } from '@/lib/cms-api'

export default function CmsMessagesPage() {
  const t = useT()
  const { locale } = useLocale()
  const statusLabel: Record<string, string> = {
    new: t('cms.messages.statusNew'),
    reviewed: t('cms.messages.statusReviewed'),
    spam: t('cms.messages.statusSpam'),
    archived: t('cms.messages.statusArchived'),
  }
  const { session } = useAuth()
  const [items, setItems] = useState<SubmissionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const [filter, setFilter] = useState<string>('')
  const canUpdate = hasAnyPermission(session, ['cms:contact:update'])

  const reload = useCallback(async () => {
    if (!session) return
    setLoading(true)
    try {
      const res = await listSubmissions(session, filter || undefined)
      setItems(res.list || [])
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.loadFailed'))
    } finally {
      setLoading(false)
    }
  }, [session, filter, t])

  useEffect(() => {
    void reload()
  }, [reload])

  async function setStatus(id: number, status: string) {
    try {
      await updateSubmission(session, id, status)
      await reload()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.actionFailed'))
    }
  }

  return (
    <div className="grid gap-4">
      <PageHeader
        title={t('cms.messages.title')}
        description={t('cms.messages.description')}
        icon={<Mail className="h-4 w-4" />}
        actions={
          <select
            className="h-9 rounded-md border border-border/60 bg-background px-2 text-sm"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="">{t('cms.messages.allStatus')}</option>
            <option value="new">{t('cms.messages.statusNew')}</option>
            <option value="reviewed">{t('cms.messages.statusReviewed')}</option>
            <option value="archived">{t('cms.messages.statusArchived')}</option>
            <option value="spam">{t('cms.messages.statusSpam')}</option>
          </select>
        }
      />
      {msg ? <div className="rounded-lg border border-border/60 bg-muted/40 px-3 py-2 text-sm">{msg}</div> : null}

      {loading ? (
        <div className="flex justify-center py-16"><div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div>
      ) : items.length === 0 ? (
        <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">{t('cms.messages.empty')}</CardContent></Card>
      ) : (
        <div className="grid gap-3">
          {items.map((it) => (
            <Card key={it.id}>
              <CardContent className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{it.name}</span>
                      <Badge variant={it.status === 'new' ? 'default' : 'secondary'} className="text-[10px]">
                        {statusLabel[it.status] || it.status}
                      </Badge>
                    </div>
                    <div className="mt-0.5 text-xs text-muted-foreground">
                      {it.email}
                      {it.company ? ` · ${it.company}` : ''}
                      {it.createdAt ? ` · ${new Date(it.createdAt).toLocaleString(locale)}` : ''}
                    </div>
                  </div>
                  {canUpdate ? (
                    <div className="flex flex-wrap gap-1.5">
                      <Button size="sm" variant="outline" onClick={() => setStatus(it.id, 'reviewed')}>{t('cms.messages.markReviewed')}</Button>
                      <Button size="sm" variant="ghost" onClick={() => setStatus(it.id, 'archived')}>{t('cms.messages.archive')}</Button>
                      <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setStatus(it.id, 'spam')}>{t('cms.messages.statusSpam')}</Button>
                    </div>
                  ) : null}
                </div>
                <p className="mt-3 whitespace-pre-wrap rounded-lg bg-muted/40 p-3 text-sm leading-6">{it.message}</p>
                {it.sourcePage ? <div className="mt-2 text-xs text-muted-foreground">{t('cms.messages.source').replace('{page}', it.sourcePage)}</div> : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
