'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

import { RpPageHeader } from '@/components/realphotos/rp-page-header'
import { toastTask } from '@/components/realphotos/surface'
import { ApiError, apiFetch, apiFetchBlob } from '@/lib/api'
import { formatRate } from '@/lib/format-rate'
import { failureClassLabelForTask, taskStatusLabel, ticketTypeLabel } from '@/lib/realphotos-labels'
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
    taskNo?: number | null
    status: string
    createdAt: string | null
    presetCode?: string
    presetName?: string
    mode?: string
    objectKey?: string | null
    failureClass?: string | null
    failureTitle?: string | null
    failureMessage?: string | null
    canReprocess?: boolean
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
  const router = useRouter()
  const [data, setData] = useState<WorkspacePayload | null>(null)
  const [message, setMessage] = useState('')
  const [thumbs, setThumbs] = useState<Record<string, string>>({})
  const [reprocessing, setReprocessing] = useState<string | null>(null)

  async function reload() {
    const payload = await apiFetch<WorkspacePayload>('/api/v1/realphotos/workspace')
    setData(payload)
  }

  useEffect(() => {
    void reload().catch((error: unknown) =>
      setMessage(error instanceof ApiError ? error.message : '工作台读取失败'),
    )
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

  // 2026-11-18 UX-P1-7：最近历史缩略图（结果图优先，未交付时用源图）。
  useEffect(() => {
    let cancelled = false
    const created: string[] = []
    setThumbs({})
    void (async () => {
      for (const item of filteredHistory) {
        if (!item.objectKey) continue
        try {
          const path = String(item.objectKey).split('/').map(encodeURIComponent).join('/')
          const blob = await apiFetchBlob(
            `/api/v1/realphotos/gateway/objects/${path}?thumb=160`,
          )
          if (cancelled) return
          const url = URL.createObjectURL(blob)
          created.push(url)
          setThumbs((prev) => ({ ...prev, [item.id]: url }))
        } catch {
          // 单张失败不阻断
        }
      }
    })()
    return () => {
      cancelled = true
      for (const url of created) URL.revokeObjectURL(url)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, historyPage])

  async function reprocess(item: WorkspacePayload['recentHistory'][number]) {
    if (reprocessing) return
    setReprocessing(item.id)
    try {
      await apiFetch(`/api/v1/realphotos/processing-tasks/${item.id}/reprocess`, {
        method: 'POST',
        body: JSON.stringify({
          presetCode: item.presetCode,
          idempotencyKey: `ws-reprocess-${item.id}-${Date.now()}`,
        }),
      })
      toastTask('已建立重新处理任务，原任务报告仍保留', true)
      await reload()
    } catch (error: unknown) {
      toastTask(error instanceof ApiError ? error.message : '重新处理失败', false)
    } finally {
      setReprocessing(null)
    }
  }


  const subtitle =
    view === 'admin'
      ? '平台运营概览：队列、失败率与成本'
      : view === 'order_support'
        ? '待确认的充值单，确认后积分即时到账'
        : view === 'tech_support'
          ? '待处理工单，处理结果会通知商家'
          : '查看积分、任务与近期处理结果；处理新图从「批量原图」开始'

  return (
    <main className="space-y-6 p-6">
      <RpPageHeader title="工作台" description={subtitle || '按角色查看待办与本账号概览'} />
      {data?.preReviewFrozen && view === 'merchant' ? (
        <p className="rp-card border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          账号处于预审冻结：目前只能查看历史与保留期内的结果，解冻后可继续上传与处理。
        </p>
      ) : null}
      <p className="text-sm">{message}</p>

      {view === 'merchant' && data?.cards ? (
        <section className="grid max-w-5xl grid-cols-2 gap-3 md:grid-cols-4">
          <article className="rp-stat">
            <div className="rp-stat-label">可用积分</div>
            <div className="rp-stat-value">{cell(data.cards.availableInteger)}</div>
            <div className="rp-stat-hint">处理中冻结 {cell(data.cards.reservedInteger)} 分</div>
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

      {view === 'merchant' && historyRows.length === 0 ? (
        <section className="rp-card border-primary/25 bg-primary/5 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <h2 className="text-sm font-semibold text-foreground">三步完成第一张原图</h2>
              <p className="text-xs text-muted-foreground">
                ① 上传或导入图片 · ② 选择设备预设 · ③ 提交处理并等待检测结果
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link className="rp-btn rp-btn-primary rp-btn-sm" href="/realphotos/batch">
                开始处理
              </Link>
              <Link className="rp-btn rp-btn-sm" href="/realphotos/library">
                查看图片资源
              </Link>
            </div>
          </div>
        </section>
      ) : null}

      {view === 'admin' && data?.opsMetrics ? (
        <section className="rp-card rounded-xl border border-border bg-card p-4 shadow-sm">
          <h2 className="mb-2 text-sm font-medium">运营指标</h2>
          <table className="rp-table w-full max-w-3xl border-collapse text-sm">
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
                <td className="border px-2 py-1">{formatRate(data.opsMetrics.failureRate)}</td>
              </tr>
              <tr>
                <th className="border px-2 py-1 text-left">检测通过率</th>
                <td className="border px-2 py-1">{formatRate(data.opsMetrics.detectionPassRate)}</td>
              </tr>
              <tr>
                <th className="border px-2 py-1 text-left">成本</th>
                <td className="border px-2 py-1">
                  {costCell(data.opsMetrics.cost, data.opsMetrics.costReason)}
                </td>
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
          <p className="mt-2 text-xs text-muted-foreground">
            队列含预审与检测；失败率按近 24 小时统计。
          </p>
        </section>
      ) : null}

      {view === 'order_support' && data?.orderSupportDesk ? (
        <section className="rp-card rounded-xl border border-border bg-card shadow-sm p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-medium">
              待处理充值单 · {data.orderSupportDesk.pendingRechargeOrders}
            </h2>
            <Link className="text-sm underline" href="/realphotos/order-support">
              打开充值确认
            </Link>
          </div>
          <table className="rp-table w-full text-sm">
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
                  <td className="rp-empty" colSpan={6}>当前没有待确认的充值单。商家提交充值申请后会出现在这里。</td>
                </tr>
              ) : (
                filteredOrders.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{item.tenantId}</td>
                    <td>{item.requesterUserId}</td>
                    <td>{item.tierYuan} 元</td>
                    <td>{item.creditPoints}</td>
                    <td>{formatDateTimeShort(item.createdAt) || '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      ) : null}

      {view === 'tech_support' && data?.techSupportDesk ? (
        <section className="rp-card rounded-xl border border-border bg-card shadow-sm p-4 space-y-3">
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
          <table className="rp-table w-full text-sm">
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
                  <td className="rp-empty" colSpan={5}>当前没有待处理工单。商家提交图片申诉后会进入这里。</td>
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

      {view === 'merchant' ? (
        <section className="rp-card rounded-xl border border-border bg-card shadow-sm p-4 space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium">最近历史</h2>
            <Link className="text-sm underline" href="/realphotos/tasks">
              全部任务
            </Link>
          </div>
          <table className="rp-table w-full text-sm">
            <thead>
              <tr>
                <th className="text-left">缩略图</th>
                <th className="text-left">任务</th>
                <th className="text-left">状态</th>
                <th className="text-left">失败原因</th>
                <th className="text-left">时间</th>
                <th className="text-left">操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredHistory.length === 0 ? (
                <tr>
                  <td className="rp-empty" colSpan={6}>还没有处理记录。上传或导入图片后，这里会显示每次处理的状态与时间。</td>
                </tr>
              ) : (
                filteredHistory.map((item) => (
                  <tr
                    key={`${item.kind}-${item.id}`}
                    className="cursor-pointer hover:bg-muted/30"
                    onClick={() => router.push(`/realphotos/tasks?taskId=${item.id}`)}
                  >
                    <td>
                      {thumbs[item.id] ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={thumbs[item.id]}
                          alt=""
                          className="h-14 w-14 rounded border object-cover"
                        />
                      ) : (
                        <span className="inline-block h-14 w-14 border text-center leading-[3.5rem] text-xs">图</span>
                      )}
                    </td>
                    <td>
                      {item.kind === 'processing' ? '处理' : '生图'} #{item.taskNo ?? item.id}
                      {item.presetName ? (
                        <div className="max-w-[12rem] truncate text-xs text-muted-foreground">
                          {item.presetName}
                        </div>
                      ) : null}
                    </td>
                    <td>{taskStatusLabel(item.status)}</td>
                    <td className="max-w-[16rem] truncate" title={item.failureMessage || ''}>
                      {item.failureMessage ||
                        (item.failureClass ? failureClassLabelForTask(item.failureClass, '') : '—')}
                    </td>
                    <td className="whitespace-nowrap">{formatDateTimeShort(item.createdAt) || '—'}</td>
                    <td className="space-x-1 whitespace-nowrap">
                      {item.canReprocess ? (
                        <button
                          className="rp-btn rp-btn-sm"
                          type="button"
                          disabled={reprocessing === item.id}
                          onClick={(event) => {
                            event.stopPropagation()
                            void reprocess(item)
                          }}
                        >
                          {reprocessing === item.id ? '提交中…' : '重新处理'}
                        </button>
                      ) : null}
                      {item.status === 'IMAGE_LOCKED' ? (
                        <Link
                          className="rp-btn rp-btn-sm rp-btn-primary"
                          href="/realphotos/library"
                          onClick={(event) => event.stopPropagation()}
                        >
                          申诉
                        </Link>
                      ) : null}
                      <button
                        className="rp-btn rp-btn-sm"
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation()
                          router.push(`/realphotos/tasks?taskId=${item.id}`)
                        }}
                      >
                        详情
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <div className="flex items-center gap-2 text-sm">
            <button
              className="rp-btn border px-2 py-1"
              type="button"
              disabled={historyPage <= 1}
              onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}
            >
              上一页
            </button>
            <span>
              第 {historyPage} / {historyPageCount} 页 · 共 {historyRows.length} 条
            </span>
            <button
              className="rp-btn border px-2 py-1"
              type="button"
              disabled={historyPage >= historyPageCount}
              onClick={() => setHistoryPage((p) => p + 1)}
            >
              下一页
            </button>
          </div>
        </section>
      ) : null}

    </main>
  )
}
