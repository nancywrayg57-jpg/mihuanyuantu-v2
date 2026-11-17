'use client'

import { useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { RpPageHeader } from '@/components/realphotos/rp-page-header'
import { toastTask } from '@/components/realphotos/surface'
import { ApiError, apiFetch } from '@/lib/api'
import {
  ticketStatusLabel,
  ticketTypeLabel,
} from '@/lib/realphotos-labels'
import { formatDateTimeShort } from '@/lib/realphotos-time'

type Ticket = {
  id: number
  tenantId: number
  tenantName?: string | null
  ownerAccountId: number
  username?: string | null
  ticketType: string
  status: string
  reason: string
  createdAt?: string | null
  resolvedAt?: string | null
  resolutionOutcome?: string
  resolutionNote?: string
}

type HeldTenantItem = {
  tenantId: number
  tenantName?: string | null
  heldTotal: number
  taskCount?: number
  accountSummary?: string | null
  ownerAccountIds?: number[]
}

type DeskTab = 'appeals' | 'held'

function tenantLabel(item: { tenantId: number; tenantName?: string | null }) {
  const name = (item.tenantName || '').trim()
  return name ? `${name}（#${item.tenantId}）` : `#${item.tenantId}`
}

function accountLabel(item: { ownerAccountId: number; username?: string | null }) {
  const name = (item.username || '').trim()
  return name ? `${name}（#${item.ownerAccountId}）` : `#${item.ownerAccountId}`
}

export default function RealphotosTechDeskPage() {
  const [items, setItems] = useState<Ticket[]>([])
  const [myItems, setMyItems] = useState<Ticket[]>([])
  const [heldItems, setHeldItems] = useState<HeldTenantItem[]>([])
  const [heldPage, setHeldPage] = useState(1)
  const [heldTotal, setHeldTotal] = useState(0)
  const [heldPageSize, setHeldPageSize] = useState(20)
  const [ticketPage, setTicketPage] = useState(1)
  const [ticketTotal, setTicketTotal] = useState(0)
  const [ticketPageSize, setTicketPageSize] = useState(20)
  const [reason, setReason] = useState('')
  const [appealReason, setAppealReason] = useState('')
  const [resolveNote, setResolveNote] = useState('')
  const [resolveOutcome, setResolveOutcome] = useState('accepted')
  const [heldDrafts, setHeldDrafts] = useState<Record<number, { amount: string; reason: string }>>({})
  const [message, setMessage] = useState('')
  const [ticketType, setTicketType] = useState('all')
  const [search, setSearch] = useState('')
  const [detail, setDetail] = useState<Ticket | null>(null)
  const [canUnfreeze, setCanUnfreeze] = useState(false)
  const [canAppeal, setCanAppeal] = useState(false)
  const [deskTab, setDeskTab] = useState<DeskTab>('appeals')

  async function loadTickets(page = ticketPage) {
    const data = await apiFetch<{
      items: Ticket[]
      page?: number
      pageSize?: number
      total?: number
    }>(`/api/v1/realphotos/support-tickets?page=${page}`)
    setItems(Array.isArray(data?.items) ? data.items : [])
    setTicketPage(Number(data?.page) || page)
    setTicketPageSize(Number(data?.pageSize) || 20)
    setTicketTotal(Number(data?.total) || (Array.isArray(data?.items) ? data.items.length : 0))
    setCanUnfreeze(true)
  }

  async function loadHeld(page = heldPage) {
    const held = await apiFetch<{
      items: HeldTenantItem[]
      page?: number
      pageSize?: number
      total?: number
    }>(`/api/v1/realphotos/held-credits?page=${page}`)
    setHeldItems(Array.isArray(held?.items) ? held.items : [])
    setHeldPage(Number(held?.page) || page)
    setHeldPageSize(Number(held?.pageSize) || 20)
    setHeldTotal(Number(held?.total) || (Array.isArray(held?.items) ? held.items.length : 0))
  }

  async function loadDesk() {
    await loadTickets(ticketPage)
    await loadHeld(heldPage)
  }

  async function loadMine(page = ticketPage) {
    const data = await apiFetch<{
      items: Ticket[]
      page?: number
      pageSize?: number
      total?: number
    }>(`/api/v1/realphotos/my-support-tickets?page=${page}`)
    setMyItems(Array.isArray(data?.items) ? data.items : [])
    setTicketPage(Number(data?.page) || page)
    setTicketPageSize(Number(data?.pageSize) || 20)
    setTicketTotal(Number(data?.total) || (Array.isArray(data?.items) ? data.items.length : 0))
    setCanAppeal(true)
  }

  useEffect(() => {
    void loadDesk().catch(() => {
      setCanUnfreeze(false)
      void loadMine(1).catch((error: unknown) =>
        setMessage(error instanceof ApiError ? error.message : '工单读取失败'),
      )
    })
    // initial load only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!canUnfreeze || deskTab !== 'held') return
    void loadHeld(heldPage).catch((error: unknown) =>
      setMessage(error instanceof ApiError ? error.message : '冻结列表读取失败'),
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [heldPage, deskTab, canUnfreeze])

  useEffect(() => {
    if (deskTab !== 'appeals' && canUnfreeze) return
    if (canUnfreeze) {
      void loadTickets(ticketPage).catch((error: unknown) =>
        setMessage(error instanceof ApiError ? error.message : '工单读取失败'),
      )
      return
    }
    if (canAppeal) {
      void loadMine(ticketPage).catch((error: unknown) =>
        setMessage(error instanceof ApiError ? error.message : '工单读取失败'),
      )
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticketPage, deskTab, canUnfreeze, canAppeal])

  const source = canUnfreeze ? items : myItems
  const visible = useMemo(
    () =>
      source.filter(
        (item) =>
          (ticketType === 'all' || item.ticketType === ticketType) &&
          matchSearchText(
            search,
            item.id,
            item.tenantId,
            item.tenantName,
            item.ownerAccountId,
            item.username,
            item.ticketType,
            ticketTypeLabel(item.ticketType),
            item.status,
            ticketStatusLabel(item.status),
            item.reason,
            item.resolutionNote,
          ),
      ),
    [source, ticketType, search],
  )
  const openCount = source.filter((item) => item.status === 'open').length
  const heldPageCount = Math.max(1, Math.ceil(heldTotal / Math.max(heldPageSize, 1)))
  const ticketPageCount = Math.max(1, Math.ceil(ticketTotal / Math.max(ticketPageSize, 1)))

  function openHandle(item: Ticket) {
    setDetail(item)
    setResolveNote('')
    setResolveOutcome('accepted')
    setReason('')
  }

  function closeHandle() {
    setDetail(null)
    setResolveNote('')
    setReason('')
  }

  function heldDraft(tenant: number) {
    return heldDrafts[tenant] || { amount: '', reason: '' }
  }

  function patchHeldDraft(tenant: number, patch: Partial<{ amount: string; reason: string }>) {
    setHeldDrafts((prev) => ({
      ...prev,
      [tenant]: { ...heldDraft(tenant), ...patch },
    }))
  }

  async function unfreezeFromDetail() {
    if (!detail) return
    try {
      const payload = await apiFetch<{ closedFreezeTickets?: number }>(
        '/api/v1/realphotos/account-freezes/release',
        {
          method: 'POST',
          body: JSON.stringify({
            userId: Number(detail.ownerAccountId),
            tenantId: Number(detail.tenantId),
            reason,
          }),
        },
      )
      const text = `已解除预审冻结；关闭冻结工单 ${payload.closedFreezeTickets ?? 0} 张`
      setMessage(text)
      toastTask(text, true)
      closeHandle()
      await loadDesk()
    } catch (error: unknown) {
      const text = error instanceof ApiError ? error.message : '解冻失败'
      setMessage(text)
      toastTask(text, false)
    }
  }

  async function createAppeal() {
    try {
      await apiFetch('/api/v1/realphotos/support-tickets', {
        method: 'POST',
        body: JSON.stringify({ ticketType: 'image_appeal', reason: appealReason }),
      })
      setMessage('已创建图片申诉工单')
      setAppealReason('')
      if (canUnfreeze) await loadDesk()
      else await loadMine()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '申诉创建失败')
    }
  }

  async function resolveDetail() {
    if (!detail) return
    try {
      const updated = await apiFetch<Ticket>(`/api/v1/realphotos/support-tickets/${detail.id}/resolve`, {
        method: 'POST',
        body: JSON.stringify({ outcome: resolveOutcome, note: resolveNote }),
      })
      const text = `工单 ${updated.id} 已办结（${updated.resolutionOutcome}）；办结不等于解锁图片`
      setMessage(text)
      toastTask(text, true)
      closeHandle()
      await loadDesk()
    } catch (error: unknown) {
      const text = error instanceof ApiError ? error.message : '办结失败'
      setMessage(text)
      toastTask(text, false)
    }
  }

  async function releaseHeldByAmount(row: HeldTenantItem) {
    const draft = heldDraft(row.tenantId)
    const amount = Number(draft.amount)
    try {
      if (!Number.isInteger(amount) || amount <= 0) {
        throw new ApiError('本次释放积分须为正整数', { code: 'INPUT_INVALID', status: 400 })
      }
      if (amount > Number(row.heldTotal)) {
        throw new ApiError('本次释放积分不能超过该租户冻结合计', { code: 'INPUT_INVALID', status: 400 })
      }
      if (!draft.reason.trim()) {
        throw new ApiError('释放必须填写原因', { code: 'INPUT_INVALID', status: 400 })
      }
      const payload = await apiFetch<{ releasedAmount?: number; heldTotalAfter?: number }>(
        '/api/v1/realphotos/held-credits/release-by-amount',
        {
          method: 'POST',
          body: JSON.stringify({
            tenantId: row.tenantId,
            amount,
            reason: draft.reason.trim(),
          }),
        },
      )
      const text = `已按量释放 ${payload.releasedAmount ?? amount} 积分；剩余 held=${payload.heldTotalAfter ?? '—'}`
      setMessage(text)
      toastTask(text, true)
      patchHeldDraft(row.tenantId, { amount: '', reason: '' })
      await loadHeld(heldPage)
    } catch (error: unknown) {
      const text = error instanceof ApiError ? error.message : '释放失败'
      setMessage(text)
      toastTask(text, false)
    }
  }

  return (
    <main className="space-y-4 p-6">
      <RpPageHeader title="工单管理" />
      <p className="text-sm">
        {message}
        {canUnfreeze ? ` · 待处理 open=${openCount}` : ''}
      </p>

      {canUnfreeze ? (
        <div className="flex gap-2 text-sm">
          <button
            className={`rp-btn ${deskTab === 'appeals' ? 'bg-muted' : ''}`}
            type="button"
            onClick={() => setDeskTab('appeals')}
          >
            账号申诉
          </button>
          <button
            className={`rp-btn ${deskTab === 'held' ? 'bg-muted' : ''}`}
            type="button"
            onClick={() => {
              setDeskTab('held')
              setHeldPage(1)
            }}
          >
            积分冻结
          </button>
        </div>
      ) : null}

      {(!canUnfreeze || deskTab === 'appeals') ? (
        <section className="rp-card p-4 shadow-sm space-y-3">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <label>
              类型筛选
              <select className="rp-input ml-2" value={ticketType} onChange={(event) => setTicketType(event.target.value)}>
                <option value="all">全部</option>
                <option value="account_freeze">{ticketTypeLabel('account_freeze')}</option>
                <option value="image_appeal">{ticketTypeLabel('image_appeal')}</option>
                <option value="order">{ticketTypeLabel('order')}</option>
              </select>
            </label>
            <ListSearch value={search} placeholder="编号 / 租户 / 账号 / 原因" onChange={setSearch} />
          </div>
          <table className="rp-table">
            <thead>
              <tr>
                <th className="text-left">编号</th>
                <th className="text-left">租户</th>
                <th className="text-left">账号</th>
                <th className="text-left">类型</th>
                <th className="text-left">状态</th>
                <th className="text-left">原因</th>
                <th className="text-left">操作</th>
              </tr>
            </thead>
            <tbody>
              {visible.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    尚无工单
                  </td>
                </tr>
              ) : (
                visible.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{tenantLabel(item)}</td>
                    <td>{accountLabel(item)}</td>
                    <td>{ticketTypeLabel(item.ticketType)}</td>
                    <td>{ticketStatusLabel(item.status)}</td>
                    <td>{item.reason}</td>
                    <td>
                      <button
                        className="rp-btn rp-btn-sm"
                        type="button"
                        onClick={() => openHandle(item)}
                      >
                        {canUnfreeze ? '处理' : '详情'}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <div className="flex items-center gap-2 text-sm">
            <button
              className="rp-btn rp-btn-sm"
              type="button"
              disabled={ticketPage <= 1}
              onClick={() => setTicketPage((p) => Math.max(1, p - 1))}
            >
              上一页
            </button>
            <span>
              第 {ticketPage} / {ticketPageCount} 页 · 共 {ticketTotal} 条 · 每页 {ticketPageSize}
            </span>
            <button
              className="rp-btn rp-btn-sm"
              type="button"
              disabled={ticketPage >= ticketPageCount}
              onClick={() => setTicketPage((p) => p + 1)}
            >
              下一页
            </button>
          </div>
        </section>
      ) : null}

      {canAppeal && !canUnfreeze ? (
        <section className="rp-card p-4 space-y-2">
          <h2 className="text-sm font-medium">创建图片申诉</h2>
          <input
            className="rp-input w-full max-w-md"
            placeholder="申诉原因"
            value={appealReason}
            onChange={(event) => setAppealReason(event.target.value)}
          />
          <button className="rp-btn text-sm" type="button" onClick={() => void createAppeal()}>
            提交申诉
          </button>
        </section>
      ) : null}

      {canUnfreeze && deskTab === 'held' ? (
        <section className="rp-card p-4 space-y-2">
          <h2 className="text-sm font-medium">积分冻结（按租户聚合）</h2>
          <p className="text-xs text-muted-foreground">
            按租户展示 held 合计；FIFO 消耗预留直到达到本次释放金额，须写原因。每页 {heldPageSize} 条。
          </p>
          <table className="rp-table">
            <thead>
              <tr>
                <th className="text-left">租户</th>
                <th className="text-left">账号摘要</th>
                <th className="text-left">冻结合计</th>
                <th className="text-left">任务数</th>
                <th className="text-left">本次释放</th>
                <th className="text-left">原因</th>
                <th className="text-left">操作</th>
              </tr>
            </thead>
            <tbody>
              {heldItems.length === 0 ? (
                <tr>
                  <td className="rp-empty" colSpan={7}>
                    暂无技术失败冻结待客服任务
                  </td>
                </tr>
              ) : (
                heldItems.map((item) => {
                  const draft = heldDraft(item.tenantId)
                  return (
                    <tr key={item.tenantId}>
                      <td>{tenantLabel(item)}</td>
                      <td>{item.accountSummary || '—'}</td>
                      <td>{item.heldTotal}</td>
                      <td>{item.taskCount ?? '—'}</td>
                      <td>
                        <input
                          className="rp-input w-24"
                          placeholder="整数"
                          value={draft.amount}
                          onChange={(event) => patchHeldDraft(item.tenantId, { amount: event.target.value })}
                        />
                      </td>
                      <td>
                        <input
                          className="rp-input w-full min-w-[10rem]"
                          placeholder="审计原因"
                          value={draft.reason}
                          onChange={(event) => patchHeldDraft(item.tenantId, { reason: event.target.value })}
                        />
                      </td>
                      <td>
                        <button
                          className="rp-btn rp-btn-sm"
                          type="button"
                          onClick={() => void releaseHeldByAmount(item)}
                        >
                          释放
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
          <div className="flex items-center gap-2 text-sm">
            <button
              className="rp-btn rp-btn-sm"
              type="button"
              disabled={heldPage <= 1}
              onClick={() => setHeldPage((p) => Math.max(1, p - 1))}
            >
              上一页
            </button>
            <span>
              第 {heldPage} / {heldPageCount} 页 · 共 {heldTotal} 条
            </span>
            <button
              className="rp-btn rp-btn-sm"
              type="button"
              disabled={heldPage >= heldPageCount}
              onClick={() => setHeldPage((p) => p + 1)}
            >
              下一页
            </button>
          </div>
        </section>
      ) : null}

      {detail ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => closeHandle()}
          role="dialog"
          aria-modal="true"
          aria-label={`处理工单 ${detail.id}`}
        >
          <div
            className="max-h-[90vh] w-full max-w-lg space-y-3 overflow-y-auto rp-card p-4 text-sm shadow"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex justify-between gap-2">
              <strong>工单 {detail.id}</strong>
              <button
                type="button"
                className="rp-btn rp-btn-sm"
                onClick={() => closeHandle()}
              >
                关闭
              </button>
            </div>
            <p>类型：{ticketTypeLabel(detail.ticketType)}</p>
            <p>状态：{ticketStatusLabel(detail.status)}</p>
            <p>
              关联账号：{tenantLabel(detail)} / {accountLabel(detail)}
            </p>
            <p>原因：{detail.reason}</p>
            <p>时间：{formatDateTimeShort(detail.createdAt) || '（无）'}</p>
            {detail.resolvedAt ? (
              <p>
                办结：{detail.resolvedAt} / {detail.resolutionOutcome} / {detail.resolutionNote}
              </p>
            ) : null}
            {canUnfreeze && detail.status === 'open' && detail.ticketType === 'image_appeal' ? (
              <div className="space-y-2 border-t pt-2">
                <p className="font-medium">标记已处理（办结 ≠ 解锁图片）</p>
                <select
                  className="rp-input"
                  value={resolveOutcome}
                  onChange={(event) => setResolveOutcome(event.target.value)}
                >
                  <option value="accepted">通过/接受</option>
                  <option value="rejected">驳回</option>
                  <option value="resolved">已处理</option>
                </select>
                <input
                  className="rp-input ml-2 w-64"
                  placeholder="办结原因"
                  value={resolveNote}
                  onChange={(event) => setResolveNote(event.target.value)}
                />
                <button
                  className="rp-btn ml-2"
                  type="button"
                  onClick={() => void resolveDetail()}
                >
                  提交
                </button>
              </div>
            ) : null}
            {canUnfreeze && detail.ticketType === 'account_freeze' && detail.status === 'open' ? (
              <div className="space-y-2 border-t pt-2">
                <p className="font-medium">解除预审冻结</p>
                <p className="text-xs text-muted-foreground">
                  目标已锁定：{tenantLabel(detail)} / {accountLabel(detail)}
                </p>
                <input
                  className="rp-input w-full"
                  placeholder="解冻原因（必填）"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                />
                <button
                  className="rp-btn"
                  type="button"
                  onClick={() => void unfreezeFromDetail()}
                >
                  解冻
                </button>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </main>
  )
}
