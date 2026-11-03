'use client'

import type { KeyboardEvent } from 'react'
import { useEffect, useState } from 'react'
import { RefreshCcw, Search } from 'lucide-react'

import { CollapsibleFilters } from '@/components/list/collapsible-filters'
import { SimplePagination } from '@/components/list/simple-pagination'
import { PageHeader } from '@/components/page/page-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ApiError, apiFetch } from '@/lib/api'
import { useT } from '@/lib/i18n'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'

type InvitationRecord = {
  id: number
  inviteCode?: string | null
  inviteCodeStatus?: string | null
  inviterUserId?: number | null
  inviterUsername?: string | null
  inviterNickname?: string | null
  inviterEmail?: string | null
  inviterPhone?: string | null
  inviterUserStatus?: number | null
  inviterRegisterSource?: string | null
  inviterCreatedAt?: string | null
  invitedUserId?: number | null
  invitedUsername?: string | null
  invitedNickname?: string | null
  invitedEmail?: string | null
  invitedPhone?: string | null
  invitedUserStatus?: number | null
  invitedRegisterSource?: string | null
  invitedCreatedAt?: string | null
  inviterRewardCredits: string
  inviteeRewardCredits: string
  rewardDelayDays: number
  availableAt?: string | null
  inviterRewardStatus: string
  inviteeRewardStatus: string
  createdAt?: string | null
}

type PageResponse<T> = {
  list: T[]
  total: number
  pageSize: number
  currentPage: number
}

type InvitationFilters = {
  inviteCode: string
  inviteCodeStatus: string
  inviterKeyword: string
  inviterUserStatus: string
  inviterRegisterSource: string
  invitedKeyword: string
  invitedUserStatus: string
  invitedRegisterSource: string
  inviterRewardStatus: string
  inviteeRewardStatus: string
}

const ALL_FILTER_VALUE = 'all'

const DEFAULT_FILTERS: InvitationFilters = {
  inviteCode: '',
  inviteCodeStatus: ALL_FILTER_VALUE,
  inviterKeyword: '',
  inviterUserStatus: ALL_FILTER_VALUE,
  inviterRegisterSource: ALL_FILTER_VALUE,
  invitedKeyword: '',
  invitedUserStatus: ALL_FILTER_VALUE,
  invitedRegisterSource: ALL_FILTER_VALUE,
  inviterRewardStatus: ALL_FILTER_VALUE,
  inviteeRewardStatus: ALL_FILTER_VALUE,
}

type TFunction = ReturnType<typeof useT>

function normalizeFilters(filters: InvitationFilters): InvitationFilters {
  return {
    inviteCode: filters.inviteCode.trim(),
    inviteCodeStatus: filters.inviteCodeStatus || ALL_FILTER_VALUE,
    inviterKeyword: filters.inviterKeyword.trim(),
    inviterUserStatus: filters.inviterUserStatus || ALL_FILTER_VALUE,
    inviterRegisterSource: filters.inviterRegisterSource || ALL_FILTER_VALUE,
    invitedKeyword: filters.invitedKeyword.trim(),
    invitedUserStatus: filters.invitedUserStatus || ALL_FILTER_VALUE,
    invitedRegisterSource: filters.invitedRegisterSource || ALL_FILTER_VALUE,
    inviterRewardStatus: filters.inviterRewardStatus || ALL_FILTER_VALUE,
    inviteeRewardStatus: filters.inviteeRewardStatus || ALL_FILTER_VALUE,
  }
}

function appendFilterParams(qs: URLSearchParams, filters: InvitationFilters) {
  const normalized = normalizeFilters(filters)
  Object.entries(normalized).forEach(([key, value]) => {
    if (value && value !== ALL_FILTER_VALUE) {
      qs.set(key, value)
    }
  })
}

function invitationStatusLabel(status: string | null | undefined, t: TFunction): string {
  switch (String(status || '').trim().toLowerCase()) {
    case 'issued':
      return t('system.invitations.statusIssued')
    case 'pending':
      return t('system.invitations.statusPending')
    case 'skipped':
      return t('system.invitations.statusSkipped')
    case 'active':
      return t('system.invitations.statusActive')
    case 'exhausted':
      return t('system.invitations.statusExhausted')
    case 'expired':
      return t('system.invitations.statusExpired')
    case 'disabled':
      return t('system.invitations.statusDisabled')
    default:
      return status || '-'
  }
}

