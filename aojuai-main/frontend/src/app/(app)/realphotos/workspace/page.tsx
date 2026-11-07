'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

type WorkspacePayload = {
  viewKind?: 'merchant' | 'admin' | 'order_support' | 'tech_support'
  merchantCards: boolean
  showTaskChainBanner: boolean
  preReviewFrozen: boolean
  cards: {
    availableInteger: string | number | null
    reservedInteger: string | number | null
    activeTasks: number | null
    monthDelivered: number | null
    unreadMessages: number | null
  } | null
  opsMetrics: {
    availableInteger: number | null
    reservedInteger: number | null
    queueDepth: number | null
    failureRate: number | null
    detectionPassRate: number | null
    cost: number | null
    modelCalls: number | null
    storageBytes: number | null
    merchantCards: boolean
  } | null
  orderSupportDesk?: {
    pendingRechargeOrders: number
    items: Array<{
      id: string
      tenantId: string
      requesterUserId: string
      tierYuan: number
      creditPoints: number
      status: string
      createdAt?: string | null
    }>
  } | null
  techSupportDesk?: {
    openTickets: number
    byType: Record<string, number>
    items: Array<{
      id: number
      tenantId: number
      ownerAccountId: number
      ticketType: string
      status: string
      reason: string
      createdAt?: string | null
    }>
  } | null
  recentHistory: Array<{
    kind: string
    id: string
    status: string
    createdAt: string | null
    presetCode?: string
    mode?: string
  }>
}

function cell(value: number | string | null | undefined, emptyLabel = '暂无数据') {
  if (value === null || value === undefined || value === '') return emptyLabel
  return String(value)
}

type Ticket = {
  id: number
  ticketType: string
  status: string
  reason: string
  createdAt?: string | null
}

