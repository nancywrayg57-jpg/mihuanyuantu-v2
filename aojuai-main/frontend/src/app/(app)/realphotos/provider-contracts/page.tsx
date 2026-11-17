'use client'

import { useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
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
  const [search, setSearch] = useState('')

  useEffect(() => {
    void apiFetch<{ items: Contract[] }>('/api/v1/realphotos/provider-contracts')
      .then((data) => setItems(data.items))
      .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '读取失败'))
  }, [])

  const visibleItems = useMemo(
    () =>
      items.filter((item) =>
        matchSearchText(search, item.duty, item.provider, item.modelId, item.configVersion, item.region, item.gapNote),
      ),
    [items, search],
  )

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">模型合同</h1>
      <p className="text-sm">{message}</p>
      <section className="rp-card p-4 shadow-sm space-y-3">
      <ListSearch value={search} placeholder="职责 / 提供商 / 模型" onChange={setSearch} />
      <table className="rp-table">
        <thead>
          <tr>
            <th className="text-left">职责</th>
            <th className="text-left">provider</th>
            <th className="text-left">model ID</th>
            <th className="text-left">版本</th>
            <th className="text-left">区域</th>
            <th className="text-left">凭据引用</th>
            <th className="text-left">capabilities</th>
            <th className="text-left">启用</th>
            <th className="text-left">缺口</th>
          </tr>
        </thead>
        <tbody>
          {visibleItems.map((item) => (
            <tr key={item.duty}>
              <td>{item.duty}</td>
              <td>{item.provider}</td>
              <td>{item.modelId || '空'}</td>
              <td>{item.configVersion}</td>
              <td>{item.region || '空'}</td>
              <td>{item.credentialRef || '空'}</td>
              <td>
                {Object.entries(item.capabilities || {})
                  .map(([key, value]) => `${key}=${String(value)}`)
                  .join('；') || '空'}
              </td>
              <td>{item.enabled ? '是' : '否'}</td>
              <td>{item.gapNote || '空'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </section>
    </main>
  )
}
