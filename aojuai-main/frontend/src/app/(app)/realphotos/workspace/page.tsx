'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

import { RpPageHeader } from '@/components/realphotos/rp-page-header'
import { ApiError, apiFetch } from '@/lib/api'
import { formatRate } from '@/lib/format-rate'
import { ticketTypeLabel } from '@/lib/realphotos-labels'
import { formatDateTimeShort } from '@/lib/realphotos-time'

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
    costReason?: string | null
    costUnknownCount?: number | null
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

function costCell(cost: number | null | undefined, reason: string | null | undefined) {
  if (typeof cost === 'number') return String(cost)
  if (reason === 'no_upstream_calls') return '尚无调用'
  if (reason === 'unit_price_missing') return '暂无上游单价'
  if (reason) return `暂无数据（${reason}）`
  return '暂无数据'
}


export default function RealphotosWorkspacePage() {
  const [data, setData] = useState<WorkspacePayload | null>(null)
  const [message, setMessage] = useState('')

  useEffect(() => {
    void apiFetch<WorkspacePayload>('/api/v1/realphotos/workspace')
      .then((payload) => {
        setData(payload)

      })
      .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '工作台读取失败'))
  }, [])

  const view = data?.viewKind || (data?.merchantCards ? 'merchant' : 'admin')
  // 2026-11-17: 工作台删除搜索框；列表直接展示后端数据。最近历史按 10 条一页。
  const filteredOrders = data?.orderSupportDesk?.items || []
  const filteredTechTickets = data?.techSupportDesk?.items || []
  const historyRows = data?.recentHistory || []
  const [historyPage, setHistoryPage] = useState(1)
  const historyPageSize = 10
  const historyPageCount = Math.max(1, Math.ceil(historyRows.length / historyPageSize))
  const filteredHistory = historyRows.slice(
    (historyPage - 1) * historyPageSize,
    historyPage * historyPageSize,
  )

  const subtitle =
    view === 'admin'
      ? ''
      : view === 'order_support'
        ? '待处理充值单'
        : view === 'tech_support'
          ? '待处理工单'
          : '本账号概览与最近历史'

  return (
    <main className="space-y-6 p-6">
      <RpPageHeader title="工作台" description={subtitle || '按角色查看待办与本账号概览'} />
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
        <section className="grid max-w-5xl grid-cols-2 gap-3 md:grid-cols-4">
          <article className="rp-stat">
            <div className="rp-stat-label">可用积分</div>
            <div className="rp-stat-value">{cell(data.cards.availableInteger)}</div>
            <div className="rp-stat-hint">冻结 {cell(data.cards.reservedInteger)}</div>
          </article>
          <article className="rp-stat">
            <div className="rp-stat-label">进行中任务</div>
            <div className="rp-stat-value">{cell(data.cards.activeTasks)}</div>
          </article>
          <article className="rp-stat">
            <div className="rp-stat-label">本月已完成</div>
            <div className="rp-stat-value">{cell(data.cards.monthDelivered)}</div>
          </article>
          <article className="rp-stat">
            <div className="rp-stat-label">未读消息</div>
            <div className="rp-stat-value">{cell(data.cards.unreadMessages)}</div>
          </article>
        </section>
      ) : null}

      {view === 'admin' && data?.opsMetrics ? (
        <section className="rp-card p-4 shadow-sm">
          <h2 className="mb-2 text-sm font-medium">运营指标</h2>
          <table className="rp-table max-w-3xl border-collapse text-sm">
            <tbody>
              <tr>
                <th className="text-left">可用余额</th>
                <td>{cell(data.opsMetrics.availableInteger)}</td>
              </tr>
              <tr>
                <th className="text-left">冻结中</th>
                <td>{cell(data.opsMetrics.reservedInteger)}</td>
              </tr>
              <tr>
                <th className="text-left">队列</th>
                <td>{cell(data.opsMetrics.queueDepth)}</td>
              </tr>
              <tr>
                <th className="text-left">失败率</th>
                <td>{formatRate(data.opsMetrics.failureRate)}</td>
              </tr>
              <tr>
                <th className="text-left">检测通过率</th>
                <td>{formatRate(data.opsMetrics.detectionPassRate)}</td>
              </tr>
              <tr>
                <th className="text-left">成本</th>
                <td>
                  {costCell(data.opsMetrics.cost, data.opsMetrics.costReason)}
                </td>
              </tr>
              <tr>
                <th className="text-left">模型调用量</th>
                <td>{cell(data.opsMetrics.modelCalls)}</td>
              </tr>
              <tr>
                <th className="text-left">存储字节</th>
                <td>{cell(data.opsMetrics.storageBytes)}</td>
              </tr>
            </tbody>
          </table>
        </section>
      ) : null}

      {view === 'order_support' && data?.orderSupportDesk ? (
        <section className="rp-card space-y-3 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-medium">
              待处理充值单 · {data.orderSupportDesk.pendingRechargeOrders}
            </h2>
            <Link className="text-sm underline" href="/realphotos/order-support">
              打开充值确认
            </Link>
          </div>
          <table className="rp-table">
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
              {filteredOrders.length === 0 ? (
                <tr>
                  <td className="rp-empty" colSpan={6}>暂无待处理充值单</td>
                </tr>
              ) : (
                filteredOrders.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{item.tenantId}</td>
                    <td>{item.requesterUserId}</td>
                    <td>{item.tierYuan} 元</td>
                    <td>{item.creditPoints}</td>
                    <td>{formatDateTimeShort(item.createdAt) || '空'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      ) : null}

      {view === 'tech_support' && data?.techSupportDesk ? (
        <section className="rp-card space-y-3 p-4">
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
          <table className="rp-table">
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
              {filteredTechTickets.length === 0 ? (
                <tr>
                  <td className="rp-empty" colSpan={5}>暂无待处理工单</td>
                </tr>
              ) : (
                filteredTechTickets.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{ticketTypeLabel(item.ticketType)}</td>
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


    </main>
  )
}
