'use client'

import { useCallback, useEffect, useState } from 'react'
import { RefreshCcw, RotateCcw, Search } from 'lucide-react'

import { SimplePagination } from '@/components/list/simple-pagination'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'
import { ApiError } from '@/lib/api'
import { hasAnyPermission } from '@/lib/auth'
import { useT } from '@/lib/i18n'
import {
  supportApi,
  type SupportOptions,
  type SupportSummary,
  type SupportTicket,
  type SupportTicketDetail,
  type SupportUserBrief,
} from '@/lib/support-api'

const ALL = '__all__'
const KEEP_STATUS = '__keep__'
const PAGE_SIZE = 20

function formatMoment(value: string | null): string {
  if (!value) return '-'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '-' : parsed.toLocaleString()
}

function displayName(brief: SupportUserBrief | null, fallback: string): string {
  if (!brief) return fallback
  return brief.nickname || brief.username || brief.email || String(brief.id)
}

/**
 * 工单管理（客服台）。所有接口都要 `support:manage`；页面按钮同样按权限渲染，
 * 权限不足直接不渲染，而不是点了再报 403。
 *
 * 列表是**分页**的：接口返回 total，页面就必须给出翻页，否则第 21 条起会静默消失。
 * 加载 / 空 / 出错三态分开渲染：出错时给可重试的提示，而不是让表格看起来"就是空的"。
 */
