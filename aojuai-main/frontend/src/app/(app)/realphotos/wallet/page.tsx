'use client'

import { useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { ApiError, apiFetch } from '@/lib/api'
import { RECHARGE_CREDITS_BY_YUAN, RECHARGE_TIERS_YUAN } from '@/lib/realphotos-s1'

type Wallet = { availableInteger?: string; reservedInteger?: string }
type Ledger = { id: string; entryType: string; operatorUserId?: string | null; deltaAvailable: string }
type PageData = { list?: Ledger[] }

export default function RealphotosWalletPage() {
  const [wallet, setWallet] = useState<Wallet | null>(null)
  const [ledger, setLedger] = useState<Ledger[]>([])
  const [tier, setTier] = useState<number>(100)
  const [note, setNote] = useState('线下凭证')
  const [message, setMessage] = useState('')
  const [search, setSearch] = useState('')

  async function reload() {
    const data = await apiFetch<Wallet>('/api/v1/realphotos/wallet')
    setWallet(data)
    const page = await apiFetch<PageData>('/api/v1/realphotos/wallet/ledger?currentPage=1&pageSize=20')
    setLedger(page.list || [])
  }

  useEffect(() => {
    void reload().catch((error: unknown) =>
      setMessage(error instanceof ApiError ? error.message : '钱包加载失败'),
    )
  }, [])

  async function createOrder() {
    try {
      const data = await apiFetch<{ id: string; creditPoints: number; priceFormula: string }>(
        '/api/v1/realphotos/recharge-orders',
        {
          method: 'POST',
          body: JSON.stringify({
            tierYuan: tier,
            voucherNote: note,
            idempotencyKey: `ui-recharge-${tier}-${Date.now()}`,
          }),
        },
      )
      setMessage(`已提交充值单 ${data.id}，${data.creditPoints} 积分，公式 ${data.priceFormula}。等待订单客服确认。`)
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '提交失败')
    }
  }

  const credits = RECHARGE_CREDITS_BY_YUAN[tier]
  const visibleLedger = useMemo(
    () => ledger.filter((row) => matchSearchText(search, row.id, row.entryType, row.deltaAvailable, row.operatorUserId)),
    [ledger, search],
  )

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">积分与充值</h1>
      <p className="text-sm text-muted-foreground">{message}</p>
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="text-left">可用余额</th>
            <th className="text-left">冻结中</th>
            <th className="text-left">档位换算</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{wallet?.availableInteger ?? '—'}</td>
            <td>{wallet?.reservedInteger ?? '—'}</td>
            <td>
              {tier} 元 → {credits} 积分
            </td>
          </tr>
        </tbody>
      </table>
      <section className="space-y-3">
        <h2 className="text-sm font-medium">充值档位</h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            档位（元）
            <select
              className="mt-1 block border px-2 py-1 text-sm"
              value={tier}
              onChange={(event) => setTier(Number(event.target.value))}
            >
              {RECHARGE_TIERS_YUAN.map((yuan) => (
                <option key={yuan} value={yuan}>
                  {yuan} 元 = {RECHARGE_CREDITS_BY_YUAN[yuan]} 积分
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            凭证备注
            <input
              className="mt-1 block border px-2 py-1 text-sm"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </label>
          <button className="border px-3 py-1 text-sm" type="button" onClick={() => void createOrder()}>
            提交充值单
          </button>
        </div>
      </section>
      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-medium">流水</h2>
          <ListSearch value={search} placeholder="流水 / 类型 / 账号" onChange={setSearch} />
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="text-left">流水</th>
              <th className="text-left">类型</th>
              <th className="text-left">可用变动</th>
              <th className="text-left">操作账号</th>
            </tr>
          </thead>
          <tbody>
            {visibleLedger.map((row) => (
              <tr key={row.id}>
                <td>{row.id}</td>
                <td>{row.entryType}</td>
                <td>{row.deltaAvailable}</td>
                <td>{row.operatorUserId || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  )
}
