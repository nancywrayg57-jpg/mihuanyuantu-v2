'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

import { SimplePagination } from '@/components/list/simple-pagination'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CreditPricingPanel } from '@/components/credits/credit-pricing-panel'
import { isFeatureAvailable } from '@/lib/feature-switches'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, apiFetch } from '@/lib/api'
import { hasAnyPermission } from '@/lib/auth'
import { useT } from '@/lib/i18n'
import { parseIdList } from '@/lib/parsers'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'

type BulkRechargeFailure = {
  userId: number
  reason: string
}

type BulkRechargeResponse = {
  requested: number
  succeeded: number
  failed: number
  failures: BulkRechargeFailure[]
}

type CreditStats = {
  totalUsers: string | number
  initializedUserAccounts: string | number
  activeAccounts: string | number
  frozenAccounts: string | number
  totalUserBalance: string
  tenantBalance: string
  totalTransactions: string | number
}

type CreditUserOption = {
  id: number
  username: string
  nickname?: string | null
  label: string
  teamNames?: string[]
}

type CreditTeamOption = {
  id: number
  name: string
  code?: string | null
  label: string
}

type CreditUserBalance = {
  userId: number
  username: string
  nickname?: string | null
  displayName: string
  email?: string | null
  phone?: string | null
  userStatus: number
  teamNames: string[]
  accountId?: number | null
  hasAccount: boolean
  accountStatus: string
  balance: string
  totalEarned: string
  totalSpent: string
  createdAt?: string | null
  updatedAt?: string | null
}

type CreditTransaction = {
  id: number
  accountId: number
  transactionType: string
  amount: string
  direction: 'in' | 'out'
  balanceAfter: string
  remark?: string | null
  accountUserId?: number | null
  accountUsername?: string | null
  accountNickname?: string | null
  accountDisplayName?: string | null
  operatorDisplayName?: string | null
  createdAt?: string | null
}

type PageResponse<T> = {
  list: T[]
  total: number
  pageSize: number
  currentPage: number
}

const PAGE_SIZE = 20
const OPTION_LIMIT = 50
type TFunction = ReturnType<typeof useT>

function getErrorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : err instanceof Error ? err.message : fallback
}

function formatDateTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : '-'
}

function getUserStatusLabel(status: number | null | undefined, t: TFunction) {
  switch (Number(status)) {
    case 0:
      return t('common.disabled')
    case 1:
      return t('system.user.statusNormal')
    case 2:
      return t('system.user.statusPending')
    case 3:
      return t('system.user.statusRejected')
    default:
      return '-'
  }
}

function getAccountStatusLabel(status: string | null | undefined, t: TFunction) {
  switch (String(status || '').trim().toLowerCase()) {
    case 'active':
      return t('system.credits.accountActive')
    case 'frozen':
      return t('system.credits.accountFrozen')
    case 'uninitialized':
      return t('system.credits.accountUninitialized')
    default:
      return status || '-'
  }
}

function getTransactionTypeLabel(type: string | null | undefined, t: TFunction) {
  switch (String(type || '').trim().toLowerCase()) {
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
      return type || '-'
  }
}

function getTransactionDirectionLabel(direction: string | null | undefined, t: TFunction) {
  switch (String(direction || '').trim().toLowerCase()) {
    case 'in':
      return t('system.credits.directionIn')
    case 'out':
      return t('system.credits.directionOut')
    default:
      return direction || '-'
  }
}

