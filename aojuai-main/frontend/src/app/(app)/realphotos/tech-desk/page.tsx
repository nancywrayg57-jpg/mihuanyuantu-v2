'use client'

import { useEffect, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'
import {
  creditDispositionLabel,
  ticketStatusLabel,
  ticketTypeLabel,
} from '@/lib/realphotos-labels'

type Ticket = {
  id: number
  tenantId: number
  ownerAccountId: number
  ticketType: string
  status: string
  reason: string
  createdAt?: string | null
  resolvedAt?: string | null
  resolutionOutcome?: string
  resolutionNote?: string
}

type HeldItem = {
  taskId: number
  tenantId: number
  ownerAccountId: number
  status: string
  failureClass?: string | null
  creditDisposition?: string | null
}

export default function RealphotosTechDeskPage() {
  const [items, setItems] = useState<Ticket[]>([])
  const [myItems, setMyItems] = useState<Ticket[]>([])
  const [heldItems, setHeldItems] = useState<HeldItem[]>([])
  const [userId, setUserId] = useState('')
  const [tenantId, setTenantId] = useState('')
  const [reason, setReason] = useState('')
  const [appealReason, setAppealReason] = useState('')
  const [resolveNote, setResolveNote] = useState('')
  const [resolveOutcome, setResolveOutcome] = useState('accepted')
  const [heldTaskId, setHeldTaskId] = useState('')
  const [heldTenantId, setHeldTenantId] = useState('')
  const [heldReason, setHeldReason] = useState('')
  const [message, setMessage] = useState('')
  const [ticketType, setTicketType] = useState('all')
  const [detail, setDetail] = useState<Ticket | null>(null)
  const [canUnfreeze, setCanUnfreeze] = useState(false)
  const [canAppeal, setCanAppeal] = useState(false)

  async function loadDesk() {
    const data = await apiFetch<{ items: Ticket[] }>('/api/v1/realphotos/support-tickets')
    setItems(data.items)
    setCanUnfreeze(true)
    const held = await apiFetch<{ items: HeldItem[] }>('/api/v1/realphotos/held-credits')
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
  const visible = source.filter((item) => ticketType === 'all' || item.ticketType === ticketType)
  const openCount = source.filter((item) => item.status === 'open').length

  async function unfreeze() {
    try {
      const payload = await apiFetch<{ closedFreezeTickets?: number }>(
        '/api/v1/realphotos/account-freezes/release',
        {
          method: 'POST',
          body: JSON.stringify({ userId: Number(userId), tenantId: Number(tenantId), reason }),
        },
      )
      setMessage(`已解除预审冻结；关闭冻结工单 ${payload.closedFreezeTickets ?? 0} 张`)
      await loadDesk()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '解冻失败')
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
      setMessage(`工单 ${updated.id} 已办结（${updated.resolutionOutcome}）；办结不等于解锁图片`)
      setDetail(updated)
      setResolveNote('')
      await loadDesk()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '办结失败')
    }
  }

  async function releaseHeld() {
    try {
      const payload = await apiFetch<{ disposition?: string }>(
        `/api/v1/realphotos/held-credits/${Number(heldTaskId)}/release`,
        {
          method: 'POST',
          body: JSON.stringify({ tenantId: Number(heldTenantId), reason: heldReason }),
        },
      )
      setMessage(`已释放冻结积分；处置=${payload.disposition || 'ok'}`)
      setHeldReason('')
      await loadDesk()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '释放失败')
    }
  }

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">工单管理</h1>
      <p className="text-sm text-muted-foreground">
        类型含 order / image_appeal / account_freeze。无数据时空态，不造假工单。解冻仅技术客服与平台管理员。
        办结申诉不等于解锁图片；释放技术失败冻结与预审解冻分开。
      </p>
      <p className="text-sm">
        {message}
        {canUnfreeze ? ` · 待处理 open=${openCount}` : ''}
      </p>
      <label className="text-sm">
        类型筛选
        <select className="ml-2 border px-2 py-1" value={ticketType} onChange={(event) => setTicketType(event.target.value)}>
          <option value="all">全部</option>
          <option value="account_freeze">{ticketTypeLabel('account_freeze')}</option>
          <option value="image_appeal">{ticketTypeLabel('image_appeal')}</option>
          <option value="order">{ticketTypeLabel('order')}</option>
        </select>
      </label>
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
                <td className="border px-2 py-1">{item.tenantId}</td>
                <td className="border px-2 py-1">{item.ownerAccountId}</td>
                <td className="border px-2 py-1">{ticketTypeLabel(item.ticketType)}</td>
                <td className="border px-2 py-1">{ticketStatusLabel(item.status)}</td>
                <td className="border px-2 py-1">{item.reason}</td>
                <td className="border px-2 py-1">
                  <button className="border px-2 py-0.5" type="button" onClick={() => setDetail(item)}>
                    详情
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      {detail ? (
        <div className="space-y-2 border p-3 text-sm">
          <div className="flex justify-between">
            <strong>工单 {detail.id}</strong>
            <button type="button" className="border px-2 py-0.5" onClick={() => setDetail(null)}>
              关闭面板
            </button>
          </div>
          <p>类型：{ticketTypeLabel(detail.ticketType)}</p>
          <p>状态：{ticketStatusLabel(detail.status)}</p>
          <p>关联账号：租户 {detail.tenantId} / 用户 {detail.ownerAccountId}</p>
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
              <button className="ml-2 border px-3 py-1" type="button" onClick={() => void resolveDetail()}>
                办结申诉
              </button>
            </div>
          ) : null}
          {canUnfreeze && detail.ticketType === 'account_freeze' && detail.status === 'open' ? (
            <p className="text-muted-foreground">冻结单请使用下方「解除预审冻结」办结并写审计。</p>
          ) : null}
        </div>
      ) : null}
      {canAppeal && !canUnfreeze ? (
        <section className="space-y-2">
          <h2 className="text-sm font-medium">创建图片申诉</h2>
          <input
            className="w-full max-w-md border px-2 py-1 text-sm"
            placeholder="申诉原因"
            value={appealReason}
            onChange={(event) => setAppealReason(event.target.value)}
          />
          <button className="border px-3 py-1 text-sm" type="button" onClick={() => void createAppeal()}>
            提交申诉
          </button>
          <p className="text-xs text-muted-foreground">商家无解冻按钮、无释放冻结积分入口。</p>
        </section>
      ) : null}
      {canUnfreeze ? (
        <>
          <section className="space-y-2">
            <h2 className="text-sm font-medium">解除预审冻结</h2>
            <input className="border px-2 py-1 text-sm" placeholder="用户编号" value={userId} onChange={(event) => setUserId(event.target.value)} />
            <input className="ml-2 border px-2 py-1 text-sm" placeholder="租户编号" value={tenantId} onChange={(event) => setTenantId(event.target.value)} />
            <input className="ml-2 border px-2 py-1 text-sm" placeholder="原因" value={reason} onChange={(event) => setReason(event.target.value)} />
            <button className="ml-2 border px-3 py-1 text-sm" type="button" onClick={() => void unfreeze()}>
              解冻
            </button>
          </section>
          <section className="space-y-2">
            <h2 className="text-sm font-medium">技术失败冻结积分释放</h2>
            <p className="text-xs text-muted-foreground">与预审解冻分开。当前 held 任务 {heldItems.length} 条。</p>
            <table className="w-full max-w-3xl border-collapse text-sm">
              <thead>
                <tr>
                  <th className="border px-2 py-1 text-left">任务</th>
                  <th className="border px-2 py-1 text-left">租户</th>
                  <th className="border px-2 py-1 text-left">账号</th>
                  <th className="border px-2 py-1 text-left">处置</th>
                </tr>
              </thead>
              <tbody>
                {heldItems.length === 0 ? (
                  <tr>
                    <td className="border px-2 py-1" colSpan={4}>
                      暂无技术失败冻结待客服任务
                    </td>
                  </tr>
                ) : (
                  heldItems.map((item) => (
                    <tr key={item.taskId}>
                      <td className="border px-2 py-1">{item.taskId}</td>
                      <td className="border px-2 py-1">{item.tenantId}</td>
                      <td className="border px-2 py-1">{item.ownerAccountId}</td>
                      <td className="border px-2 py-1">{creditDispositionLabel(item.creditDisposition)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            <input
              className="border px-2 py-1 text-sm"
              placeholder="任务编号"
              value={heldTaskId}
              onChange={(event) => setHeldTaskId(event.target.value)}
            />
            <input
              className="ml-2 border px-2 py-1 text-sm"
              placeholder="租户编号"
              value={heldTenantId}
              onChange={(event) => setHeldTenantId(event.target.value)}
            />
            <input
              className="ml-2 border px-2 py-1 text-sm"
              placeholder="审计原因"
              value={heldReason}
              onChange={(event) => setHeldReason(event.target.value)}
            />
            <button className="ml-2 border px-3 py-1 text-sm" type="button" onClick={() => void releaseHeld()}>
              释放冻结积分
            </button>
          </section>
        </>
      ) : null}
    </main>
  )
}
