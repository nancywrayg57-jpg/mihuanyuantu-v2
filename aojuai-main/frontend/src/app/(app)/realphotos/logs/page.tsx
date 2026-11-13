'use client'

import { useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
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

  useEffect(() => {
    void apiFetch<{ items: LogRow[]; pageSize: number }>('/api/v1/realphotos/account-logs')
      .then((data) => {
        setItems(data.items)
      })
      .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '日志读取失败'))
  }, [])

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

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">系统日志</h1>
      <p className="text-sm">{message}</p>
      <ListSearch value={search} placeholder="操作者 / 目标 / 动作 / 原因" onChange={setSearch} />
      <table className="w-full border-collapse text-sm">
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
    </main>
  )
}