export default function CreditsPage() {
  const t = useT()
  const { session } = useAuth()
  const { targetTenant, targetTenantId, featureCatalog } = useTenant()

  const canRead = useMemo(
    () => hasAnyPermission(session, ['credits:read', 'credits:account:list', 'credits:transaction:list']),
    [session],
  )
  const canRecharge = useMemo(() => hasAnyPermission(session, ['credits:recharge']), [session])
  const canEditPricing = useMemo(() => hasAnyPermission(session, ['credits:pricing:update']), [session])
  const pricingRequestOpts = useMemo(() => ({ session, tenantId: targetTenantId }), [session, targetTenantId])
  const reconciliationAvailable = isFeatureAvailable(featureCatalog, 'credits.pricing_reconciliation')
  const canAccessPage = canRead || canRecharge

  const requestOptions = useMemo(
    () => ({
      session,
      tenantId: targetTenantId,
    }),
    [session, targetTenantId],
  )

  const [activeTab, setActiveTab] = useState<'recharge' | 'balances' | 'transactions' | 'pricing'>(
    canRecharge ? 'recharge' : 'balances',
  )

  const [stats, setStats] = useState<CreditStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [statsError, setStatsError] = useState<string | null>(null)

  const [userOptions, setUserOptions] = useState<CreditUserOption[]>([])
  const [teamOptions, setTeamOptions] = useState<CreditTeamOption[]>([])
  const [optionsLoading, setOptionsLoading] = useState(false)
  const [optionsError, setOptionsError] = useState<string | null>(null)

  const [amount, setAmount] = useState('10')
  const [remark, setRemark] = useState('')
  const [userIdsRaw, setUserIdsRaw] = useState('')
  const [teamIdsRaw, setTeamIdsRaw] = useState('')
  const [includeChildren, setIncludeChildren] = useState(true)
  const [rechargeLoading, setRechargeLoading] = useState(false)
  const [rechargeResult, setRechargeResult] = useState<BulkRechargeResponse | null>(null)
  const [rechargeError, setRechargeError] = useState<string | null>(null)

  const [balancePage, setBalancePage] = useState(1)
  const [balanceKeywordInput, setBalanceKeywordInput] = useState('')
  const [balanceKeyword, setBalanceKeyword] = useState('')
  const [balanceUserStatus, setBalanceUserStatus] = useState('all')
  const [balanceAccountStatus, setBalanceAccountStatus] = useState('all')
  const [balanceTeamId, setBalanceTeamId] = useState('all')
  const [balanceData, setBalanceData] = useState<PageResponse<CreditUserBalance> | null>(null)
  const [balanceLoading, setBalanceLoading] = useState(false)
  const [balanceError, setBalanceError] = useState<string | null>(null)

  const [transactionPage, setTransactionPage] = useState(1)
  const [transactionUserId, setTransactionUserId] = useState('all')
  const [transactionType, setTransactionType] = useState('all')
  const [transactionDirection, setTransactionDirection] = useState('all')
  const [transactionData, setTransactionData] = useState<PageResponse<CreditTransaction> | null>(null)
  const [transactionLoading, setTransactionLoading] = useState(false)
  const [transactionError, setTransactionError] = useState<string | null>(null)

  useEffect(() => {
    if (canRecharge) {
      setActiveTab((current) => (current === 'balances' || current === 'transactions' || current === 'pricing' ? current : 'recharge'))
    } else if (canRead) {
      setActiveTab((current) => (current === 'transactions' || current === 'pricing' ? current : 'balances'))
    }
  }, [canRead, canRecharge])

  const loadOptions = useCallback(async () => {
    if (!session || !canAccessPage) return
    setOptionsLoading(true)
    setOptionsError(null)
    try {
      const [users, teams] = await Promise.all([
        apiFetch<CreditUserOption[]>(`/api/v1/credits/options/users?limit=${OPTION_LIMIT}`, requestOptions),
        apiFetch<CreditTeamOption[]>(`/api/v1/credits/options/teams?limit=${OPTION_LIMIT}`, requestOptions),
      ])
      setUserOptions(users)
      setTeamOptions(teams)
    } catch (err) {
      setOptionsError(getErrorMessage(err, t('system.credits.loadOptionsFailed')))
    } finally {
      setOptionsLoading(false)
    }
  }, [canAccessPage, requestOptions, session, t])

  const loadStats = useCallback(async () => {
    if (!session || !canRead) return
    setStatsLoading(true)
    setStatsError(null)
    try {
      const data = await apiFetch<CreditStats>('/api/v1/credits/stats', requestOptions)
      setStats(data)
    } catch (err) {
      setStats(null)
      setStatsError(getErrorMessage(err, t('system.credits.loadStatsFailed')))
    } finally {
      setStatsLoading(false)
    }
  }, [canRead, requestOptions, session, t])

  const loadBalances = useCallback(async () => {
    if (!session || !canRead) return
    setBalanceLoading(true)
    setBalanceError(null)
    try {
      const params = new URLSearchParams({
        currentPage: String(balancePage),
        pageSize: String(PAGE_SIZE),
      })
      if (balanceKeyword.trim()) params.set('keyword', balanceKeyword.trim())
      if (balanceUserStatus !== 'all') params.set('userStatus', balanceUserStatus)
      if (balanceAccountStatus !== 'all') params.set('accountStatus', balanceAccountStatus)
      if (balanceTeamId !== 'all') params.set('teamId', balanceTeamId)
      const data = await apiFetch<PageResponse<CreditUserBalance>>(
        `/api/v1/credits/user-balances?${params.toString()}`,
        requestOptions,
      )
      setBalanceData(data)
    } catch (err) {
      setBalanceData(null)
      setBalanceError(getErrorMessage(err, t('system.credits.loadBalancesFailed')))
    } finally {
      setBalanceLoading(false)
    }
  }, [balanceAccountStatus, balanceKeyword, balancePage, balanceTeamId, balanceUserStatus, canRead, requestOptions, session, t])

  const loadTransactions = useCallback(async () => {
    if (!session || !canRead) return
    setTransactionLoading(true)
    setTransactionError(null)
    try {
      const params = new URLSearchParams({
        currentPage: String(transactionPage),
        pageSize: String(PAGE_SIZE),
      })
      if (transactionUserId !== 'all') params.set('userId', transactionUserId)
      if (transactionType !== 'all') params.set('transactionType', transactionType)
      if (transactionDirection !== 'all') params.set('direction', transactionDirection)
      const data = await apiFetch<PageResponse<CreditTransaction>>(
        `/api/v1/credits/transactions?${params.toString()}`,
        requestOptions,
      )
      setTransactionData(data)
    } catch (err) {
      setTransactionData(null)
      setTransactionError(getErrorMessage(err, t('system.credits.loadTransactionsFailed')))
    } finally {
      setTransactionLoading(false)
    }
  }, [canRead, requestOptions, session, t, transactionDirection, transactionPage, transactionType, transactionUserId])

  useEffect(() => {
    if (!session || !canAccessPage) return
    void loadOptions()
  }, [canAccessPage, loadOptions, session])

  useEffect(() => {
    if (!session || !canRead) return
    void loadStats()
  }, [canRead, loadStats, session])

  useEffect(() => {
    if (!session || !canRead) return
    void loadBalances()
  }, [canRead, loadBalances, session])

  useEffect(() => {
    if (!session || !canRead) return
    void loadTransactions()
  }, [canRead, loadTransactions, session])

  if (!canAccessPage) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t('system.credits.title')}</CardTitle>
          <CardDescription>{t('system.credits.noPermission')}</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const statCards = [
    { label: t('system.credits.statUsers'), value: String(stats?.totalUsers ?? '-') },
    { label: t('system.credits.statInitializedAccounts'), value: String(stats?.initializedUserAccounts ?? '-') },
    { label: t('system.credits.statActiveAccounts'), value: String(stats?.activeAccounts ?? '-') },
    { label: t('system.credits.statFrozenAccounts'), value: String(stats?.frozenAccounts ?? '-') },
    { label: t('system.credits.statUserBalanceTotal'), value: stats?.totalUserBalance ?? '-' },
    { label: t('system.credits.statTenantBalance'), value: stats?.tenantBalance ?? '-' },
    { label: t('system.credits.statTransactionTotal'), value: String(stats?.totalTransactions ?? '-') },
  ]

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader className="gap-2">
          <CardTitle>{t('system.credits.centerTitle')}</CardTitle>
          <CardDescription>
            {t('system.credits.centerDescription')}
            {session?.isSuperuser && targetTenant ? (
              <span className="ml-2 text-xs text-muted-foreground">
                {t('system.common.targetTenant').replace('{name}', targetTenant.name).replace('{code}', targetTenant.code)}
              </span>
            ) : null}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {canRead ? (
            <>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={() => void loadStats()} disabled={statsLoading}>
                  {statsLoading ? t('system.common.refreshing') : t('system.credits.refreshStats')}
                </Button>
                <Button variant="outline" onClick={() => void loadOptions()} disabled={optionsLoading}>
                  {optionsLoading ? t('common.loading') : t('system.credits.refreshOptions')}
                </Button>
              </div>
              {statsError ? <div className="text-sm text-destructive">{statsError}</div> : null}
              {optionsError ? <div className="text-sm text-destructive">{optionsError}</div> : null}
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {statCards.map((item) => (
                  <div key={item.label} className="rounded-xl border px-4 py-3">
                    <div className="text-xs text-muted-foreground">{item.label}</div>
                    <div className="mt-1 text-lg font-semibold">{item.value}</div>
                  </div>
                ))}
              </div>
            </>
          ) : null}

          <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as typeof activeTab)} className="grid gap-4">
            <TabsList className="flex h-auto w-fit flex-wrap gap-1">
              {canRecharge ? <TabsTrigger value="recharge">{t('system.credits.tabRecharge')}</TabsTrigger> : null}
              {canRead ? <TabsTrigger value="balances">{t('system.credits.tabBalances')}</TabsTrigger> : null}
              {canRead ? <TabsTrigger value="transactions">{t('system.credits.tabTransactions')}</TabsTrigger> : null}
              {canRead ? <TabsTrigger value="pricing">{t('app.system.credits.pricing.tab')}</TabsTrigger> : null}
            </TabsList>

            {canRecharge ? (
              <TabsContent value="recharge" className="mt-0">
                <div className="grid gap-4">
                  <div className="grid gap-4 rounded-xl border p-4 xl:grid-cols-[180px_1fr]">
                    <div className="grid gap-2">
                      <Label htmlFor="amount">{t('system.credits.amount')}</Label>
                      <Input id="amount" value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="remark">{t('system.common.remark')}</Label>
                      <Input id="remark" value={remark} onChange={(e) => setRemark(e.target.value)} />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="user-ids">{t('system.credits.userIdList')}</Label>
                      <Textarea
                        id="user-ids"
                        value={userIdsRaw}
                        onChange={(e) => setUserIdsRaw(e.target.value)}
                        placeholder={t('system.common.exampleIds').replace('{ids}', '1,2,3')}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="team-ids">{t('system.credits.teamIdList')}</Label>
                      <Textarea
                        id="team-ids"
                        value={teamIdsRaw}
                        onChange={(e) => setTeamIdsRaw(e.target.value)}
                        placeholder={t('system.common.exampleIds').replace('{ids}', '10,11')}
                      />
                    </div>
                    <div className="xl:col-span-2">
                      <label className="flex items-center gap-2 text-sm">
                        <Checkbox checked={includeChildren} onCheckedChange={(value) => setIncludeChildren(Boolean(value))} />
                        {t('system.credits.includeChildren')}
                      </label>
                    </div>
                    <div className="xl:col-span-2 text-xs text-muted-foreground">
                      {t('system.credits.optionsLoadedHint')
                        .replace('{users}', String(userOptions.length))
                        .replace('{teams}', String(teamOptions.length))}
                    </div>
                    <div className="xl:col-span-2 flex flex-wrap items-center gap-2">
                      <Button
                        disabled={rechargeLoading}
                        onClick={async () => {
                          if (!session) return
                          setRechargeLoading(true)
                          setRechargeError(null)
                          setRechargeResult(null)
                          try {
                            const userIds = parseIdList(userIdsRaw)
                            const teamIds = parseIdList(teamIdsRaw)
                            const response = await apiFetch<BulkRechargeResponse>('/api/v1/credits/recharge/bulk', {
                              ...requestOptions,
                              method: 'POST',
                              body: JSON.stringify({
                                amount,
                                remark: remark || undefined,
                                userIds,
                                teamIds,
                                includeChildren,
                              }),
                            })
                            setRechargeResult(response)
                            await Promise.all([loadStats(), loadBalances(), loadTransactions()])
                          } catch (err) {
                            setRechargeError(getErrorMessage(err, t('system.credits.rechargeFailed')))
                          } finally {
                            setRechargeLoading(false)
                          }
                        }}
                      >
                        {rechargeLoading ? t('system.common.executing') : t('system.credits.rechargeButton')}
                      </Button>
                      <Button
                        variant="outline"
                        disabled={rechargeLoading}
                        onClick={() => {
                          setUserIdsRaw('')
                          setTeamIdsRaw('')
                          setRemark('')
                          setRechargeError(null)
                          setRechargeResult(null)
                        }}
                      >
                        {t('system.common.clear')}
                      </Button>
                    </div>
                  </div>

                  {rechargeError ? <div className="text-sm text-destructive">{rechargeError}</div> : null}
                  {rechargeResult ? (
                    <div className="rounded-xl border p-4 text-sm">
                      <div>
                        {t('system.credits.resultSummary')
                          .replace('{requested}', String(rechargeResult.requested))
                          .replace('{succeeded}', String(rechargeResult.succeeded))
                          .replace('{failed}', String(rechargeResult.failed))}
                      </div>
                      {rechargeResult.failures.length > 0 ? (
                        <div className="mt-2 grid gap-1 text-xs text-muted-foreground">
                          {rechargeResult.failures.slice(0, 20).map((failure) => (
                            <div key={`${failure.userId}-${failure.reason}`}>
                              {t('system.credits.failureUser')
                                .replace('{id}', String(failure.userId))
                                .replace('{reason}', failure.reason)}
                            </div>
                          ))}
                          {rechargeResult.failures.length > 20 ? <div>{t('system.credits.failureLimit')}</div> : null}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </TabsContent>
            ) : null}

            {canRead ? (
              <TabsContent value="balances" className="mt-0">
                <div className="grid gap-4">
                  <div className="grid gap-3 rounded-xl border p-4 xl:grid-cols-[minmax(0,220px)_180px_180px_220px_auto]">
                    <div className="grid gap-2">
                      <Label htmlFor="balance-keyword">{t('common.search')}</Label>
                      <Input
                        id="balance-keyword"
                        value={balanceKeywordInput}
                        onChange={(e) => setBalanceKeywordInput(e.target.value)}
                        placeholder={t('system.credits.balanceSearchPlaceholder')}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label>{t('system.credits.userStatus')}</Label>
                      <Select
                        value={balanceUserStatus}
                        onValueChange={(value) => {
                          setBalanceUserStatus(value)
                          setBalancePage(1)
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">{t('common.all')}</SelectItem>
                          <SelectItem value="1">{t('system.user.statusNormal')}</SelectItem>
                          <SelectItem value="0">{t('common.disabled')}</SelectItem>
                          <SelectItem value="2">{t('system.user.statusPending')}</SelectItem>
                          <SelectItem value="3">{t('system.user.statusRejected')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label>{t('system.credits.accountStatus')}</Label>
                      <Select
                        value={balanceAccountStatus}
                        onValueChange={(value) => {
                          setBalanceAccountStatus(value)
                          setBalancePage(1)
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">{t('common.all')}</SelectItem>
                          <SelectItem value="active">{t('system.credits.accountActive')}</SelectItem>
                          <SelectItem value="frozen">{t('system.credits.accountFrozen')}</SelectItem>
                          <SelectItem value="uninitialized">{t('system.credits.accountUninitialized')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label>{t('system.common.team')}</Label>
                      <Select
                        value={balanceTeamId}
                        onValueChange={(value) => {
                          setBalanceTeamId(value)
                          setBalancePage(1)
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder={t('system.credits.allTeams')} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">{t('system.credits.allTeams')}</SelectItem>
                          {teamOptions.map((team) => (
                            <SelectItem key={team.id} value={String(team.id)}>
                              {team.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-end gap-2">
                      <Button
                        onClick={() => {
                          setBalanceKeyword(balanceKeywordInput.trim())
                          setBalancePage(1)
                        }}
                      >
                        {t('system.credits.applyFilters')}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setBalanceKeywordInput('')
                          setBalanceKeyword('')
                          setBalanceUserStatus('all')
                          setBalanceAccountStatus('all')
                          setBalanceTeamId('all')
                          setBalancePage(1)
                        }}
                      >
                        {t('common.reset')}
                      </Button>
                    </div>
                  </div>

                  {balanceError ? <div className="text-sm text-destructive">{balanceError}</div> : null}

                  <div className="overflow-x-auto rounded-xl border">
                    <Table className="min-w-[920px]">
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('system.common.user')}</TableHead>
                          <TableHead>{t('system.common.team')}</TableHead>
                          <TableHead>{t('system.credits.userStatus')}</TableHead>
                          <TableHead>{t('system.credits.accountStatus')}</TableHead>
                          <TableHead>{t('system.credits.balance')}</TableHead>
                          <TableHead>{t('system.credits.totalEarned')}</TableHead>
                          <TableHead>{t('system.credits.totalSpent')}</TableHead>
                          <TableHead>{t('common.updatedAt')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {(balanceData?.list || []).map((row) => (
                          <TableRow key={row.userId}>
                            <TableCell>
                              <div className="font-medium">{row.displayName || row.username}</div>
                              <div className="text-xs text-muted-foreground">{row.username}</div>
                            </TableCell>
                            <TableCell>{row.teamNames.length > 0 ? row.teamNames.join('、') : '-'}</TableCell>
                            <TableCell>{getUserStatusLabel(row.userStatus, t)}</TableCell>
                            <TableCell>{getAccountStatusLabel(row.accountStatus, t)}</TableCell>
                            <TableCell>{row.balance}</TableCell>
                            <TableCell>{row.totalEarned}</TableCell>
                            <TableCell>{row.totalSpent}</TableCell>
                            <TableCell>{formatDateTime(row.updatedAt || row.createdAt)}</TableCell>
                          </TableRow>
                        ))}
                        {!balanceLoading && (balanceData?.list || []).length === 0 ? (
                          <TableRow>
                            <TableCell colSpan={8} className="py-8 text-center text-muted-foreground">
                              {t('common.empty')}
                            </TableCell>
                          </TableRow>
                        ) : null}
                      </TableBody>
                    </Table>
                  </div>

                  <SimplePagination
                    total={balanceData?.total || 0}
                    currentPage={balanceData?.currentPage || balancePage}
                    pageSize={balanceData?.pageSize || PAGE_SIZE}
                    disabled={balanceLoading}
                    onChange={setBalancePage}
                  />
                </div>
              </TabsContent>
            ) : null}

            {canRead ? (
              <TabsContent value="transactions" className="mt-0">
                <div className="grid gap-4">
                  <div className="grid gap-3 rounded-xl border p-4 xl:grid-cols-[240px_180px_180px_auto]">
                    <div className="grid gap-2">
                      <Label>{t('system.common.user')}</Label>
                      <Select
                        value={transactionUserId}
                        onValueChange={(value) => {
                          setTransactionUserId(value)
                          setTransactionPage(1)
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder={t('system.credits.allUsers')} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">{t('system.credits.allUsers')}</SelectItem>
                          {userOptions.map((user) => (
                            <SelectItem key={user.id} value={String(user.id)}>
                              {user.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label>{t('system.credits.transactionType')}</Label>
                      <Select
                        value={transactionType}
                        onValueChange={(value) => {
                          setTransactionType(value)
                          setTransactionPage(1)
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">{t('system.credits.allTypes')}</SelectItem>
                          <SelectItem value="recharge">{t('system.credits.typeRecharge')}</SelectItem>
                          <SelectItem value="consume">{t('system.credits.typeConsume')}</SelectItem>
                          <SelectItem value="refund">{t('system.credits.typeRefund')}</SelectItem>
                          <SelectItem value="bonus">{t('system.credits.typeBonus')}</SelectItem>
                          <SelectItem value="adjust">{t('system.credits.typeAdjust')}</SelectItem>
                          <SelectItem value="transfer">{t('system.credits.typeTransfer')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label>{t('system.credits.direction')}</Label>
                      <Select
                        value={transactionDirection}
                        onValueChange={(value) => {
                          setTransactionDirection(value)
                          setTransactionPage(1)
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">{t('system.credits.allDirections')}</SelectItem>
                          <SelectItem value="in">{t('system.credits.directionIn')}</SelectItem>
                          <SelectItem value="out">{t('system.credits.directionOut')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-end gap-2">
                      <Button variant="outline" onClick={() => void loadTransactions()}>
                        {t('system.credits.refreshCurrentFilters')}
                      </Button>
                    </div>
                  </div>

                  {transactionError ? <div className="text-sm text-destructive">{transactionError}</div> : null}

                  <div className="overflow-x-auto rounded-xl border">
                    <Table className="min-w-[980px]">
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('system.common.time')}</TableHead>
                          <TableHead>{t('system.common.user')}</TableHead>
                          <TableHead>{t('system.common.type')}</TableHead>
                          <TableHead>{t('system.credits.direction')}</TableHead>
                          <TableHead>{t('system.credits.amountColumn')}</TableHead>
                          <TableHead>{t('system.credits.balance')}</TableHead>
                          <TableHead>{t('system.common.remark')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {(transactionData?.list || []).map((row) => (
                          <TableRow key={row.id}>
                            <TableCell>{formatDateTime(row.createdAt)}</TableCell>
                            <TableCell>{row.accountDisplayName || row.accountNickname || row.accountUsername || '-'}</TableCell>
                            <TableCell>{getTransactionTypeLabel(row.transactionType, t)}</TableCell>
                            <TableCell>{getTransactionDirectionLabel(row.direction, t)}</TableCell>
                            <TableCell>{row.amount}</TableCell>
                            <TableCell>{row.balanceAfter}</TableCell>
                            <TableCell className="max-w-[320px] truncate">{row.remark || '-'}</TableCell>
                          </TableRow>
                        ))}
                        {!transactionLoading && (transactionData?.list || []).length === 0 ? (
                          <TableRow>
                            <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
                              {t('system.credits.noTransactions')}
                            </TableCell>
                          </TableRow>
                        ) : null}
                      </TableBody>
                    </Table>
                  </div>

                  <SimplePagination
                    total={transactionData?.total || 0}
                    currentPage={transactionData?.currentPage || transactionPage}
                    pageSize={transactionData?.pageSize || PAGE_SIZE}
                    disabled={transactionLoading}
                    onChange={setTransactionPage}
                  />
                </div>
              </TabsContent>
            ) : null}
            {canRead ? (
              <TabsContent value="pricing" className="mt-0">
                <CreditPricingPanel requestOpts={pricingRequestOpts} canEdit={canEditPricing} reconciliationAvailable={reconciliationAvailable} />
              </TabsContent>
            ) : null}
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}