export default function SupportAdminTicketsPage() {
  const t = useT()
  const { session } = useAuth()
  const { targetTenantId } = useTenant()

  const [options, setOptions] = useState<SupportOptions | null>(null)
  const [summary, setSummary] = useState<SupportSummary | null>(null)
  const [tickets, setTickets] = useState<SupportTicket[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const [statusFilter, setStatusFilter] = useState(ALL)
  const [categoryFilter, setCategoryFilter] = useState(ALL)
  const [priorityFilter, setPriorityFilter] = useState(ALL)
  const [unassignedOnly, setUnassignedOnly] = useState(false)
  const [keywordDraft, setKeywordDraft] = useState('')
  const [keyword, setKeyword] = useState('')

  const [detail, setDetail] = useState<SupportTicketDetail | null>(null)
  const [replyBody, setReplyBody] = useState('')
  const [replyInternal, setReplyInternal] = useState(false)
  const [replyStatus, setReplyStatus] = useState(KEEP_STATUS)

  const canManage = Boolean(session && hasAnyPermission(session, ['support:manage']))

  const load = useCallback(async () => {
    if (!session || !canManage) return
    setLoading(true)
    setError(null)
    try {
      const [result, counters] = await Promise.all([
        supportApi.adminList(
          {
            page,
            pageSize: PAGE_SIZE,
            status: statusFilter === ALL ? undefined : statusFilter,
            category: categoryFilter === ALL ? undefined : categoryFilter,
            priority: priorityFilter === ALL ? undefined : priorityFilter,
            keyword: keyword || undefined,
            unassigned: unassignedOnly || undefined,
          },
          { session, tenantId: targetTenantId },
        ),
        supportApi.adminSummary({ session, tenantId: targetTenantId }),
      ])
      setTickets(result.list)
      setTotal(result.total)
      setSummary(counters)
    } catch (reason) {
      setTickets([])
      setTotal(0)
      setError(reason instanceof ApiError ? reason.message : t('support.error.load'))
    } finally {
      setLoading(false)
    }
  }, [
    session,
    canManage,
    targetTenantId,
    page,
    statusFilter,
    categoryFilter,
    priorityFilter,
    keyword,
    unassignedOnly,
    t,
  ])

  const loadOptions = useCallback(async () => {
    // 后端 /options 需要 support:read；没有权限就不发这个请求，不靠 catch 403 兜底。
    if (!session || !hasAnyPermission(session, ['support:read', 'support:manage'])) return
    try {
      setOptions(await supportApi.options({ session, tenantId: targetTenantId }))
    } catch {
      // 选项拉不到不阻塞列表
    }
  }, [session, targetTenantId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    void loadOptions()
  }, [loadOptions])

  if (!session) return null

  const context = { session, tenantId: targetTenantId }
  const statuses = options?.statuses ?? []
  const categories = options?.categories ?? []
  const priorities = options?.priorities ?? []
  const filtered =
    statusFilter !== ALL ||
    categoryFilter !== ALL ||
    priorityFilter !== ALL ||
    unassignedOnly ||
    keyword !== ''

  function applyFilter(next: () => void) {
    // 换筛选条件必须回到第 1 页：留在第 3 页会得到一个"什么都没有"的空列表。
    setPage(1)
    next()
  }

  function resetFilters() {
    setPage(1)
    setStatusFilter(ALL)
    setCategoryFilter(ALL)
    setPriorityFilter(ALL)
    setUnassignedOnly(false)
    setKeywordDraft('')
    setKeyword('')
  }

  async function openDetail(ticket: SupportTicket) {
    setError(null)
    try {
      setDetail(await supportApi.adminGet(ticket.id, context))
      setReplyBody('')
      setReplyInternal(false)
      setReplyStatus(KEEP_STATUS)
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : t('support.error.load'))
    }
  }

  async function submitReply() {
    if (!detail) return
    setSubmitting(true)
    setError(null)
    try {
      const next = await supportApi.adminReply(
        detail.id,
        {
          body: replyBody.trim(),
          isInternal: replyInternal,
          status: replyStatus === KEEP_STATUS ? undefined : replyStatus,
        },
        context,
      )
      setDetail(next)
      setReplyBody('')
      setReplyStatus(KEEP_STATUS)
      await load()
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : t('support.error.reply'))
    } finally {
      setSubmitting(false)
    }
  }

  async function changeStatus(ticket: SupportTicket, status: string) {
    setError(null)
    try {
      await supportApi.adminUpdate(ticket.id, { status }, context)
      await load()
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : t('support.error.update'))
    }
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{t('support.admin.title')}</CardTitle>
          <CardDescription>{t('support.admin.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {summary ? (
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">
                {t('support.summary.total')}: {summary.total}
              </Badge>
              {statuses.map((value) => (
                <Badge key={value} variant="secondary">
                  {t(`support.status.${value}`)}: {summary[value as keyof SupportSummary] ?? 0}
                </Badge>
              ))}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={() => void load()} disabled={loading}>
              <RefreshCcw className={loading ? 'mr-2 h-4 w-4 animate-spin' : 'mr-2 h-4 w-4'} />
              {t('support.action.refresh')}
            </Button>
            <Select
              value={statusFilter}
              onValueChange={(value) => applyFilter(() => setStatusFilter(value))}
            >
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>{t('support.filter.all')}</SelectItem>
                {statuses.map((value) => (
                  <SelectItem key={value} value={value}>
                    {t(`support.status.${value}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={categoryFilter}
              onValueChange={(value) => applyFilter(() => setCategoryFilter(value))}
            >
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>{t('support.filter.all')}</SelectItem>
                {categories.map((value) => (
                  <SelectItem key={value} value={value}>
                    {t(`support.category.${value}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={priorityFilter}
              onValueChange={(value) => applyFilter(() => setPriorityFilter(value))}
            >
              <SelectTrigger className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>{t('support.filter.all')}</SelectItem>
                {priorities.map((value) => (
                  <SelectItem key={value} value={value}>
                    {t(`support.priority.${value}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={unassignedOnly}
                onCheckedChange={(value) => applyFilter(() => setUnassignedOnly(Boolean(value)))}
              />
              {t('support.filter.unassignedOnly')}
            </label>
            <Input
              className="w-56"
              placeholder={t('support.field.keyword')}
              value={keywordDraft}
              onChange={(e) => setKeywordDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') applyFilter(() => setKeyword(keywordDraft.trim()))
              }}
            />
            <Button
              variant="outline"
              onClick={() => applyFilter(() => setKeyword(keywordDraft.trim()))}
            >
              <Search className="mr-2 h-4 w-4" />
              {t('support.action.search')}
            </Button>
            {filtered ? (
              <Button variant="ghost" onClick={resetFilters}>
                <RotateCcw className="mr-2 h-4 w-4" />
                {t('support.action.clearFilters')}
              </Button>
            ) : null}
          </div>

          {error ? (
            <div className="flex flex-wrap items-center gap-3 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              <span className="flex-1">{error}</span>
              <Button size="sm" variant="outline" disabled={loading} onClick={() => void load()}>
                {t('support.action.refresh')}
              </Button>
            </div>
          ) : null}

          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('support.column.ticketNo')}</TableHead>
                  <TableHead>{t('support.column.subject')}</TableHead>
                  <TableHead>{t('support.column.requester')}</TableHead>
                  <TableHead>{t('support.column.assignee')}</TableHead>
                  <TableHead>{t('support.column.status')}</TableHead>
                  <TableHead>{t('support.column.priority')}</TableHead>
                  <TableHead>{t('support.column.lastMessageAt')}</TableHead>
                  <TableHead className="text-right">{t('support.column.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tickets.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center text-muted-foreground">
                      {loading ? t('support.loading') : error ? '-' : t('support.empty')}
                    </TableCell>
                  </TableRow>
                ) : (
                  tickets.map((ticket) => (
                    <TableRow key={ticket.id}>
                      <TableCell className="font-mono">{ticket.ticketNo || '-'}</TableCell>
                      <TableCell>
                        {ticket.subject}
                        {ticket.slaOverdue ? (
                          <Badge className="ml-2" variant="destructive">
                            {t('support.badge.overdue')}
                          </Badge>
                        ) : null}
                      </TableCell>
                      <TableCell>
                        {displayName(ticket.requester, t('support.detail.anonymous'))}
                      </TableCell>
                      <TableCell>{displayName(ticket.assignee, '-')}</TableCell>
                      <TableCell>
                        {canManage ? (
                          <Select
                            value={ticket.status}
                            onValueChange={(value) => void changeStatus(ticket, value)}
                          >
                            <SelectTrigger className="w-36">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {statuses.map((value) => (
                                <SelectItem key={value} value={value}>
                                  {t(`support.status.${value}`)}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <Badge variant="secondary">{t(`support.status.${ticket.status}`)}</Badge>
                        )}
                      </TableCell>
                      <TableCell>{t(`support.priority.${ticket.priority}`)}</TableCell>
                      <TableCell>{formatMoment(ticket.lastMessageAt)}</TableCell>
                      <TableCell className="text-right">
                        <Button size="sm" variant="outline" onClick={() => void openDetail(ticket)}>
                          {t('support.action.view')}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <SimplePagination
            total={total}
            currentPage={page}
            pageSize={PAGE_SIZE}
            disabled={loading}
            onChange={setPage}
          />
        </CardContent>
      </Card>

      <Dialog open={detail !== null} onOpenChange={(open) => !open && setDetail(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{detail?.subject ?? t('support.detail.title')}</DialogTitle>
            <DialogDescription>
              {detail?.ticketNo ?? ''} ·{' '}
              {detail ? displayName(detail.requester, t('support.detail.anonymous')) : ''}
            </DialogDescription>
          </DialogHeader>
          <div className="text-sm font-medium">{t('support.detail.conversation')}</div>
          <div className="max-h-72 space-y-3 overflow-y-auto pr-1">
            {(detail?.messages ?? []).map((message) => (
              <div key={message.id} className="rounded-md border p-3">
                <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
                  <span>{t(`support.role.${message.authorRole}`)}</span>
                  <span>{formatMoment(message.createdAt)}</span>
                  {message.isInternal ? (
                    <Badge variant="outline">{t('support.badge.internal')}</Badge>
                  ) : null}
                </div>
                <div className="whitespace-pre-wrap text-sm">{message.body}</div>
              </div>
            ))}
          </div>
          {canManage ? (
            <div className="space-y-3">
              <div className="grid gap-2">
                <Label>{t('support.field.reply')}</Label>
                <Textarea rows={3} value={replyBody} onChange={(e) => setReplyBody(e.target.value)} />
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={replyInternal}
                    onCheckedChange={(value) => setReplyInternal(Boolean(value))}
                  />
                  {t('support.detail.replyInternal')}
                </label>
                <div className="flex items-center gap-2 text-sm">
                  <span>{t('support.detail.changeStatus')}</span>
                  <Select value={replyStatus} onValueChange={setReplyStatus}>
                    <SelectTrigger className="w-40">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={KEEP_STATUS}>{t('support.detail.keepStatus')}</SelectItem>
                      {statuses.map((value) => (
                        <SelectItem key={value} value={value}>
                          {t(`support.status.${value}`)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetail(null)} disabled={submitting}>
              {t('support.action.cancel')}
            </Button>
            {canManage ? (
              <Button onClick={() => void submitReply()} disabled={submitting || !replyBody.trim()}>
                {t('support.action.send')}
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
