'use client'

import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { Plus, RefreshCcw, RotateCcw, Search } from 'lucide-react'

import { SimplePagination } from '@/components/list/simple-pagination'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
  type SupportTicket,
  type SupportTicketDetail,
} from '@/lib/support-api'

const ALL = '__all__'
const PAGE_SIZE = 20

type TicketDraft = {
  subject: string
  description: string
  category: string
  priority: string
  relatedType: string
  relatedId: string
}

const EMPTY_DRAFT: TicketDraft = {
  subject: '',
  description: '',
  category: 'other',
  priority: 'normal',
  relatedType: '',
  relatedId: '',
}

/**
 * 从查询串预填提单表单。
 *
 * 别的模块（例如某个业务工作台的「就这一条记录提工单」）用链接把上下文带过来：
 * `/support/tickets?subject=…&category=…&relatedType=…&relatedId=…`。
 * 本模块**不认识**这些 relatedType 的含义——照原样透传给后端就行，
 * 这正是包的泛化关联能被任何业务分支复用的原因。
 */
function draftFromSearchParams(params: URLSearchParams): TicketDraft | null {
  const draft: TicketDraft = {
    ...EMPTY_DRAFT,
    subject: (params.get('subject') || '').slice(0, 200),
    description: (params.get('description') || '').slice(0, 5000),
    category: (params.get('category') || EMPTY_DRAFT.category).trim(),
    priority: (params.get('priority') || EMPTY_DRAFT.priority).trim(),
    relatedType: (params.get('relatedType') || '').trim().slice(0, 40),
    relatedId: (params.get('relatedId') || '').trim().slice(0, 80),
  }
  const carriesContext =
    draft.subject !== '' ||
    draft.description !== '' ||
    draft.relatedType !== '' ||
    draft.relatedId !== '' ||
    params.get('category') !== null
  return carriesContext ? draft : null
}

function formatMoment(value: string | null): string {
  if (!value) return '-'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '-' : parsed.toLocaleString()
}

/**
 * 我的工单：只看得到本人提交的工单（后端按 requester_user_id 过滤，
 * 同租户他人与跨租户一律 404，不是 403）。
 *
 * 列表是**分页**的：接口返回 total，页面就必须给出翻页，否则第 21 条起会静默消失。
 * 加载 / 空 / 出错三态分开渲染：出错时给可重试的提示，而不是让表格看起来"就是空的"。
 */
