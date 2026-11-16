'use client'

import { useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { RpPageHeader } from '@/components/realphotos/rp-page-header'
import { ApiError, apiFetch } from '@/lib/api'

type LogRow = {
  id: number
  operatorUserId: number
  targetUserId: number
  tenantId: number
  operatorDisplay?: string
  targetDisplay?: string
  tenantDisplay?: string
  action: string
  actionLabel?: string
  reason: string
  result: string
  resultLabel?: string
  before: Record<string, unknown>
  after: Record<string, unknown>
}

export default function RealphotosLogsPage() {
  const [items, setItems] = useState<LogRow[]>([])
  const [message, setMessage] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [total, setTotal] = useState(0)

  useEffect(() => {
    void apiFetch<{ items: LogRow[]; page?: number; pageSize?: number; total?: number }>(
      `/api/v1/realphotos/account-logs?page=${page}`,
    )
      .then((data) => {
        setItems(Array.isArray(data.items) ? data.items : [])
        setPage(Number(data.page) || page)
        setPageSize(Number(data.pageSize) || 20)
        setTotal(Number(data.total) || (Array.isArray(data.items) ? data.items.length : 0))
      })
      .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '日志读取失败'))
  }, [page])

  const visibleItems = useMemo(
    () =>
      items.filter((item) =>
        matchSearchText(
          search,
          item.id,
          item.operatorDisplay,
          item.targetDisplay,
          item.tenantDisplay,
          item.action,
          item.actionLabel,
          item.reason,
          item.result,
          item.resultLabel,
          item.operatorUserId,
          item.targetUserId,
          item.tenantId,
        ),
      ),
    [items, search],
  )
  const pageCount = Math.max(1, Math.ceil(total / Math.max(pageSize, 1)))

  return (
    <main className="space-y-4 p-6">
      <RpPageHeader title="系统日志" />
      <p className="text-sm">{message}</p>
      <section className="rp-card rounded-xl border border-border bg-card p-4 shadow-sm space-y-3">
        <ListSearch value={search} placeholder="操作者 / 目标 / 动作 / 原因" onChange={setSearch} />
        <table className="rp-table w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="border px-2 py-1 text-left">时间序号</th>
              <th className="border px-2 py-1 text-left">操作者</th>
              <th className="border px-2 py-1 text-left">目标</th>
              <th className="border px-2 py-1 text-left">租户</th>
              <th className="border px-2 py-1 text-left">动作</th>
              <th className="border px-2 py-1 text-left">原因</th>
              <th className="border px-2 py-1 text-left">结果</th>
            </tr>
          </thead>
          <tbody>
            {visibleItems.map((item) => (
              <tr key={item.id}>
                <td className="border px-2 py-1">{item.id}</td>
                <td className="border px-2 py-1">
                  <div>{item.operatorDisplay || `用户 #${item.operatorUserId}`}</div>
                  <div className="text-xs text-muted-foreground">#{item.operatorUserId}</div>
                </td>
                <td className="border px-2 py-1">
                  <div>{item.targetDisplay || `用户 #${item.targetUserId}`}</div>
                  <div className="text-xs text-muted-foreground">#{item.targetUserId}</div>
                </td>
                <td className="border px-2 py-1">
                  <div>{item.tenantDisplay || `租户 #${item.tenantId}`}</div>
                  <div className="text-xs text-muted-foreground">#{item.tenantId}</div>
                </td>
                <td className="border px-2 py-1" title={item.action}>
                  {item.actionLabel || item.action}
                </td>
                <td className="border px-2 py-1">{item.reason}</td>
                <td className="border px-2 py-1" title={item.result}>
                  {item.resultLabel || item.result}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex items-center gap-2 text-sm">
          <button
            className="rp-btn border px-2 py-1"
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            上一页
          </button>
          <span>
            第 {page} / {pageCount} 页 · 共 {total} 条 · 每页 {pageSize}
          </span>
          <button
            className="rp-btn border px-2 py-1"
            type="button"
            disabled={page >= pageCount}
            onClick={() => setPage((p) => p + 1)}
          >
            下一页
          </button>
        </div>
      </section>
    </main>
  )
}
