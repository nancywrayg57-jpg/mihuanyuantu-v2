'use client'

import { useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { RpPageHeader } from '@/components/realphotos/rp-page-header'
import { toastTask } from '@/components/realphotos/surface'
import { ApiError, apiFetch } from '@/lib/api'
import { ledgerEntryTypeLabel } from '@/lib/realphotos-labels'
import { formatDateTimeShort } from '@/lib/realphotos-time'
import { RECHARGE_CREDITS_BY_YUAN, RECHARGE_TIERS_YUAN } from '@/lib/realphotos-s1'

type Wallet = { availableInteger?: string; reservedInteger?: string }
type Ledger = {
  id: string
  entryType: string
  operatorUserId?: string | null
  operatorDisplay?: string | null
  deltaAvailable: string
  deltaReserved?: string
  beforeAvailable?: string
  afterAvailable?: string
  beforeReserved?: string
  afterReserved?: string
  taskId?: string | null
  taskNo?: number | null
  taskKind?: 'processing' | 'generation' | null
  batchId?: string | null
  createdAt?: string | null
}
type PageData = { list?: Ledger[]; total?: number; currentPage?: number; pageSize?: number }

const LEDGER_PAGE_SIZE = 10

function signed(value: string | undefined): string {
  const num = Number(value || 0)
  if (num > 0) return `+${num}`
  return String(num)
}

function taskRef(row: Ledger): string {
  if (row.taskNo != null) {
    return `${row.taskKind === 'generation' ? '生图' : '处理'} #${row.taskNo}`
  }
  if (row.taskId) return `#${row.taskId}`
  return '—'
}

export default function RealphotosWalletPage() {
  const [wallet, setWallet] = useState<Wallet | null>(null)
  const [ledger, setLedger] = useState<Ledger[]>([])
  const [tier, setTier] = useState<number>(100)
  const [note, setNote] = useState('线下凭证')
  const [message, setMessage] = useState('')
  const [search, setSearch] = useState('')
  const [ledgerPage, setLedgerPage] = useState(1)
  const [ledgerTotal, setLedgerTotal] = useState(0)
  const [exporting, setExporting] = useState(false)

  async function reload() {
    const data = await apiFetch<Wallet>('/api/v1/realphotos/wallet')
    setWallet(data)
    const page = await apiFetch<PageData>(
      `/api/v1/realphotos/wallet/ledger?currentPage=${ledgerPage}&pageSize=${LEDGER_PAGE_SIZE}`,
    )
    setLedger(page.list || [])
    setLedgerTotal(Number(page.total || 0))
  }

  useEffect(() => {
    void reload().catch((error: unknown) =>
      setMessage(error instanceof ApiError ? error.message : '钱包加载失败'),
    )
  }, [ledgerPage])

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
      const text = `已提交充值单 ${data.id}，${data.creditPoints} 积分，公式 ${data.priceFormula}。等待订单客服确认。`
      setMessage(text)
      toastTask(text, true)
    } catch (error: unknown) {
      const text = error instanceof ApiError ? error.message : '提交失败'
      setMessage(text)
      toastTask(text, false)
    }
  }

  const credits = RECHARGE_CREDITS_BY_YUAN[tier]
  const visibleLedger = useMemo(
    () =>
      ledger.filter((row) =>
        matchSearchText(
          search,
          row.id,
          row.entryType,
          ledgerEntryTypeLabel(row.entryType),
          row.deltaAvailable,
          row.deltaReserved,
          row.operatorUserId,
          taskRef(row),
        ),
      ),
    [ledger, search],
  )

  async function exportLedger() {
    if (exporting) return
    setExporting(true)
    try {
      const all: Ledger[] = []
      let page = 1
      for (;;) {
        const data = await apiFetch<PageData>(
          `/api/v1/realphotos/wallet/ledger?currentPage=${page}&pageSize=100`,
        )
        const rows = data.list || []
        all.push(...rows)
        const total = Number(data.total || 0)
        if (rows.length === 0 || all.length >= total) break
        page += 1
      }
      const header = [
        '流水号',
        '类型',
        '可用变动',
        '冻结变动',
        '变动后可用',
        '变动后冻结',
        '关联任务',
        '操作账号',
        '时间',
      ]
      const exported = all.filter((row) =>
        matchSearchText(
          search,
          row.id,
          row.entryType,
          ledgerEntryTypeLabel(row.entryType),
          row.deltaAvailable,
          row.deltaReserved,
          row.operatorUserId,
          taskRef(row),
        ),
      )
      const lines = [
        header,
        ...exported.map((row) => [
          row.id,
          ledgerEntryTypeLabel(row.entryType),
          signed(row.deltaAvailable),
          signed(row.deltaReserved),
          row.afterAvailable ?? '',
          row.afterReserved ?? '',
          taskRef(row),
          row.operatorDisplay || row.operatorUserId || '',
          formatDateTimeShort(row.createdAt),
        ]),
      ]
      const csv = lines
        .map((line) => line.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
        .join('\r\n')
      const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `蜜獾原图-积分流水-${new Date().toISOString().slice(0, 10)}.csv`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      setMessage(`已导出 ${exported.length} 条流水。`)
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '导出失败')
    } finally {
      setExporting(false)
    }
  }

  return (
    <main className="space-y-6 p-6">
      <RpPageHeader title="积分与充值" />
      <p className="text-sm text-muted-foreground">{message}</p>
      <section className="rp-card p-4 shadow-sm">
      <table className="rp-table">
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
      </section>
      <section className="rp-card space-y-3 p-4">
        <h2 className="text-sm font-medium">充值档位</h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            档位（元）
            <select
              className="rp-input mt-1 block"
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
              className="rp-input mt-1 block"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </label>
          <button className="rp-btn rp-btn-primary text-sm" type="button" onClick={() => void createOrder()}>
            提交充值单
          </button>
        </div>
      </section>
      <section className="rp-card space-y-3 p-4">
        <div className="rp-filter flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-medium">流水</h2>
          <div className="flex flex-wrap items-center gap-2">
            <ListSearch value={search} placeholder="流水 / 类型 / 任务号 / 账号" onChange={setSearch} />
            <button className="rp-btn rp-btn-sm" type="button" disabled={exporting} onClick={() => void exportLedger()}>
              {exporting ? '导出中…' : '导出 CSV'}
            </button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          处理任务提交时先从可用余额冻结，检测/交付时从冻结里消费，因此「消费」类记录的可用变动为 0、冻结变动为负；
          「变动后」列展示该笔之后的可用 / 冻结余额。
        </p>
        <table className="rp-table">
          <thead>
            <tr>
              <th className="text-left">流水</th>
              <th className="text-left">类型</th>
              <th className="text-left">可用变动</th>
              <th className="text-left">冻结变动</th>
              <th className="text-left">变动后（可用 / 冻结）</th>
              <th className="text-left">关联任务</th>
              <th className="text-left">操作账号</th>
              <th className="text-left">时间</th>
            </tr>
          </thead>
          <tbody>
            {visibleLedger.map((row) => (
              <tr key={row.id}>
                <td>{row.id}</td>
                <td>{ledgerEntryTypeLabel(row.entryType)}</td>
                <td>{signed(row.deltaAvailable)}</td>
                <td>{signed(row.deltaReserved)}</td>
                <td>
                  {row.afterAvailable ?? '—'} / {row.afterReserved ?? '—'}
                </td>
                <td className="whitespace-nowrap">{taskRef(row)}</td>
                <td>{row.operatorDisplay || row.operatorUserId || ''}</td>
                <td className="whitespace-nowrap">{formatDateTimeShort(row.createdAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex items-center gap-2 text-sm">
          <button
            className="rp-btn rp-btn-sm"
            type="button"
            disabled={ledgerPage <= 1}
            onClick={() => setLedgerPage((p) => Math.max(1, p - 1))}
          >
            上一页
          </button>
          <span>
            第 {ledgerPage} / {Math.max(1, Math.ceil(ledgerTotal / LEDGER_PAGE_SIZE))} 页 · 共 {ledgerTotal} 条 · 每页 {LEDGER_PAGE_SIZE}
          </span>
          <button
            className="rp-btn rp-btn-sm"
            type="button"
            disabled={ledgerPage >= Math.max(1, Math.ceil(ledgerTotal / LEDGER_PAGE_SIZE))}
            onClick={() => setLedgerPage((p) => p + 1)}
          >
            下一页
          </button>
        </div>
      </section>
    </main>
  )
}
