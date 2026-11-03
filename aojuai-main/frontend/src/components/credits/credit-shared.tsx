'use client';
import { translateActive } from '@/lib/i18n/registry'
import type { ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { CreditTransaction } from '@/lib/api/credits';
export const USER_STATUS_LABELS: Record<number, string> = {
    0: translateActive("components.credits.creditShared.copy001"),
    1: translateActive("components.credits.creditShared.copy002"),
    2: translateActive("components.credits.creditShared.copy003"),
    3: translateActive("components.credits.creditShared.copy004"),
};
export const ACCOUNT_STATUS_LABELS: Record<string, string> = {
    active: translateActive("components.credits.creditShared.copy005"),
    frozen: translateActive("components.credits.creditShared.copy006"),
    uninitialized: translateActive("components.credits.creditShared.copy007"),
};
export const TRANSACTION_TYPE_LABELS: Record<string, string> = {
    recharge: translateActive("components.credits.creditShared.copy008"),
    consume: translateActive("components.credits.creditShared.copy009"),
    refund: translateActive("components.credits.creditShared.copy010"),
    transfer: translateActive("components.credits.creditShared.copy011"),
    bonus: translateActive("components.credits.creditShared.copy012"),
    adjust: translateActive("components.credits.creditShared.copy013"),
};
export const TRANSACTION_DIRECTION_LABELS: Record<string, string> = {
    in: translateActive("components.credits.creditShared.copy014"),
    out: translateActive("components.credits.creditShared.copy015"),
};
export function formatCreditDateTime(value?: string | null) {
    if (!value)
        return '-';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime()))
        return '-';
    return parsed.toLocaleString();
}
export function getUserStatusLabel(status: number) {
    return USER_STATUS_LABELS[status] || translateActive("components.credits.creditShared.copy016").replace("{0}", String(status));
}
export function getAccountStatusLabel(status: string) {
    return ACCOUNT_STATUS_LABELS[status] || status;
}
export function getTransactionTypeLabel(type: string) {
    return TRANSACTION_TYPE_LABELS[type] || type;
}
export function getTransactionDirectionLabel(direction: string) {
    return TRANSACTION_DIRECTION_LABELS[direction] || direction;
}
export function getTransactionAmountLabel(item: Pick<CreditTransaction, 'direction' | 'amount'>) {
    return `${item.direction === 'out' ? '-' : '+'}${item.amount}`;
}
export function getCreditUserLabel(item: {
    displayName?: string | null;
    nickname?: string | null;
    username?: string | null;
}) {
    const displayName = item.displayName || item.nickname || item.username || '-';
    if (item.username && displayName !== item.username) {
        return `${displayName}（${item.username}）`;
    }
    return displayName;
}
export function getTeamSummary(teamNames: string[]) {
    if (!teamNames.length)
        return '-';
    if (teamNames.length === 1)
        return teamNames[0];
    return `${teamNames[0]} +${teamNames.length - 1}`;
}
function getShareUsageLabel(extra?: Record<string, unknown>) {
    if (!extra || typeof extra !== 'object')
        return '';
    if (extra.public_share_group_id || extra.publicShareGroupId)
        return translateActive("components.credits.creditShared.copy017");
    if (extra.public_share_id || extra.publicShareId)
        return translateActive("components.credits.creditShared.copy018");
    return '';
}
export function buildCreditBillingSummary(item: Pick<CreditTransaction, 'extra'>) {
  const extra = (item.extra ?? {}) as Record<string, unknown>
  const billing = (extra.billing ?? {}) as Record<string, unknown>
  const usage = (extra.usage ?? {}) as Record<string, unknown>
  const totals = ((billing.totals ?? usage.totals) ?? null) as Record<string, number> | null
  const byModel = ((billing.byModel ?? usage.byModel) ?? null) as Record<string, unknown> | null
  const parts: string[] = []
  if (typeof billing.pricingMode === 'string') parts.push(String(billing.pricingMode))
  if (byModel) parts.push(Object.keys(byModel).join(', '))
  if (totals) {
    const cached = Number(totals.cachedTokens ?? 0)
    parts.push(`${Number(totals.inputTokens ?? 0)}/${Number(totals.outputTokens ?? 0)}${cached ? ` (cached ${cached})` : ''}`)
  }
  const shadow = billing.shadow as Record<string, unknown> | undefined
  if (shadow && typeof shadow.points === 'string') parts.push(`unified≈${shadow.points}`)
  if (billing.basis === 'flat_fallback') parts.push('flat')
  if (billing.fallbackRate === true || (shadow && shadow.fallbackRate === true)) parts.push('fallback-rate')
  return parts.join(' · ')
}

