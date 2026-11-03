'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

import { SimplePagination } from '@/components/list/simple-pagination'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ApiError, apiFetch } from '@/lib/api'
import { useT } from '@/lib/i18n'
import { useAuth } from '@/hooks/useAuth'

type PageResponse<T> = {
  list: T[]
  total: number
  pageSize: number
  currentPage: number
}

type CreditAccount = {
  id: number
  accountType: 'tenant' | 'user'
  balance: string
  totalEarned: string
  totalSpent: string
  status: 'active' | 'frozen'
  createdAt?: string | null
}

type CreditTransaction = {
  id: number
  transactionType: string
  amount: string
  direction: 'in' | 'out'
  balanceAfter: string
  remark?: string | null
  createdAt?: string | null
  extra?: Record<string, unknown>
}

const PAGE_SIZE = 20
type TFunction = ReturnType<typeof useT>

function getAccountStatusLabel(status: string, t: TFunction) {
  return status === 'frozen' ? t('system.credits.accountFrozen') : t('system.credits.accountActive')
}

function getAccountTypeLabel(type: string, t: TFunction) {
  return type === 'tenant' ? t('system.personal.tenantAccount') : t('system.personal.userAccount')
}

function getTransactionTypeLabel(type: string, t: TFunction) {
  switch (type) {
    case 'recharge':
      return t('system.credits.typeRecharge')
    case 'consume':
      return t('system.credits.typeConsume')
    case 'refund':
      return t('system.credits.typeRefund')
    case 'bonus':
      return t('system.credits.typeBonus')
    case 'adjust':
      return t('system.credits.typeAdjust')
    case 'transfer':
      return t('system.credits.typeTransfer')
    default:
      return type
  }
}

function getDirectionLabel(direction: string, t: TFunction) {
  return direction === 'in' ? t('system.credits.directionIn') : t('system.credits.directionOut')
}

export default function MyCreditsPage() {
  const t = useT()
  const { session } = useAuth()
  const [account, setAccount] = useState<CreditAccount | null>(null)
  const [transactions, setTransactions] = useState<PageResponse<CreditTransaction> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  const transactionRows = useMemo(() => transactions?.list || [], [transactions?.list])
  const currentPage = transactions?.currentPage ?? page
  const pageSize = transactions?.pageSize ?? PAGE_SIZE
  const total = transactions?.total ?? 0

  const load = useCallback(async () => {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const [a, tx] = await Promise.all([
        apiFetch<CreditAccount>('/api/v1/credits/my/account', { session }),
        apiFetch<PageResponse<CreditTransaction>>(`/api/v1/credits/my/transactions?currentPage=${page}&pageSize=${PAGE_SIZE}&sortBy=created_at&sortOrder=desc`, {
          session,
        }),
      ])
      setAccount(a)
      setTransactions(tx)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('system.common.loadFailed'))
      setAccount(null)
      setTransactions(null)
    } finally {
      setLoading(false)
    }
  }, [page, session, t])

  const transactionDescription = useMemo(() => {
    const shareCount = transactionRows.filter((tx) => {
      const extra = tx.extra
      if (!extra || typeof extra !== 'object') return false
      return Boolean(extra.public_share_id || extra.public_share_group_id || extra.publicShareId || extra.publicShareGroupId)
    }).length
    return shareCount > 0
      ? t('system.personal.creditTransactionShareDescription').replace('{n}', String(shareCount))
      : t('system.personal.creditTransactionDescription')
  }, [transactionRows, t])

  useEffect(() => {
    void load()
  }, [load])

  if (!session) return null

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>{t('system.personal.creditsTitle')}</CardTitle>
          <CardDescription>{t('system.personal.creditsDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={load} disabled={loading}>
              {t('common.refresh')}
            </Button>
          </div>
          {error ? <div className="text-sm text-destructive">{error}</div> : null}
          {account ? (
            <div className="grid gap-2 rounded-md border p-3 md:grid-cols-2">
              <div>
                {t('system.credits.balance')}: <span className="font-medium">{account.balance}</span>
              </div>
              <div>
                {t('common.status')}: <span className="font-medium">{getAccountStatusLabel(account.status, t)}</span>
              </div>
              <div>{t('system.credits.totalEarned')}: {account.totalEarned}</div>
              <div>{t('system.credits.totalSpent')}: {account.totalSpent}</div>
              <div className="md:col-span-2 text-xs text-muted-foreground">
                {t('system.personal.accountMeta')
                  .replace('{type}', getAccountTypeLabel(account.accountType, t))
                  .replace('{time}', account.createdAt ? new Date(account.createdAt).toLocaleString() : '-')}
              </div>
            </div>
          ) : (
            <div className="text-muted-foreground">{t('system.personal.noCreditAccount')}</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('system.credits.tabTransactions')}</CardTitle>
          <CardDescription>{transactionDescription}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[160px]">{t('system.common.time')}</TableHead>
                  <TableHead>{t('system.common.type')}</TableHead>
                  <TableHead>{t('system.credits.direction')}</TableHead>
                  <TableHead>{t('system.credits.amountColumn')}</TableHead>
                  <TableHead>{t('system.credits.balance')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('system.common.remark')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transactionRows.map((tx) => {
                  const extra = tx.extra
                  const shareUsageLabel =
                    extra && typeof extra === 'object'
                      ? extra.public_share_group_id || extra.publicShareGroupId
                        ? t('system.personal.shareGroupUsage')
                        : extra.public_share_id || extra.publicShareId
                          ? t('system.personal.shareUsage')
                          : ''
                      : ''
                  const remark = shareUsageLabel ? `${tx.remark || t('system.personal.appCallCost')} · ${shareUsageLabel}` : tx.remark || '-'

                  return (
                    <TableRow key={tx.id}>
                      <TableCell>{tx.createdAt ? new Date(tx.createdAt).toLocaleString() : ''}</TableCell>
                      <TableCell>{getTransactionTypeLabel(tx.transactionType, t)}</TableCell>
                      <TableCell>{getDirectionLabel(tx.direction, t)}</TableCell>
                      <TableCell>{tx.amount}</TableCell>
                      <TableCell>{tx.balanceAfter}</TableCell>
                      <TableCell className="hidden md:table-cell">{remark}</TableCell>
                    </TableRow>
                  )
                })}
                {!loading && transactionRows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="py-6 text-center text-muted-foreground">
                      {t('system.credits.noTransactions')}
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>
          <div className="mt-4">
            <SimplePagination total={total} currentPage={currentPage} pageSize={pageSize} disabled={loading} onChange={setPage} />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
