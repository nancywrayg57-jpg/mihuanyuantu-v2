import { apiFetch } from '@/lib/api'
import type { Session } from '@/lib/auth'

type ApiOpts = {
  session?: Session | null
  tenantId?: number | null
}

export type CreditsPaged<T> = {
  list: T[]
  total: number
  currentPage: number
  pageSize: number
}

export type CreditStats = {
  totalUsers: number
  initializedUserAccounts: number
  activeAccounts: number
  frozenAccounts: number
  totalUserBalance: string
  tenantBalance: string
  totalTransactions: number
}

export type CreditAccount = {
  id: number
  tenantId?: number
  userId?: number | null
  accountType: 'tenant' | 'user'
  balance: string
  totalEarned: string
  totalSpent: string
  status: 'active' | 'frozen'
  username?: string | null
  nickname?: string | null
  displayName?: string | null
  email?: string | null
  phone?: string | null
  teamNames?: string[]
  createdAt?: string | null
  updatedAt?: string | null
}

export type CreditUserOption = {
  id: number
  username: string
  nickname?: string | null
  label: string
  email?: string | null
  phone?: string | null
  status: number
  teamNames: string[]
}

export type CreditTeamOption = {
  id: number
  name: string
  code?: string | null
  label: string
  status: number
  parentId?: number | null
}

