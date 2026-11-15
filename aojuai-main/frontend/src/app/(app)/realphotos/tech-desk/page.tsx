'use client'

import { useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { toastTask } from '@/components/realphotos/surface'
import { ApiError, apiFetch } from '@/lib/api'
import {
  ticketStatusLabel,
  ticketTypeLabel,
} from '@/lib/realphotos-labels'

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
  const [userId, setUserId] = useState('')
  const [tenantId, setTenantId] = useState('')
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

  async function loadDesk() {
    const data = await apiFetch<{ items: Ticket[] }>('/api/v1/realphotos/support-tickets')
    setItems(data.items)
    setCanUnfreeze(true)
    const held = await apiFetch<{ items: HeldTenantItem[] }>('/api/v1/realphotos/held-credits')
    setHeldItems(held.items || [])
  }

  async function loadMine() {
    const data = await apiFetch<{ items: Ticket[] }>('/api/v1/realphotos/my-support-tickets')
    setMyItems(data.items || [])
    setCanAppeal(true)
  }

  useEffect(() => {
    void loadDesk().catch(() => {
      setCanUnfreeze(false)
      void loadMine().catch((error: unknown) =>
        setMessage(error instanceof ApiError ? error.message : '工单读取失败'),
      )
    })
  }, [])

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

  function openHandle(item: Ticket) {
    setDetail(item)
    setResolveNote('')
    setResolveOutcome('accepted')
  }

  function closeHandle() {
    setDetail(null)
    setResolveNote('')
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

  async function unfreeze() {
    try {
      const payload = await apiFetch<{ closedFreezeTickets?: number }>(
        '/api/v1/realphotos/account-freezes/release',
        {
          method: 'POST',
          body: JSON.stringify({ userId: Number(userId), tenantId: Number(tenantId), reason }),
        },
      )
      const text = `已解除预审冻结；关闭冻结工单 ${payload.closedFreezeTickets ?? 0} 张`
      setMessage(text)
      toastTask(text, true)
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
      await loadDesk()
    } catch (error: unknown) {
      const text = error instanceof ApiError ? error.message : '释放失败'
      setMessage(text)
      toastTask(text, false)
    }
  }

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">工单管理</h1>
      <p className="text-sm">
        {message}
        {canUnfreeze ? ` · 待处理 open=${openCount}` : ''}
      </p>

      {canUnfreeze ? (
        <div className="flex gap-2 text-sm">
          <button
            className={`rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-3 py-1 ${deskTab === 'appeals' ? 'bg-muted' : ''}`}
            type="button"
            onClick={() => setDeskTab('appeals')}
          >
            账号申诉
          </button>
          <button
            className={`rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-3 py-1 ${deskTab === 'held' ? 'bg-muted' : ''}`}
            type="button"
            onClick={() => setDeskTab('held')}
          >
            积分冻结
          </button>
        </div>
      ) : null}

      {(!canUnfreeze || deskTab === 'appeals') ? (
        <section className="rp-card rounded-xl border border-border bg-card p-4 shadow-sm space-y-3">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <label>
              类型筛选
              <select className="ml-2 border px-2 py-1" value={ticketType} onChange={(event) => setTicketType(event.target.value)}>
                <option value="all">全部</option>
                <option value="account_freeze">{ticketTypeLabel('account_freeze')}</option>
                <option value="image_appeal">{ticketTypeLabel('image_appeal')}</option>
                <option value="order">{ticketTypeLabel('order')}</option>
              </select>
            </label>
            <ListSearch value={search} placeholder="编号 / 租户 / 账号 / 原因" onChange={setSearch} />
          </div>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className="border px-2 py-1 text-left">编号</th>
                <th className="border px-2 py-1 text-left">租户</th>
                <th className="border px-2 py-1 text-left">账号</th>
                <th className="border px-2 py-1 text-left">类型</th>
                <th className="border px-2 py-1 text-left">状态</th>
                <th className="border px-2 py-1 text-left">原因</th>
                <th className="border px-2 py-1 text-left">操作</th>
              </tr>
            </thead>
            <tbody>
              {visible.length === 0 ? (
                <tr>
                  <td className="border px-2 py-1" colSpan={7}>
                    尚无工单
                  </td>
                </tr>
              ) : (
                visible.map((item) => (
                  <tr key={item.id}>
                    <td className="border px-2 py-1">{item.id}</td>
                    <td className="border px-2 py-1">{tenantLabel(item)}</td>
                    <td className="border px-2 py-1">{accountLabel(item)}</td>
                    <td className="border px-2 py-1">{ticketTypeLabel(item.ticketType)}</td>
                    <td className="border px-2 py-1">{ticketStatusLabel(item.status)}</td>
                    <td className="border px-2 py-1">{item.reason}</td>
                    <td className="border px-2 py-1">
                      <button
                        className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-0.5"
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
        </section>
      ) : null}

      {canAppeal && !canUnfreeze ? (
        <section className="rp-card rounded-xl border border-border bg-card shadow-sm p-4 space-y-2">
          <h2 className="text-sm font-medium">创建图片申诉</h2>
          <input
            className="w-full max-w-md border px-2 py-1 text-sm"
            placeholder="申诉原因"
            value={appealReason}
            onChange={(event) => setAppealReason(event.target.value)}
          />
          <button className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-3 py-1 text-sm" type="button" onClick={() => void createAppeal()}>
            提交申诉
          </button>
        </section>
      ) : null}

      {canUnfreeze && deskTab === 'appeals' ? (
        <section className="rp-card rounded-xl border border-border bg-card shadow-sm p-4 space-y-2">
          <h2 className="text-sm font-medium">解除预审冻结</h2>
          <input className="border px-2 py-1 text-sm" placeholder="用户编号" value={userId} onChange={(event) => setUserId(event.target.value)} />
          <input className="ml-2 border px-2 py-1 text-sm" placeholder="租户编号" value={tenantId} onChange={(event) => setTenantId(event.target.value)} />
          <input className="ml-2 border px-2 py-1 text-sm" placeholder="原因" value={reason} onChange={(event) => setReason(event.target.value)} />
          <button className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none ml-2 border px-3 py-1 text-sm" type="button" onClick={() => void unfreeze()}>
            解冻
          </button>
        </section>
      ) : null}

      {canUnfreeze && deskTab === 'held' ? (
        <section className="rp-card rounded-xl border border-border bg-card shadow-sm p-4 space-y-2">
          <h2 className="text-sm font-medium">积分冻结（按租户聚合）</h2>
          <p className="text-xs text-muted-foreground">按租户展示 held 合计；FIFO 消耗预留直到达到本次释放金额，须写原因。</p>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className="border px-2 py-1 text-left">租户</th>
                <th className="border px-2 py-1 text-left">账号摘要</th>
                <th className="border px-2 py-1 text-left">冻结合计</th>
                <th className="border px-2 py-1 text-left">任务数</th>
                <th className="border px-2 py-1 text-left">本次释放</th>
                <th className="border px-2 py-1 text-left">原因</th>
                <th className="border px-2 py-1 text-left">操作</th>
              </tr>
            </thead>
            <tbody>
              {heldItems.length === 0 ? (
                <tr>
                  <td className="border px-2 py-1" colSpan={7}>
                    暂无技术失败冻结待客服任务
                  </td>
                </tr>
              ) : (
                heldItems.map((item) => {
                  const draft = heldDraft(item.tenantId)
                  return (
                    <tr key={item.tenantId}>
                      <td className="border px-2 py-1">{tenantLabel(item)}</td>
                      <td className="border px-2 py-1">{item.accountSummary || '—'}</td>
                      <td className="border px-2 py-1">{item.heldTotal}</td>
                      <td className="border px-2 py-1">{item.taskCount ?? '—'}</td>
                      <td className="border px-2 py-1">
                        <input
                          className="w-24 border px-2 py-1"
                          placeholder="整数"
                          value={draft.amount}
                          onChange={(event) => patchHeldDraft(item.tenantId, { amount: event.target.value })}
                        />
                      </td>
                      <td className="border px-2 py-1">
                        <input
                          className="w-full min-w-[10rem] border px-2 py-1"
                          placeholder="审计原因"
                          value={draft.reason}
                          onChange={(event) => patchHeldDraft(item.tenantId, { reason: event.target.value })}
                        />
                      </td>
                      <td className="border px-2 py-1">
                        <button
                          className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-0.5"
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
            className="max-h-[90vh] w-full max-w-lg space-y-3 overflow-y-auto rp-card rounded-xl border border-border bg-card p-4 text-sm shadow"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex justify-between gap-2">
              <strong>工单 {detail.id}</strong>
              <button
                type="button"
                className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-0.5"
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
            <p>时间：{detail.createdAt || '（无）'}</p>
            {detail.resolvedAt ? (
              <p>
                办结：{detail.resolvedAt} / {detail.resolutionOutcome} / {detail.resolutionNote}
              </p>
            ) : null}
            {canUnfreeze && detail.status === 'open' && detail.ticketType === 'image_appeal' ? (
              <div className="space-y-2 border-t pt-2">
                <p className="font-medium">标记已处理（办结 ≠ 解锁图片）</p>
                <select
                  className="border px-2 py-1"
                  value={resolveOutcome}
                  onChange={(event) => setResolveOutcome(event.target.value)}
                >
                  <option value="accepted">通过/接受</option>
                  <option value="rejected">驳回</option>
                  <option value="resolved">已处理</option>
                </select>
                <input
                  className="ml-2 w-64 border px-2 py-1"
                  placeholder="办结原因"
                  value={resolveNote}
                  onChange={(event) => setResolveNote(event.target.value)}
                />
                <button
                  className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none ml-2 border px-3 py-1"
                  type="button"
                  onClick={() => void resolveDetail()}
                >
                  提交
                </button>
              </div>
            ) : null}
            {canUnfreeze && detail.ticketType === 'account_freeze' && detail.status === 'open' ? (
              <p className="text-muted-foreground">冻结单请在「账号申诉」页下方「解除预审冻结」办结并写审计。</p>
            ) : null}
          </div>
        </div>
      ) : null}
    </main>
  )
}