export default function RealphotosWorkspacePage() {
  const [data, setData] = useState<WorkspacePayload | null>(null)
  const [message, setMessage] = useState('')
  const [appealReason, setAppealReason] = useState('')
  const [myTickets, setMyTickets] = useState<Ticket[]>([])

  useEffect(() => {
    void apiFetch<WorkspacePayload>('/api/v1/realphotos/workspace')
      .then((payload) => {
        setData(payload)
        if (payload.merchantCards) {
          void apiFetch<{ items: Ticket[] }>('/api/v1/realphotos/my-support-tickets')
            .then((rows) => setMyTickets(rows.items || []))
            .catch(() => undefined)
        }
      })
      .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '工作台读取失败'))
  }, [])

  const view = data?.viewKind || (data?.merchantCards ? 'merchant' : 'admin')

  async function createAppeal() {
    try {
      await apiFetch('/api/v1/realphotos/support-tickets', {
        method: 'POST',
        body: JSON.stringify({ ticketType: 'image_appeal', reason: appealReason }),
      })
      setMessage('已创建图片申诉')
      setAppealReason('')
      const rows = await apiFetch<{ items: Ticket[] }>('/api/v1/realphotos/my-support-tickets')
      setMyTickets(rows.items || [])
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '申诉创建失败')
    }
  }

  const subtitle =
    view === 'admin'
      ? '平台运营指标。不展示商家四卡。'
      : view === 'order_support'
        ? '订单客服工作台：待处理充值单。不展示商家四卡与业务原图历史。'
        : view === 'tech_support'
          ? '技术客服工作台：待处理工单。不展示商家四卡。'
          : '本账号概览与最近历史。'

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">工作台</h1>
      <p className="text-sm text-muted-foreground">{subtitle}</p>
      {data?.preReviewFrozen && view === 'merchant' ? (
        <p className="text-sm text-destructive">
          账号已冻结：可查看历史与保留期内结果，不能从工作台发起新获取或处理。请到
          <Link className="mx-1 underline" href="/realphotos/batch">
            批量原图
          </Link>
          会看到同样拒绝。
        </p>
      ) : null}
      <p className="text-sm">{message}</p>
      {data?.showTaskChainBanner ? <p className="text-sm">一条任务链</p> : null}

      {view === 'merchant' && data?.cards ? (
        <section className="grid max-w-4xl grid-cols-2 gap-3 text-sm md:grid-cols-4">
          <article className="border p-3">
            <div>可用积分</div>
            <div className="text-lg">{cell(data.cards.availableInteger)}</div>
            <div className="text-muted-foreground">冻结 {cell(data.cards.reservedInteger)}</div>
          </article>
          <article className="border p-3">
            <div>进行中任务</div>
            <div className="text-lg">{cell(data.cards.activeTasks)}</div>
            <div className="text-muted-foreground">本账号处理中</div>
          </article>
          <article className="border p-3">
            <div>本月已完成</div>
            <div className="text-lg">{cell(data.cards.monthDelivered)}</div>
            <div className="text-muted-foreground">DELIVERED 真实计数</div>
          </article>
          <article className="border p-3">
            <div>未读消息</div>
            <div className="text-lg">{cell(data.cards.unreadMessages)}</div>
            <div className="text-muted-foreground">本账号收件箱</div>
          </article>
        </section>
      ) : null}

      {view === 'admin' && data?.opsMetrics ? (
        <section>
          <h2 className="mb-2 text-sm font-medium">运营指标</h2>
          <table className="w-full max-w-3xl border-collapse text-sm">
            <tbody>
              <tr>
                <th className="border px-2 py-1 text-left">可用余额</th>
                <td className="border px-2 py-1">{cell(data.opsMetrics.availableInteger)}</td>
              </tr>
              <tr>
                <th className="border px-2 py-1 text-left">冻结中</th>
                <td className="border px-2 py-1">{cell(data.opsMetrics.reservedInteger)}</td>
              </tr>
              <tr>
                <th className="border px-2 py-1 text-left">队列</th>
                <td className="border px-2 py-1">{cell(data.opsMetrics.queueDepth)}</td>
              </tr>
              <tr>
                <th className="border px-2 py-1 text-left">失败率</th>
                <td className="border px-2 py-1">{cell(data.opsMetrics.failureRate)}</td>
              </tr>
              <tr>
                <th className="border px-2 py-1 text-left">检测通过率</th>
                <td className="border px-2 py-1">{cell(data.opsMetrics.detectionPassRate)}</td>
              </tr>
              <tr>
                <th className="border px-2 py-1 text-left">成本</th>
                <td className="border px-2 py-1">{cell(data.opsMetrics.cost)}</td>
              </tr>
              <tr>
                <th className="border px-2 py-1 text-left">模型调用量</th>
                <td className="border px-2 py-1">{cell(data.opsMetrics.modelCalls)}</td>
              </tr>
              <tr>
                <th className="border px-2 py-1 text-left">存储字节</th>
                <td className="border px-2 py-1">{cell(data.opsMetrics.storageBytes)}</td>
              </tr>
            </tbody>
          </table>
        </section>
      ) : null}

      {view === 'order_support' && data?.orderSupportDesk ? (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-medium">
              待处理充值单 · {data.orderSupportDesk.pendingRechargeOrders}
            </h2>
            <Link className="text-sm underline" href="/realphotos/order-support">
              打开充值确认
            </Link>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-left">单号</th>
                <th className="text-left">租户</th>
                <th className="text-left">申请人</th>
                <th className="text-left">档位</th>
                <th className="text-left">积分</th>
                <th className="text-left">时间</th>
              </tr>
            </thead>
            <tbody>
              {data.orderSupportDesk.items.length === 0 ? (
                <tr>
                  <td colSpan={6}>暂无待处理充值单</td>
                </tr>
              ) : (
                data.orderSupportDesk.items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{item.tenantId}</td>
                    <td>{item.requesterUserId}</td>
                    <td>{item.tierYuan} 元</td>
                    <td>{item.creditPoints}</td>
                    <td>{item.createdAt || '空'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      ) : null}

      {view === 'tech_support' && data?.techSupportDesk ? (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-medium">待处理工单 · {data.techSupportDesk.openTickets}</h2>
            <Link className="text-sm underline" href="/realphotos/tech-desk">
              打开工单管理
            </Link>
          </div>
          <p className="text-xs text-muted-foreground">
            按类型：
            {Object.keys(data.techSupportDesk.byType).length === 0
              ? '空'
              : Object.entries(data.techSupportDesk.byType)
                  .map(([k, v]) => `${k}=${v}`)
                  .join(' · ')}
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-left">编号</th>
                <th className="text-left">类型</th>
                <th className="text-left">租户</th>
                <th className="text-left">账号</th>
                <th className="text-left">原因</th>
              </tr>
            </thead>
            <tbody>
              {data.techSupportDesk.items.length === 0 ? (
                <tr>
                  <td colSpan={5}>暂无待处理工单</td>
                </tr>
              ) : (
                data.techSupportDesk.items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{item.ticketType}</td>
                    <td>{item.tenantId}</td>
                    <td>{item.ownerAccountId}</td>
                    <td>{item.reason}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      ) : null}

      {view === 'merchant' ? (
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium">最近历史（本账号）</h2>
            <Link className="text-sm underline" href="/realphotos/tasks">
              全部任务
            </Link>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-left">类型</th>
                <th className="text-left">编号</th>
                <th className="text-left">状态</th>
                <th className="text-left">时间</th>
              </tr>
            </thead>
            <tbody>
              {(data?.recentHistory || []).length === 0 ? (
                <tr>
                  <td colSpan={4}>暂无本账号历史</td>
                </tr>
              ) : (
                (data?.recentHistory || []).map((item) => (
                  <tr key={`${item.kind}-${item.id}`}>
                    <td>{item.kind === 'processing' ? '处理' : '生图'}</td>
                    <td>{item.id}</td>
                    <td>{item.status}</td>
                    <td>{item.createdAt || '空'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      ) : null}

      {view === 'merchant' ? (
        <section className="space-y-2">
          <h2 className="text-sm font-medium">图片申诉（本租户）</h2>
          <p className="text-xs text-muted-foreground">可查看/创建申诉；无解冻入口。</p>
          <div className="flex flex-wrap gap-2 text-sm">
            <input
              className="w-full max-w-md border px-2 py-1"
              placeholder="申诉原因"
              value={appealReason}
              onChange={(event) => setAppealReason(event.target.value)}
            />
            <button className="border px-3 py-1" type="button" onClick={() => void createAppeal()}>
              创建申诉
            </button>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-left">编号</th>
                <th className="text-left">类型</th>
                <th className="text-left">状态</th>
                <th className="text-left">原因</th>
              </tr>
            </thead>
            <tbody>
              {myTickets.length === 0 ? (
                <tr>
                  <td colSpan={4}>尚无本账号工单</td>
                </tr>
              ) : (
                myTickets.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{item.ticketType}</td>
                    <td>{item.status}</td>
                    <td>{item.reason}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      ) : null}
    </main>
  )
}