export type CreditUserBalance = {
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

export type CreditTransaction = {
  id: number
  accountId: number
  transactionType: string
  amount: string
  direction: 'in' | 'out'
  balanceBefore: string
  balanceAfter: string
  remark?: string | null
  operatorId?: number | null
  accountType?: string | null
  accountUserId?: number | null
  accountUsername?: string | null
  accountNickname?: string | null
  accountDisplayName?: string | null
  operatorUsername?: string | null
  operatorNickname?: string | null
  operatorDisplayName?: string | null
  extra?: Record<string, unknown>
  createdAt?: string | null
}

export type CreditBulkRechargeFailure = {
  userId: number
  reason: string
}

export type CreditBulkRechargeResponse = {
  requested: number
  succeeded: number
  failed: number
  failures: CreditBulkRechargeFailure[]
}

function buildQuery(params: Record<string, string | number | null | undefined>) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

export async function getCreditStats(opts?: ApiOpts) {
  return apiFetch<CreditStats>('/api/v1/credits/stats', { ...opts })
}

export async function getMyCreditAccount(opts?: ApiOpts) {
  return apiFetch<CreditAccount>('/api/v1/credits/my/account', { ...opts })
}

export async function listCreditUserOptions(
  query: { keyword?: string; limit?: number } = {},
  opts?: ApiOpts,
) {
  return apiFetch<CreditUserOption[]>(
    `/api/v1/credits/options/users${buildQuery({
      keyword: query.keyword || undefined,
      limit: query.limit ?? 20,
    })}`,
    { ...opts },
  )
}

export async function listCreditTeamOptions(
  query: { keyword?: string; limit?: number } = {},
  opts?: ApiOpts,
) {
  return apiFetch<CreditTeamOption[]>(
    `/api/v1/credits/options/teams${buildQuery({
      keyword: query.keyword || undefined,
      limit: query.limit ?? 20,
    })}`,
    { ...opts },
  )
}

export async function listCreditUserBalances(
  query: {
    page?: number
    pageSize?: number
    keyword?: string
    userStatus?: number | null
    accountStatus?: string | null
    teamId?: number | null
  } = {},
  opts?: ApiOpts,
) {
  return apiFetch<CreditsPaged<CreditUserBalance>>(
    `/api/v1/credits/user-balances${buildQuery({
      currentPage: query.page ?? 1,
      pageSize: query.pageSize ?? 20,
      keyword: query.keyword || undefined,
      userStatus: query.userStatus ?? undefined,
      accountStatus: query.accountStatus || undefined,
      teamId: query.teamId ?? undefined,
    })}`,
    { ...opts },
  )
}

export async function listCreditTransactions(
  query: {
    page?: number
    pageSize?: number
    userId?: number | null
    transactionType?: string | null
    direction?: string | null
  } = {},
  opts?: ApiOpts,
) {
  return apiFetch<CreditsPaged<CreditTransaction>>(
    `/api/v1/credits/transactions${buildQuery({
      currentPage: query.page ?? 1,
      pageSize: query.pageSize ?? 20,
      userId: query.userId ?? undefined,
      transactionType: query.transactionType || undefined,
      direction: query.direction || undefined,
      sortBy: 'created_at',
      sortOrder: 'desc',
    })}`,
    { ...opts },
  )
}

export async function listMyCreditTransactions(
  query: {
    page?: number
    pageSize?: number
    transactionType?: string | null
    direction?: string | null
  } = {},
  opts?: ApiOpts,
) {
  return apiFetch<CreditsPaged<CreditTransaction>>(
    `/api/v1/credits/my/transactions${buildQuery({
      currentPage: query.page ?? 1,
      pageSize: query.pageSize ?? 20,
      transactionType: query.transactionType || undefined,
      direction: query.direction || undefined,
      sortBy: 'created_at',
      sortOrder: 'desc',
    })}`,
    { ...opts },
  )
}

export async function bulkRechargeCredits(
  payload: {
    amount: string
    remark?: string
    userIds?: number[]
    teamIds?: number[]
    includeChildren?: boolean
  },
  opts?: ApiOpts,
) {
  return apiFetch<CreditBulkRechargeResponse>('/api/v1/credits/recharge/bulk', {
    method: 'POST',
    body: JSON.stringify(payload),
    ...opts,
  })
}

// ---------------------------------------------------------------------------
// 统一积分策略：计价模式 + 费率（平台 pricebook + 租户覆盖）
// ---------------------------------------------------------------------------
export type CreditPricingMode = 'legacy' | 'shadow' | 'unified'

export type CreditRateSchedule = {
  timezone: string
  defaultBand?: string
  source?: string
  sourceUrl?: string
  effectiveAt?: string
  verifiedAt?: string
  remark?: string
  bands: Array<{
    key: string
    multiplier: string
    weekdays: number[]
    windows: Array<{ start: string; end: string }>
    priority?: number
  }>
}

export type CreditPriceItemView = {
  id: number | null
  tenantId: number | null
  scope: 'platform' | 'tenant'
  itemType: string
  matchKey: string
  inputPointsPer1k: string
  outputPointsPer1k: string
  cachedPointsPer1k: string | null
  cacheWritePointsPer1k?: string | null
  pointsPerUnit: string
  unitDivisor: string | null
  priority: number
  isActive: boolean
  remark: string
  rateSchedule: CreditRateSchedule | null
  updatedAt: string | null
}

export type CreditPricingOverview = {
  marginPercent?: string
  cachedBilling?: 'passthrough' | 'full_price' | string
  pricebookBaseMarginPercent?: number
  pricingMode: CreditPricingMode
  availableModes: CreditPricingMode[]
  pricebookVersion: string
  itemTypes: string[]
  platformItems: CreditPriceItemView[]
  tenantOverrides: CreditPriceItemView[]
  tenantTimezone: string
  currentTenantTime: string
}

export type CreditPriceItemUpsertPayload = {
  itemType: string
  matchKey: string
  inputPointsPer1k?: string
  outputPointsPer1k?: string
  cachedPointsPer1k?: string | null
  cacheWritePointsPer1k?: string | null
  pointsPerUnit?: string
  unitDivisor?: string | null
  priority?: number
  isActive?: boolean
  remark?: string
  rateSchedule?: CreditRateSchedule | null
}

export async function getCreditPricing(opts?: ApiOpts) {
  return apiFetch<CreditPricingOverview>('/api/v1/credits/pricing', { ...opts })
}

export async function updateCreditPricingMode(pricingMode: CreditPricingMode, opts?: ApiOpts) {
  return apiFetch<CreditPricingOverview>('/api/v1/credits/pricing/mode', {
    ...opts,
    method: 'PUT',
    body: JSON.stringify({ pricingMode }),
  })
}

export async function updateCreditPriceAdjustment(
  payload: { marginPercent?: string; cachedBilling?: 'passthrough' | 'full_price' },
  opts?: ApiOpts,
) {
  return apiFetch<{ marginPercent: string; cachedBilling: string }>('/api/v1/credits/pricing/margin', {
    ...opts,
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function upsertCreditPriceItem(payload: CreditPriceItemUpsertPayload, opts?: ApiOpts) {
  return apiFetch<CreditPriceItemView>('/api/v1/credits/pricing/items', {
    ...opts,
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteCreditPriceItem(itemId: number, opts?: ApiOpts) {
  return apiFetch<{ deleted: boolean; id: number }>(`/api/v1/credits/pricing/items/${itemId}`, {
    ...opts,
    method: 'DELETE',
  })
}

export type CreditPricingReconciliationRow = {
  referenceType: string
  txCount: number
  withBilling: number
  legacyRows: number
  shadowRows: number
  unifiedRows: number
  flatFallbackRows: number
  fallbackRateRows: number
  chargedOut: string
  shadowLegacySum: string
  shadowUnifiedSum: string
  shadowDelta: string
}

export type CreditPricingReconciliation = {
  days: number
  pricebookVersion: string
  rows: CreditPricingReconciliationRow[]
  coverage: {
    txCount: number
    withBilling: number
    billingCoverage: number | null
    usageItems: number
    estimatedItems: number
    emptyModelItems: number
    fallbackRateRows: number
    flatFallbackRows: number
  }
}

export async function getCreditPricingReconciliation(days: number, opts?: ApiOpts) {
  return apiFetch<CreditPricingReconciliation>(`/api/v1/credits/pricing/reconciliation?days=${encodeURIComponent(String(days))}`, { ...opts })
}
