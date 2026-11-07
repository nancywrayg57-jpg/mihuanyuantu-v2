'use client'

import { useEffect, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

type Metrics = {
  availableInteger: number
  reservedInteger: number
  queueDepth: number
  failureRate: number | null
  detectionPassRate: number | null
  cost: number | null
  modelCalls: number | null
  storageBytes: number
  merchantCards: boolean
}

function cell(value: number | null) {
  return value === null ? '空' : String(value)
}

export default function RealphotosAdminPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [message, setMessage] = useState('')

  useEffect(() => {
    void apiFetch<Metrics>('/api/v1/realphotos/ops-metrics')
      .then((data) => setMetrics(data))
      .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '指标读取失败'))
  }, [])

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">运营指标</h1>
      <p className="text-sm">{message}</p>
      <table className="w-full max-w-3xl border-collapse text-sm">
        <tbody>
          <tr><th className="border px-2 py-1 text-left">可用余额</th><td className="border px-2 py-1">{cell(metrics?.availableInteger ?? null)}</td></tr>
          <tr><th className="border px-2 py-1 text-left">冻结中</th><td className="border px-2 py-1">{cell(metrics?.reservedInteger ?? null)}</td></tr>
          <tr><th className="border px-2 py-1 text-left">队列</th><td className="border px-2 py-1">{cell(metrics?.queueDepth ?? null)}</td></tr>
          <tr><th className="border px-2 py-1 text-left">失败率</th><td className="border px-2 py-1">{cell(metrics?.failureRate ?? null)}</td></tr>
          <tr><th className="border px-2 py-1 text-left">检测通过率</th><td className="border px-2 py-1">{cell(metrics?.detectionPassRate ?? null)}</td></tr>
          <tr><th className="border px-2 py-1 text-left">成本</th><td className="border px-2 py-1">{cell(metrics?.cost ?? null)}</td></tr>
          <tr><th className="border px-2 py-1 text-left">模型调用量</th><td className="border px-2 py-1">{cell(metrics?.modelCalls ?? null)}</td></tr>
          <tr><th className="border px-2 py-1 text-left">存储字节</th><td className="border px-2 py-1">{cell(metrics?.storageBytes ?? null)}</td></tr>
        </tbody>
      </table>
    </main>
  )
}