export default function SupportTicketsPage() {
  const t = useT()
  const { session } = useAuth()
  const { targetTenantId } = useTenant()

  const [options, setOptions] = useState<SupportOptions | null>(null)
  const [tickets, setTickets] = useState<SupportTicket[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string>(ALL)
  const [categoryFilter, setCategoryFilter] = useState<string>(ALL)
  const [keywordDraft, setKeywordDraft] = useState('')
  const [keyword, setKeyword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const searchParams = useSearchParams()
  const prefill = draftFromSearchParams(new URLSearchParams(searchParams.toString()))
  const [createOpen, setCreateOpen] = useState(prefill !== null)
  const [form, setForm] = useState<TicketDraft>(prefill ?? EMPTY_DRAFT)

  const [detail, setDetail] = useState<SupportTicketDetail | null>(null)
  const [replyBody, setReplyBody] = useState('')

  const filtered = statusFilter !== ALL || categoryFilter !== ALL || keyword !== ''

  const load = useCallback(async () => {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const result = await supportApi.listMine(
        {
          page,
          pageSize: PAGE_SIZE,
          status: statusFilter === ALL ? undefined : statusFilter,
          category: categoryFilter === ALL ? undefined : categoryFilter,
          keyword: keyword || undefined,
        },
        { session, tenantId: targetTenantId },
      )
      setTickets(result.list)
      setTotal(result.total)
    } catch (reason) {
      setTickets([])
      setTotal(0)
      setError(reason instanceof ApiError ? reason.message : t('support.error.load'))
    } finally {
      setLoading(false)
    }
  }, [session, targetTenantId, page, statusFilter, categoryFilter, keyword, t])

  const loadOptions = useCallback(async () => {
    if (!session) return
    try {
      setOptions(await supportApi.options({ session, tenantId: targetTenantId }))
    } catch {
      // 选项拉不到不阻塞列表：下拉退回后端默认值即可
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
  const canCreate = hasAnyPermission(session, ['support:create'])
  const categories = options?.categories ?? ['other']
  const priorities = options?.priorities ?? ['normal']
  const statuses = options?.statuses ?? []
  // 链接可能带来包不认识的取值（老书签、别的分支的词表）。下拉只显示白名单里的值，
  // 越界的一律落到默认项——留着会渲染成一个空下拉，提交也必然 422。
  const draftCategory = categories.includes(form.category) ? form.category : 'other'
  const draftPriority = priorities.includes(form.priority) ? form.priority : 'normal'

  function applyFilter(next: () => void) {
    // 换筛选条件必须回到第 1 页：留在第 3 页会得到一个"什么都没有"的空列表。
    setPage(1)
    next()
  }

  function resetFilters() {
    setPage(1)
    setStatusFilter(ALL)
    setCategoryFilter(ALL)
    setKeywordDraft('')
    setKeyword('')
  }

  async function submitCreate() {
    setSubmitting(true)
    setError(null)
    try {
      await supportApi.create(
        {
          subject: form.subject.trim(),
          description: form.description.trim(),
          category: form.category,
          priority: form.priority,
          relatedType: form.relatedType || undefined,
          relatedId: form.relatedId || undefined,
        },
        context,
      )
      setCreateOpen(false)
      setForm(EMPTY_DRAFT)
      setPage(1)
      await load()
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : t('support.error.create'))
    } finally {
      setSubmitting(false)
    }
  }

  async function openDetail(ticket: SupportTicket) {
    setError(null)
    try {
      setDetail(await supportApi.getMine(ticket.id, context))
      setReplyBody('')
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : t('support.error.load'))
    }
  }

  async function submitReply() {
    if (!detail) return
    setSubmitting(true)
    setError(null)
    try {
      const next = await supportApi.reply(detail.id, replyBody.trim(), context)
      setDetail(next)
      setReplyBody('')
      await load()
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : t('support.error.reply'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{t('support.tickets.title')}</CardTitle>
          <CardDescription>{t('support.tickets.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
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
              <Input
                className="w-52"
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
            {canCreate ? (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                {t('support.action.create')}
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
                  <TableHead>{t('support.column.category')}</TableHead>
                  <TableHead>{t('support.column.status')}</TableHead>
                  <TableHead>{t('support.column.priority')}</TableHead>
                  <TableHead>{t('support.column.lastMessageAt')}</TableHead>
                  <TableHead className="text-right">{t('support.column.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tickets.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground">
                      {loading ? t('support.loading') : error ? '-' : t('support.empty')}
                    </TableCell>
                  </TableRow>
                ) : (
                  tickets.map((ticket) => (
                    <TableRow key={ticket.id}>
                      <TableCell className="font-mono">{ticket.ticketNo || '-'}</TableCell>
                      <TableCell>{ticket.subject}</TableCell>
                      <TableCell>{t(`support.category.${ticket.category}`)}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">{t(`support.status.${ticket.status}`)}</Badge>
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

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('support.action.create')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid gap-2">
              <Label>{t('support.field.subject')}</Label>
              <Input
                value={form.subject}
                onChange={(e) => setForm((s) => ({ ...s, subject: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label>{t('support.field.description')}</Label>
              <Textarea
                rows={5}
                value={form.description}
                onChange={(e) => setForm((s) => ({ ...s, description: e.target.value }))}
              />
            </div>
            <div className="grid gap-2 md:grid-cols-2 md:gap-3">
              <div className="grid gap-2">
                <Label>{t('support.field.category')}</Label>
                <Select
                  value={draftCategory}
                  onValueChange={(value) => setForm((s) => ({ ...s, category: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((value) => (
                      <SelectItem key={value} value={value}>
                        {t(`support.category.${value}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>{t('support.field.priority')}</Label>
                <Select
                  value={draftPriority}
                  onValueChange={(value) => setForm((s) => ({ ...s, priority: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {priorities.map((value) => (
                      <SelectItem key={value} value={value}>
                        {t(`support.priority.${value}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={submitting}>
              {t('support.action.cancel')}
            </Button>
            <Button
              onClick={() => void submitCreate()}
              disabled={submitting || form.subject.trim().length < 2 || form.description.trim().length < 2}
            >
              {t('support.action.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={detail !== null} onOpenChange={(open) => !open && setDetail(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{detail?.subject ?? t('support.detail.title')}</DialogTitle>
            <DialogDescription>
              {detail?.ticketNo ?? ''} · {detail ? t(`support.status.${detail.status}`) : ''}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <div className="text-sm font-medium">{t('support.detail.conversation')}</div>
            <div className="max-h-80 space-y-3 overflow-y-auto pr-1">
              {(detail?.messages ?? []).map((message) => (
                <div key={message.id} className="rounded-md border p-3">
                  <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{t(`support.role.${message.authorRole}`)}</span>
                    <span>{formatMoment(message.createdAt)}</span>
                  </div>
                  <div className="whitespace-pre-wrap text-sm">{message.body}</div>
                </div>
              ))}
            </div>
          </div>
          {canCreate && detail && detail.status !== 'closed' ? (
            <div className="grid gap-2">
              <Label>{t('support.field.reply')}</Label>
              <Textarea
                rows={3}
                value={replyBody}
                onChange={(e) => setReplyBody(e.target.value)}
              />
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetail(null)} disabled={submitting}>
              {t('support.action.cancel')}
            </Button>
            {canCreate && detail && detail.status !== 'closed' ? (
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
