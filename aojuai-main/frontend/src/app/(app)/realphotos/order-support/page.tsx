'use client'

import { useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { ApiError, apiFetch } from '@/lib/api'
import { taskStatusLabel } from '@/lib/realphotos-labels'

type Order = {
  id: string
  tenantId: string
  tierYuan: number
  creditPoints: number
  voucherNote: string
  status: string
}

export default function RealphotosOrderSupportPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState('')
  const [search, setSearch] = useState('')

  async function reload() {
    const data = await apiFetch<{ items: Order[] }>('/api/v1/realphotos/recharge-orders')
    setOrders(data.items || [])
  }

  useEffect(() => {
    void reload().catch((error: unknown) =>
      setMessage(error instanceof ApiError ? error.message : '订单加载失败'),
    )
  }, [])

  async function confirm(id: string) {
    await apiFetch(`/api/v1/realphotos/recharge-orders/${id}/confirm`, { method: 'POST' })
    setMessage(`已确认 ${id}`)
    await reload()
  }

  async function reject(id: string) {
    if (!reason.trim()) {
      setMessage('拒单必须填写原因')
      return
    }
    await apiFetch(`/api/v1/realphotos/recharge-orders/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    })
    setMessage(`已拒单 ${id}`)
    await reload()
  }

  const visibleOrders = useMemo(
    () =>
      orders.filter((item) =>
        matchSearchText(
          search,
          item.id,
          item.tenantId,
          item.tierYuan,
          item.creditPoints,
          item.voucherNote,
          item.status,
          taskStatusLabel(item.status),
        ),
      ),
    [orders, search],
  )

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">订单客服</h1>
      <p className="text-sm text-muted-foreground">{message}</p>
      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-medium">充值单</h2>
          <ListSearch value={search} placeholder="单号 / 租户 / 凭证" onChange={setSearch} />
        </div>
        <label className="block text-sm">
          拒单原因
          <input
            className="mt-1 block w-full max-w-md border px-2 py-1 text-sm"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="text-left">订单</th>
              <th className="text-left">租户</th>
              <th className="text-left">金额</th>
              <th className="text-left">积分</th>
              <th className="text-left">凭证</th>
              <th className="text-left">状态</th>
              <th className="text-left">操作</th>
            </tr>
          </thead>
          <tbody>
            {visibleOrders.length === 0 ? (
              <tr>
                <td colSpan={7}>暂无充值单</td>
              </tr>
            ) : (
              visibleOrders.map((order) => (
                <tr key={order.id}>
                  <td>{order.id}</td>
                  <td>{order.tenantId}</td>
                  <td>{order.tierYuan}</td>
                  <td>{order.creditPoints}</td>
                  <td>{order.voucherNote}</td>
                  <td>{taskStatusLabel(order.status)}</td>
                  <td className="space-x-2">
                    <button className="border px-2 py-1" type="button" onClick={() => void confirm(order.id)}>
                      确认到账
                    </button>
                    <button className="border px-2 py-1" type="button" onClick={() => void reject(order.id)}>
                      拒单
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </main>
  )
}
