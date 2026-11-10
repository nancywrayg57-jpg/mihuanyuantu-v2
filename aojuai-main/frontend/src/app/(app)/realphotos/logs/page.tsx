'use client'

import { useEffect, useState } from 'react'

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
  const [pageSize, setPageSize] = useState(20)
  const [message, setMessage] = useState('')

  useEffect(() => {
    void apiFetch<{ items: LogRow[]; pageSize: number }>('/api/v1/realphotos/account-logs')
      .then((data) => {
        setItems(data.items)
        setPageSize(data.pageSize)
      })
      .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '日志读取失败'))
  }, [])

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">系统日志</h1>
      <p className="text-sm text-muted-foreground">
        每页 {pageSize} 条。只记录成功的用户账号变更。主列显示名称；编号保留在次行便于运维核对。
      </p>
      <p className="text-sm">{message}</p>
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
          {items.map((item) => (
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
