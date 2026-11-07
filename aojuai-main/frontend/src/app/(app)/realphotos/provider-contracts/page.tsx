'use client'

import { useEffect, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

type Contract = {
  duty: string
  provider: string
  modelId: string
  configVersion: string
  region: string
  credentialRef: string
  baseUrl: string
  capabilities: Record<string, unknown>
  enabled: boolean
  gapNote: string
}

export default function RealphotosProviderContractsPage() {
  const [items, setItems] = useState<Contract[]>([])
  const [message, setMessage] = useState('')

  useEffect(() => {
    void apiFetch<{ items: Contract[] }>('/api/v1/realphotos/provider-contracts')
      .then((data) => setItems(data.items))
      .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '读取失败'))
  }, [])

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">模型合同</h1>
      <p className="text-sm text-muted-foreground">每项职责只有一套配置。这里不显示上游 Key。</p>
      <p className="text-sm">{message}</p>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className="border px-2 py-1 text-left">职责</th>
            <th className="border px-2 py-1 text-left">provider</th>
            <th className="border px-2 py-1 text-left">model ID</th>
            <th className="border px-2 py-1 text-left">版本</th>
            <th className="border px-2 py-1 text-left">区域</th>
            <th className="border px-2 py-1 text-left">凭据引用</th>
            <th className="border px-2 py-1 text-left">capabilities</th>
            <th className="border px-2 py-1 text-left">启用</th>
            <th className="border px-2 py-1 text-left">缺口</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.duty}>
              <td className="border px-2 py-1">{item.duty}</td>
              <td className="border px-2 py-1">{item.provider}</td>
              <td className="border px-2 py-1">{item.modelId || '空'}</td>
              <td className="border px-2 py-1">{item.configVersion}</td>
              <td className="border px-2 py-1">{item.region || '空'}</td>
              <td className="border px-2 py-1">{item.credentialRef || '空'}</td>
              <td className="border px-2 py-1">
                {Object.entries(item.capabilities || {})
                  .map(([key, value]) => `${key}=${String(value)}`)
                  .join('；') || '空'}
              </td>
              <td className="border px-2 py-1">{item.enabled ? '是' : '否'}</td>
              <td className="border px-2 py-1">{item.gapNote || '空'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  )
}