export function buildCreditTransactionRemark(item: Pick<CreditTransaction, 'remark' | 'extra'>) {
    const shareUsageLabel = getShareUsageLabel(item.extra);
    return shareUsageLabel ? `${item.remark || translateActive("components.credits.creditShared.copy019")} · ${shareUsageLabel}` : item.remark || '-';
}
type CreditMetricCardItem = {
    key: string;
    label: string;
    value: ReactNode;
};
export function CreditMetricCards({ items, columnsClassName = 'sm:grid-cols-2 xl:grid-cols-5', }: {
    items: CreditMetricCardItem[];
    columnsClassName?: string;
}) {
    return (<div className={`grid gap-2 ${columnsClassName}`}>
      {items.map((item) => (<div key={item.key} className="rounded-lg border px-3 py-2">
          <div className="text-xs text-muted-foreground">{item.label}</div>
          <div className="mt-1 text-lg font-semibold">{item.value}</div>
        </div>))}
    </div>);
}
export function CreditTransactionTable({ rows, loading = false, emptyText, showAccount = false, showOperator = false, showDirection = false, showTime = true, remarkClassName = 'hidden md:table-cell', timeClassName = 'hidden xl:table-cell', }: {
    rows: CreditTransaction[];
    loading?: boolean;
    emptyText?: string;
    showAccount?: boolean;
    showOperator?: boolean;
    showDirection?: boolean;
    showTime?: boolean;
    remarkClassName?: string;
    timeClassName?: string;
}) {
    const columns = [
        showAccount ? 'account' : null,
        showTime ? 'time' : null,
        'type',
        showDirection ? 'direction' : null,
        'amount',
        'balance',
        showOperator ? 'operator' : null,
        'remark',
    ].filter(Boolean).length;
    return (<div className="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            {showAccount ? <TableHead>{translateActive("components.credits.creditShared.copy020")}</TableHead> : null}
            {showTime ? <TableHead className={timeClassName}>{translateActive("components.credits.creditShared.copy021")}</TableHead> : null}
            <TableHead>{translateActive("components.credits.creditShared.copy022")}</TableHead>
            {showDirection ? <TableHead>{translateActive("components.credits.creditShared.copy023")}</TableHead> : null}
            <TableHead>{translateActive("components.credits.creditShared.copy024")}</TableHead>
            <TableHead>{translateActive("components.credits.creditShared.copy025")}</TableHead>
            {showOperator ? <TableHead className="hidden lg:table-cell">{translateActive("components.credits.creditShared.copy026")}</TableHead> : null}
            <TableHead className={remarkClassName}>{translateActive("components.credits.creditShared.copy027")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((item) => (<TableRow key={item.id}>
              {showAccount ? (<TableCell>
                  <div className="min-w-0">
                    <div className="truncate font-medium">
                      {item.accountDisplayName || item.accountUsername || translateActive("components.credits.creditShared.copy028").replace("{0}", String(item.accountId))}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {item.accountUsername && item.accountDisplayName && item.accountDisplayName !== item.accountUsername
                    ? item.accountUsername
                    : item.accountType || '-'}
                    </div>
                  </div>
                </TableCell>) : null}
              {showTime ? <TableCell className={timeClassName}>{formatCreditDateTime(item.createdAt)}</TableCell> : null}
              <TableCell>{getTransactionTypeLabel(item.transactionType)}</TableCell>
              {showDirection ? <TableCell>{getTransactionDirectionLabel(item.direction)}</TableCell> : null}
              <TableCell className={item.direction === 'out' ? 'text-destructive' : 'text-foreground'}>
                {getTransactionAmountLabel(item)}
              </TableCell>
              <TableCell>{item.balanceAfter}</TableCell>
              {showOperator ? (<TableCell className="hidden lg:table-cell">
                  {item.operatorDisplayName || item.operatorUsername || '-'}
                </TableCell>) : null}
              <TableCell className={remarkClassName}>{buildCreditTransactionRemark(item)}{buildCreditBillingSummary(item) ? (<div className="text-xs text-muted-foreground">{buildCreditBillingSummary(item)}</div>) : null}</TableCell>
            </TableRow>))}
          {!loading && rows.length === 0 ? (<TableRow>
              <TableCell colSpan={columns} className="py-6 text-center text-muted-foreground">
                {emptyText || translateActive("components.credits.creditShared.copy029")}
              </TableCell>
            </TableRow>) : null}
        </TableBody>
      </Table>
    </div>);
}
export function CreditStatusBadges({ accountStatus, userStatus, }: {
    accountStatus?: string | null;
    userStatus?: number | null;
}) {
    return (<div className="flex flex-wrap gap-1">
      {accountStatus ? <Badge variant="outline">{getAccountStatusLabel(accountStatus)}</Badge> : null}
      {typeof userStatus === 'number' ? <Badge variant="outline">{getUserStatusLabel(userStatus)}</Badge> : null}
    </div>);
}