function userStatusLabel(status: number | null | undefined, t: TFunction): string {
  switch (status) {
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

function registerSourceLabel(value: string | null | undefined, t: TFunction): string {
  switch (String(value || '').trim().toLowerCase()) {
    case 'admin':
      return t('system.invitations.sourceAdmin')
    case 'self':
      return t('system.invitations.sourceSelf')
    case 'invite':
      return t('system.invitations.sourceInvite')
    default:
      return value || '-'
  }
}

function renderUserTitle(
  nickname: string | null | undefined,
  username: string | null | undefined,
  userId: number | null | undefined,
  t: TFunction,
) {
  return nickname || username || (userId ? t('system.invitations.userFallback').replace('{id}', String(userId)) : '-')
}

function renderContact(email: string | null | undefined, phone: string | null | undefined) {
  const values = [phone, email].map((item) => String(item || '').trim()).filter(Boolean)
  return values.length ? values.join(' / ') : '-'
}

function handleFilterInputEnter(event: KeyboardEvent<HTMLInputElement>, onSearch: () => void) {
  if (event.key === 'Enter') {
    onSearch()
  }
}

export default function SystemInvitationsPage() {
  const t = useT()
  const { session } = useAuth()
  const { targetTenant, targetTenantId } = useTenant()

  const [records, setRecords] = useState<PageResponse<InvitationRecord> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [draftFilters, setDraftFilters] = useState<InvitationFilters>({ ...DEFAULT_FILTERS })
  const [filters, setFilters] = useState<InvitationFilters>({ ...DEFAULT_FILTERS })

  async function loadRecords(nextPage = page, nextFilters = filters) {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const qs = new URLSearchParams({
        currentPage: String(nextPage),
        pageSize: '20',
      })
      appendFilterParams(qs, nextFilters)
      const res = await apiFetch<PageResponse<InvitationRecord>>(`/api/v1/invitations/admin/records?${qs.toString()}`, {
        session,
        tenantId: targetTenantId,
      })
      setRecords(res)
      setPage(res.currentPage)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('system.invitations.loadFailed'))
      setRecords(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!session) return
    void loadRecords(1, filters)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken, targetTenantId])

  if (!session) return null

  const applyFilters = () => {
    const nextFilters = normalizeFilters(draftFilters)
    setFilters(nextFilters)
    void loadRecords(1, nextFilters)
  }

  const resetFilters = () => {
    const nextFilters = { ...DEFAULT_FILTERS }
    setDraftFilters(nextFilters)
    setFilters(nextFilters)
    void loadRecords(1, nextFilters)
  }

  return (
    <div className="grid gap-4">
      <PageHeader
        title={t('system.invitations.title')}
        description={
          targetTenant
            ? t('system.invitations.descriptionWithTenant').replace('{name}', targetTenant.name)
            : t('system.invitations.description')
        }
      />

      <Card>
        <CardHeader>
          <PageHeader title={t('system.invitations.listTitle')} description={t('system.invitations.listDescription')} />
        </CardHeader>
        <CardContent className="grid gap-4">
          <CollapsibleFilters defaultExpanded title={t('system.invitations.filtersTitle')}>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <div className="grid gap-2">
                <Label htmlFor="inviteCode">{t('system.invitations.inviteCode')}</Label>
                <Input
                  id="inviteCode"
                  value={draftFilters.inviteCode}
                  onChange={(event) => setDraftFilters((current) => ({ ...current, inviteCode: event.target.value }))}
                  onKeyDown={(event) => handleFilterInputEnter(event, applyFilters)}
                  placeholder={t('system.invitations.inviteCodePlaceholder')}
                />
              </div>

              <div className="grid gap-2">
                <Label>{t('system.invitations.inviteCodeStatus')}</Label>
                <Select
                  value={draftFilters.inviteCodeStatus}
                  onValueChange={(value) => setDraftFilters((current) => ({ ...current, inviteCodeStatus: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('system.invitations.allInviteCodeStatus')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_FILTER_VALUE}>{t('system.invitations.allInviteCodeStatus')}</SelectItem>
                    <SelectItem value="active">{t('system.invitations.statusActive')}</SelectItem>
                    <SelectItem value="exhausted">{t('system.invitations.statusExhausted')}</SelectItem>
                    <SelectItem value="expired">{t('system.invitations.statusExpired')}</SelectItem>
                    <SelectItem value="disabled">{t('system.invitations.statusDisabled')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="inviterKeyword">{t('system.invitations.inviter')}</Label>
                <Input
                  id="inviterKeyword"
                  value={draftFilters.inviterKeyword}
                  onChange={(event) => setDraftFilters((current) => ({ ...current, inviterKeyword: event.target.value }))}
                  onKeyDown={(event) => handleFilterInputEnter(event, applyFilters)}
                  placeholder={t('system.invitations.keywordPlaceholder')}
                />
              </div>

              <div className="grid gap-2">
                <Label>{t('system.invitations.inviterStatus')}</Label>
                <Select
                  value={draftFilters.inviterUserStatus}
                  onValueChange={(value) => setDraftFilters((current) => ({ ...current, inviterUserStatus: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('system.invitations.allInviterStatus')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_FILTER_VALUE}>{t('system.invitations.allInviterStatus')}</SelectItem>
                    <SelectItem value="1">{t('system.user.statusNormal')}</SelectItem>
                    <SelectItem value="0">{t('common.disabled')}</SelectItem>
                    <SelectItem value="2">{t('system.user.statusPending')}</SelectItem>
                    <SelectItem value="3">{t('system.user.statusRejected')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label>{t('system.invitations.inviterSource')}</Label>
                <Select
                  value={draftFilters.inviterRegisterSource}
                  onValueChange={(value) => setDraftFilters((current) => ({ ...current, inviterRegisterSource: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('system.invitations.allInviterSource')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_FILTER_VALUE}>{t('system.invitations.allInviterSource')}</SelectItem>
                    <SelectItem value="admin">{t('system.invitations.sourceAdmin')}</SelectItem>
                    <SelectItem value="self">{t('system.invitations.sourceSelf')}</SelectItem>
                    <SelectItem value="invite">{t('system.invitations.sourceInvite')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="invitedKeyword">{t('system.invitations.invited')}</Label>
                <Input
                  id="invitedKeyword"
                  value={draftFilters.invitedKeyword}
                  onChange={(event) => setDraftFilters((current) => ({ ...current, invitedKeyword: event.target.value }))}
                  onKeyDown={(event) => handleFilterInputEnter(event, applyFilters)}
                  placeholder={t('system.invitations.keywordPlaceholder')}
                />
              </div>

              <div className="grid gap-2">
                <Label>{t('system.invitations.invitedStatus')}</Label>
                <Select
                  value={draftFilters.invitedUserStatus}
                  onValueChange={(value) => setDraftFilters((current) => ({ ...current, invitedUserStatus: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('system.invitations.allInvitedStatus')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_FILTER_VALUE}>{t('system.invitations.allInvitedStatus')}</SelectItem>
                    <SelectItem value="1">{t('system.user.statusNormal')}</SelectItem>
                    <SelectItem value="0">{t('common.disabled')}</SelectItem>
                    <SelectItem value="2">{t('system.user.statusPending')}</SelectItem>
                    <SelectItem value="3">{t('system.user.statusRejected')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label>{t('system.invitations.invitedSource')}</Label>
                <Select
                  value={draftFilters.invitedRegisterSource}
                  onValueChange={(value) => setDraftFilters((current) => ({ ...current, invitedRegisterSource: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('system.invitations.allInvitedSource')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_FILTER_VALUE}>{t('system.invitations.allInvitedSource')}</SelectItem>
                    <SelectItem value="admin">{t('system.invitations.sourceAdmin')}</SelectItem>
                    <SelectItem value="self">{t('system.invitations.sourceSelf')}</SelectItem>
                    <SelectItem value="invite">{t('system.invitations.sourceInvite')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label>{t('system.invitations.inviterRewardStatus')}</Label>
                <Select
                  value={draftFilters.inviterRewardStatus}
                  onValueChange={(value) => setDraftFilters((current) => ({ ...current, inviterRewardStatus: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('system.invitations.allInviterRewardStatus')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_FILTER_VALUE}>{t('system.invitations.allInviterRewardStatus')}</SelectItem>
                    <SelectItem value="pending">{t('system.invitations.statusPending')}</SelectItem>
                    <SelectItem value="issued">{t('system.invitations.statusIssued')}</SelectItem>
                    <SelectItem value="skipped">{t('system.invitations.statusSkipped')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label>{t('system.invitations.inviteeRewardStatus')}</Label>
                <Select
                  value={draftFilters.inviteeRewardStatus}
                  onValueChange={(value) => setDraftFilters((current) => ({ ...current, inviteeRewardStatus: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('system.invitations.allInviteeRewardStatus')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_FILTER_VALUE}>{t('system.invitations.allInviteeRewardStatus')}</SelectItem>
                    <SelectItem value="pending">{t('system.invitations.statusPending')}</SelectItem>
                    <SelectItem value="issued">{t('system.invitations.statusIssued')}</SelectItem>
                    <SelectItem value="skipped">{t('system.invitations.statusSkipped')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={applyFilters} disabled={loading}>
                <Search className="mr-2 h-4 w-4" />
                {t('system.invitations.query')}
              </Button>
              <Button variant="outline" onClick={resetFilters} disabled={loading}>
                <RefreshCcw className="mr-2 h-4 w-4" />
                {t('common.reset')}
              </Button>
              <div className="text-xs text-muted-foreground">
                {t('system.invitations.totalHint').replace('{n}', String(records?.total || 0))}
              </div>
            </div>
          </CollapsibleFilters>

          {error ? <div className="text-sm text-destructive">{error}</div> : null}

          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('system.invitations.invitedAt')}</TableHead>
                  <TableHead>{t('system.invitations.inviter')}</TableHead>
                  <TableHead>{t('system.invitations.inviterRegistrationInfo')}</TableHead>
                  <TableHead>{t('system.invitations.invited')}</TableHead>
                  <TableHead>{t('system.invitations.invitedRegistrationInfo')}</TableHead>
                  <TableHead className="hidden lg:table-cell">{t('system.invitations.inviteCode')}</TableHead>
                  <TableHead>{t('system.invitations.rewardStatus')}</TableHead>
                  <TableHead className="hidden xl:table-cell">{t('system.invitations.availableAt')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(records?.list || []).map((record) => (
                  <TableRow key={record.id}>
                    <TableCell className="whitespace-nowrap">
                      {record.createdAt ? new Date(record.createdAt).toLocaleString() : '-'}
                    </TableCell>
                    <TableCell>
                      <div className="font-medium">
                        {renderUserTitle(record.inviterNickname, record.inviterUsername, record.inviterUserId, t)}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        ID: {record.inviterUserId || '-'} · {userStatusLabel(record.inviterUserStatus, t)}
                      </div>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      <div>{renderContact(record.inviterEmail, record.inviterPhone)}</div>
                      <div>{t('system.invitations.registerSource').replace('{source}', registerSourceLabel(record.inviterRegisterSource, t))}</div>
                      <div>
                        {t('system.invitations.registeredAt').replace(
                          '{time}',
                          record.inviterCreatedAt ? new Date(record.inviterCreatedAt).toLocaleString() : '-',
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="font-medium">
                        {renderUserTitle(record.invitedNickname, record.invitedUsername, record.invitedUserId, t)}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        ID: {record.invitedUserId || '-'} · {userStatusLabel(record.invitedUserStatus, t)}
                      </div>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      <div>{renderContact(record.invitedEmail, record.invitedPhone)}</div>
                      <div>{t('system.invitations.registerSource').replace('{source}', registerSourceLabel(record.invitedRegisterSource, t))}</div>
                      <div>
                        {t('system.invitations.registeredAt').replace(
                          '{time}',
                          record.invitedCreatedAt ? new Date(record.invitedCreatedAt).toLocaleString() : '-',
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      <div className="font-mono text-xs">{record.inviteCode || '-'}</div>
                      <div className="mt-1">
                        <Badge variant="outline">{invitationStatusLabel(record.inviteCodeStatus, t)}</Badge>
                      </div>
                    </TableCell>
                    <TableCell className="text-xs">
                      <div>
                        {t('system.invitations.rewardStatusLine')
                          .replace('{inviter}', invitationStatusLabel(record.inviterRewardStatus, t))
                          .replace('{invitee}', invitationStatusLabel(record.inviteeRewardStatus, t))}
                      </div>
                      <div className="mt-1 text-muted-foreground">
                        {t('system.invitations.rewardSnapshot')
                          .replace('{inviter}', record.inviterRewardCredits)
                          .replace('{invitee}', record.inviteeRewardCredits)}
                      </div>
                      <div className="text-muted-foreground">
                        {t('system.invitations.delayDays').replace('{n}', String(record.rewardDelayDays))}
                      </div>
                    </TableCell>
                    <TableCell className="hidden xl:table-cell whitespace-nowrap">
                      {record.availableAt ? new Date(record.availableAt).toLocaleString() : '-'}
                    </TableCell>
                  </TableRow>
                ))}
                {!loading && (records?.list || []).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="py-8 text-center text-muted-foreground">
                      {t('system.invitations.emptyRecords')}
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>

          <SimplePagination
            total={records?.total || 0}
            currentPage={records?.currentPage || page}
            pageSize={records?.pageSize || 20}
            disabled={loading}
            onChange={(nextPage) => {
              void loadRecords(nextPage, filters)
            }}
          />
        </CardContent>
      </Card>
    </div>
  )
}
