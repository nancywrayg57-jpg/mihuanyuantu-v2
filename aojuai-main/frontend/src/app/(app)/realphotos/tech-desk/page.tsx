'use client'

import { useEffect, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

type Ticket = {
  id: number
  tenantId: number
  ownerAccountId: number
  ticketType: string
  status: string
  reason: string
}

export default function RealphotosTechDeskPage() {
  const [items, setItems] = useState<Ticket[]>([])
  const [userId, setUserId] = useState('')
  const [tenantId, setTenantId] = useState('')
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState('')

  async function load() {
    const data = await apiFetch<{ items: Ticket[] }>('/api/v1/realphotos/support-tickets')
    setItems(data.items)
  }

  useEffect(() => {
    void load().catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '工单读取失败'))
  }, [])

  async function unfreeze() {
    try {
      await apiFetch('/api/v1/realphotos/account-freezes/release', {
        method: 'POST',
        body: JSON.stringify({ userId: Number(userId), tenantId: Number(tenantId), reason }),
      })
      setMessage('已解除预审冻结')
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '解冻失败')
    }
  }

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">技术客服</h1>
      <p className="text-sm">{message}</p>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className="border px-2 py-1 text-left">编号</th>
            <th className="border px-2 py-1 text-left">租户</th>
            <th className="border px-2 py-1 text-left">账号</th>
            <th className="border px-2 py-1 text-left">类型</th>
            <th className="border px-2 py-1 text-left">状态</th>
            <th className="border px-2 py-1 text-left">原因</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td className="border px-2 py-1">{item.id}</td>
              <td className="border px-2 py-1">{item.tenantId}</td>
              <td className="border px-2 py-1">{item.ownerAccountId}</td>
              <td className="border px-2 py-1">{item.ticketType}</td>
              <td className="border px-2 py-1">{item.status}</td>
              <td className="border px-2 py-1">{item.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <section className="space-y-2">
        <h2 className="text-sm font-medium">解除预审冻结</h2>
        <input className="border px-2 py-1 text-sm" placeholder="用户编号" value={userId} onChange={(event) => setUserId(event.target.value)} />
        <input className="ml-2 border px-2 py-1 text-sm" placeholder="租户编号" value={tenantId} onChange={(event) => setTenantId(event.target.value)} />
        <input className="ml-2 border px-2 py-1 text-sm" placeholder="原因" value={reason} onChange={(event) => setReason(event.target.value)} />
        <button className="ml-2 border px-3 py-1 text-sm" type="button" onClick={() => void unfreeze()}>解冻</button>
      </section>
    </main>
  )
}
