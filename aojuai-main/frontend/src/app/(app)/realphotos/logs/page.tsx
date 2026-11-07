'use client'

import { useEffect, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

type LogRow = {
  id: number
  operatorUserId: number
  targetUserId: number
  tenantId: number
  action: string
  reason: string
  result: string
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
      <p className="text-sm text-muted-foreground">每页 {pageSize} 条。只记录成功的用户账号变更。</p>
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
              <td className="border px-2 py-1">{item.operatorUserId}</td>
              <td className="border px-2 py-1">{item.targetUserId}</td>
              <td className="border px-2 py-1">{item.tenantId}</td>
              <td className="border px-2 py-1">{item.action}</td>
              <td className="border px-2 py-1">{item.reason}</td>
              <td className="border px-2 py-1">{item.result}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  )
}
