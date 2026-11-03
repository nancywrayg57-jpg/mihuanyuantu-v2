'use client'

import { useEffect, useMemo, useState } from 'react'
import { MoreHorizontal, Plus, RefreshCcw } from 'lucide-react'

import { SimplePagination } from '@/components/list/simple-pagination'
import { PageHeader } from '@/components/page/page-header'
import { UserProfileForm } from '@/components/profile/user-profile-form'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { MultiSelect, type MultiSelectOption } from '@/components/ui/multi-select'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, apiFetch } from '@/lib/api'
import { hasAnyPermission } from '@/lib/auth'
import { useT } from '@/lib/i18n'
import { getEnabledUserProfileFields, normalizeUserProfileFieldsConfig, type UserProfileFieldsConfig } from '@/lib/user-profile-fields'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'

type PageResponse<T> = {
  list: T[]
  total: number
  pageSize: number
  currentPage: number
}

type RoleOption = { id: number; name: string; code: string }

type TeamOption = {
  value: number
  label: string
  disabled?: boolean
  children?: TeamOption[]
}

type UserListItem = {
  id: number
  username: string
  nickname?: string | null
  email?: string | null
  phone?: string | null
  status: number
  roles: string[]
  teams: Array<{ id: number; name: string }>
  tenantId?: number | null
  tenantName?: string | null
  profile?: Record<string, unknown>
  createdAt?: string | null
}

type UserDetail = {
  id: number
  username: string
  nickname?: string | null
  email?: string | null
  phone?: string | null
  status: number
  roles: Array<{ id: number; name: string; code: string }>
  teams: Array<{ id: number; name: string }>
  profile?: Record<string, unknown>
}

type UserProfileConfigResponse = {
  config?: {
    registration?: {
      userProfileFields?: UserProfileFieldsConfig
    }
  }
}

type TFunction = ReturnType<typeof useT>

function flattenTeamOptions(nodes: TeamOption[], depth = 0): MultiSelectOption[] {
  const out: MultiSelectOption[] = []
  for (const n of nodes) {
    out.push({ value: n.value, label: n.label, depth, disabled: Boolean(n.disabled) })
    if (n.children?.length) out.push(...flattenTeamOptions(n.children, depth + 1))
  }
  return out
}

function statusLabel(status: number, t: TFunction) {
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
      return String(status)
  }
}

function statusBadgeVariant(status: number): Parameters<typeof Badge>[0]['variant'] {
  switch (status) {
    case 1:
      return 'secondary'
    case 2:
      return 'outline'
    case 3:
      return 'destructive'
    default:
      return 'outline'
  }
}

type UserForm = {
  id?: number
  username: string
  password: string
  nickname: string
  email: string
  phone: string
  profile: Record<string, unknown>
  status: number
  roleIds: number[]
  teamIds: number[]
}

const emptyCreateForm: UserForm = {
  username: '',
  password: '',
  nickname: '',
  email: '',
  phone: '',
  profile: {},
  status: 1,
  roleIds: [],
  teamIds: [],
}

export default function UsersPage() {
  const t = useT()
  const { session } = useAuth()
  const { targetTenantId, targetTenant } = useTenant()

  const [tab, setTab] = useState<'all' | 'pending'>('all')
  const [queryUsername, setQueryUsername] = useState('')
  const [profileFilters, setProfileFilters] = useState<Record<string, unknown>>({})
  const [page, setPage] = useState(1)
  const [data, setData] = useState<PageResponse<UserListItem> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [roles, setRoles] = useState<RoleOption[]>([])
  const [teams, setTeams] = useState<TeamOption[]>([])
  const [profileConfig, setProfileConfig] = useState<UserProfileFieldsConfig>(normalizeUserProfileFieldsConfig(null))
  const flatTeams = useMemo(() => flattenTeamOptions(teams), [teams])
  const roleOptions = useMemo<MultiSelectOption[]>(
    () => roles.map((r) => ({ value: r.id, label: `${r.name} (${r.code})` })),
    [roles],
  )
  const listVisibleProfileFields = useMemo(
    () => getEnabledUserProfileFields(profileConfig).filter((field) => field.listVisible),
    [profileConfig],
  )
  const filterableProfileConfig = useMemo(
    () => ({
      ...profileConfig,
      fields: getEnabledUserProfileFields(profileConfig)
        .filter((field) => field.filterable)
        .map((field) => ({ ...field, required: false })),
    }),
    [profileConfig],
  )

  const canCreate = hasAnyPermission(session, ['user:create'])
  const canEdit = hasAnyPermission(session, ['user:update'])
  const canDelete = hasAnyPermission(session, ['user:delete'])
  const canResetPassword = hasAnyPermission(session, ['user:reset-password'])
  const canAudit = hasAnyPermission(session, ['user:audit'])

  async function loadOptions() {
    if (!session) return
    try {
      const profileConfigRequest = session.isSuperuser && targetTenantId
        ? apiFetch<UserProfileConfigResponse>(`/api/v1/tenants/${targetTenantId}`, { session })
        : apiFetch<UserProfileConfigResponse>('/api/v1/tenant/profile/settings', { session })

      const [roleList, teamOptions, tenantConfig] = await Promise.all([
        apiFetch<RoleOption[]>('/api/v1/roles/all', { session, tenantId: targetTenantId }),
        apiFetch<TeamOption[]>('/api/v1/teams/options', { session, tenantId: targetTenantId }),
        profileConfigRequest.catch(() => null),
      ])
      setRoles(roleList)
      setTeams(teamOptions)
      setProfileConfig(normalizeUserProfileFieldsConfig(tenantConfig?.config?.registration?.userProfileFields))
    } catch {
      setRoles([])
      setTeams([])
      setProfileConfig(normalizeUserProfileFieldsConfig(null))
    }
  }

  async function loadUsers() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const path = tab === 'pending' ? '/api/v1/users/pending' : '/api/v1/users'
      const res = await apiFetch<PageResponse<UserListItem>>(path, {
        method: 'POST',
        session,
        tenantId: targetTenantId,
        body: JSON.stringify({
          currentPage: page,
          pageSize: 10,
          username: queryUsername || undefined,
          profileFilters: profileFilters && Object.keys(profileFilters).length > 0 ? profileFilters : undefined,
        }),
      })
      setData(res)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('system.common.loadFailed'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadOptions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken, targetTenantId])

  useEffect(() => {
    void loadUsers()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken, tab, page, targetTenantId])

  useEffect(() => {
    setProfileFilters({})
  }, [targetTenantId])

  const total = data?.total ?? 0
  const pageSize = data?.pageSize ?? 10
  const currentPage = data?.currentPage ?? page

  const [userDialogOpen, setUserDialogOpen] = useState(false)
  const [userDialogMode, setUserDialogMode] = useState<'create' | 'edit'>('create')
  const [userForm, setUserForm] = useState<UserForm>(emptyCreateForm)
  const [userDialogError, setUserDialogError] = useState<string | null>(null)

  const [resetOpen, setResetOpen] = useState(false)
  const [resetUserId, setResetUserId] = useState<number | null>(null)
  const [resetPassword, setResetPassword] = useState('')
  const [resetError, setResetError] = useState<string | null>(null)

  const [auditOpen, setAuditOpen] = useState(false)
  const [auditUserId, setAuditUserId] = useState<number | null>(null)
  const [auditApproved, setAuditApproved] = useState(true)
  const [auditRemark, setAuditRemark] = useState('')
  const [auditError, setAuditError] = useState<string | null>(null)

  async function openCreate() {
    setUserDialogMode('create')
    setUserForm(emptyCreateForm)
    setUserDialogError(null)
    setUserDialogOpen(true)
  }

  async function openEdit(userId: number) {
    if (!session) return
    setUserDialogMode('edit')
    setUserDialogError(null)
    setUserDialogOpen(true)
    try {
      const detail = await apiFetch<UserDetail>(`/api/v1/users/${userId}`, {
        session,
        tenantId: targetTenantId,
      })
      setUserForm({
        id: detail.id,
        username: detail.username,
        password: '',
        nickname: detail.nickname || '',
        email: detail.email || '',
        phone: detail.phone || '',
        profile: detail.profile || {},
        status: detail.status,
        roleIds: (detail.roles || []).map((r) => r.id),
        teamIds: (detail.teams || []).map((t) => t.id),
      })
    } catch (err) {
      setUserDialogError(err instanceof ApiError ? err.message : t('system.user.loadUserFailed'))
    }
  }

  if (!session) return null

  return (
    <div className="grid gap-4">
      <PageHeader
        title={t('system.user.title')}
        description={
          <>
            <div>{t('system.user.description')}</div>
            {session.isSuperuser && targetTenant ? (
              <div className="mt-1 text-xs text-muted-foreground">
                {t('system.common.targetTenant').replace('{name}', targetTenant.name).replace('{code}', targetTenant.code)}
              </div>
            ) : null}
          </>
        }
      />
      <Card>
        <CardContent className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="flex flex-1 items-center gap-2">
              <Input
                value={queryUsername}
                onChange={(e) => setQueryUsername(e.target.value)}
                placeholder={t('system.user.searchPlaceholder')}
              />
              <Button
                variant="secondary"
                onClick={() => {
                  setPage(1)
                  void loadUsers()
                }}
                disabled={loading}
              >
                {t('common.search')}
              </Button>
              <Button variant="outline" onClick={loadUsers} disabled={loading}>
                <RefreshCcw className="mr-2 h-4 w-4" />
                {t('common.refresh')}
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setQueryUsername('')
                  setProfileFilters({})
                  setPage(1)
                }}
                disabled={loading}
              >
                {t('system.user.clearFilters')}
              </Button>
            </div>

            {canCreate ? (
              <Button onClick={() => void openCreate()}>
                <Plus className="mr-2 h-4 w-4" />
                {t('system.user.create')}
              </Button>
            ) : null}
          </div>

          {(filterableProfileConfig.fields || []).length > 0 ? (
            <div className="grid gap-3 rounded-md border p-4">
              <div className="text-sm font-medium">{t('system.user.profileFilters')}</div>
              <UserProfileForm
                config={filterableProfileConfig}
                value={profileFilters}
                onChange={setProfileFilters}
                disabled={loading}
              />
            </div>
          ) : null}

          {error ? <div className="text-sm text-destructive">{error}</div> : null}

          <Tabs
            value={tab}
            onValueChange={(v) => {
              setTab(v === 'pending' ? 'pending' : 'all')
              setPage(1)
            }}
          >
            <TabsList>
              <TabsTrigger value="all">{t('system.user.allUsers')}</TabsTrigger>
              <TabsTrigger value="pending">{t('system.user.pendingReview')}</TabsTrigger>
            </TabsList>

            <TabsContent value="all">
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="hidden w-[80px] md:table-cell">ID</TableHead>
                      <TableHead>{t('auth.username')}</TableHead>
                      <TableHead className="hidden md:table-cell">{t('system.auth.nickname')}</TableHead>
                      <TableHead>{t('common.status')}</TableHead>
                      <TableHead className="hidden md:table-cell">{t('system.user.roles')}</TableHead>
                      <TableHead className="hidden md:table-cell">{t('system.common.team')}</TableHead>
                      {listVisibleProfileFields.map((field) => (
                        <TableHead key={`head:${field.key}`} className="hidden xl:table-cell">
                          {field.label}
                        </TableHead>
                      ))}
                      <TableHead className="hidden md:table-cell">{t('common.createdAt')}</TableHead>
                      <TableHead className="w-[80px] text-right">{t('common.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(data?.list || []).map((u) => (
                      <TableRow key={u.id}>
                        <TableCell className="hidden md:table-cell">{u.id}</TableCell>
                        <TableCell>
                          <div className="font-medium">{u.username}</div>
                          <div className="text-xs text-muted-foreground md:hidden">{u.nickname || '-'}</div>
                          {session.isSuperuser && u.tenantName ? (
                            <div className="text-xs text-muted-foreground md:hidden">{u.tenantName}</div>
                          ) : null}
                        </TableCell>
                        <TableCell className="hidden md:table-cell">{u.nickname || '-'}</TableCell>
                        <TableCell>
                          <Badge variant={statusBadgeVariant(u.status)}>{statusLabel(u.status, t)}</Badge>
                        </TableCell>
                        <TableCell className="hidden md:table-cell">{(u.roles || []).join(', ') || '-'}</TableCell>
                        <TableCell className="hidden md:table-cell">
                          {(u.teams || []).map((t) => t.name).join(', ') || '-'}
                        </TableCell>
                        {listVisibleProfileFields.map((field) => {
                          const rawValue = u.profile?.[field.key]
                          const displayValue = Array.isArray(rawValue)
                            ? rawValue.join(', ')
                            : typeof rawValue === 'boolean'
                              ? rawValue
                                ? t('system.common.yes')
                                : t('system.common.no')
                              : rawValue == null || rawValue === ''
                                ? '-'
                                : String(rawValue)
                          return (
                            <TableCell key={`${u.id}:${field.key}`} className="hidden xl:table-cell">
                              {displayValue}
                            </TableCell>
                          )
                        })}
                        <TableCell className="hidden md:table-cell">
                          {u.createdAt ? new Date(u.createdAt).toLocaleString() : ''}
                        </TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button size="icon" variant="ghost">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              {canEdit ? (
                                <DropdownMenuItem onClick={() => void openEdit(u.id)}>{t('common.edit')}</DropdownMenuItem>
                              ) : null}
                              {canResetPassword ? (
                                <DropdownMenuItem
                                  onClick={() => {
                                    setResetUserId(u.id)
                                    setResetPassword('')
                                    setResetError(null)
                                    setResetOpen(true)
                                  }}
                                >
                                  {t('system.user.resetPassword')}
                                </DropdownMenuItem>
                              ) : null}
                              {canDelete ? (
                                <>
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem
                                    className="text-destructive focus:text-destructive"
                                    onClick={async () => {
                                      setError(null)
                                      try {
                                        await apiFetch(`/api/v1/users/${u.id}`, {
                                          method: 'DELETE',
                                          session,
                                          tenantId: targetTenantId,
                                        })
                                        await loadUsers()
                                      } catch (err) {
                                        setError(err instanceof ApiError ? err.message : t('system.common.deleteFailed'))
                                      }
                                    }}
                                  >
                                    {t('common.delete')}
                                  </DropdownMenuItem>
                                </>
                              ) : null}
                              {!canEdit && !canResetPassword && !canDelete ? (
                                <DropdownMenuItem disabled>{t('system.user.noActions')}</DropdownMenuItem>
                              ) : null}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                    {!loading && (data?.list || []).length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={8 + listVisibleProfileFields.length} className="py-6 text-center text-muted-foreground">
                          {t('common.empty')}
                        </TableCell>
                      </TableRow>
                    ) : null}
                  </TableBody>
                </Table>
              </div>
            </TabsContent>

            <TabsContent value="pending">
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="hidden w-[80px] md:table-cell">ID</TableHead>
                      <TableHead>{t('auth.username')}</TableHead>
                      <TableHead>{t('common.status')}</TableHead>
                      <TableHead className="w-[80px] text-right">{t('common.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(data?.list || []).map((u) => (
                      <TableRow key={u.id}>
                        <TableCell className="hidden md:table-cell">{u.id}</TableCell>
                        <TableCell>
                          <div className="font-medium">{u.username}</div>
                          <div className="text-xs text-muted-foreground">{u.nickname || '-'}</div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={statusBadgeVariant(u.status)}>{statusLabel(u.status, t)}</Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button size="icon" variant="ghost">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              {canAudit ? (
                                <DropdownMenuItem
                                  onClick={() => {
                                    setAuditUserId(u.id)
                                    setAuditApproved(true)
                                    setAuditRemark('')
                                    setAuditError(null)
                                    setAuditOpen(true)
                                  }}
                                >
                                  {t('system.user.audit')}
                                </DropdownMenuItem>
                              ) : null}
                              {canEdit ? (
                                <>
                                  {canAudit ? <DropdownMenuSeparator /> : null}
                                  <DropdownMenuItem onClick={() => void openEdit(u.id)}>
                                    {t('system.user.viewEdit')}
                                  </DropdownMenuItem>
                                </>
                              ) : null}
                              {!canAudit && !canEdit ? (
                                <DropdownMenuItem disabled>{t('system.user.noActions')}</DropdownMenuItem>
                              ) : null}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                    {!loading && (data?.list || []).length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={4} className="py-6 text-center text-muted-foreground">
                          {t('common.empty')}
                        </TableCell>
                      </TableRow>
                    ) : null}
                  </TableBody>
                </Table>
              </div>
            </TabsContent>
          </Tabs>

          <SimplePagination
            total={total}
            currentPage={currentPage}
            pageSize={pageSize}
            disabled={loading}
            onChange={(p) => setPage(p)}
          />
        </CardContent>
      </Card>

      <Dialog open={userDialogOpen} onOpenChange={setUserDialogOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{userDialogMode === 'create' ? t('system.user.create') : t('system.user.edit')}</DialogTitle>
            <DialogDescription>{t('system.user.dialogDescription')}</DialogDescription>
          </DialogHeader>

          {userDialogError ? <div className="text-sm text-destructive">{userDialogError}</div> : null}

          <div className="grid gap-4 md:grid-cols-2">
            <div className="grid gap-2">
              <Label>{t('auth.username')}</Label>
              <Input
                value={userForm.username}
                onChange={(e) => setUserForm((s) => ({ ...s, username: e.target.value }))}
                disabled={userDialogMode === 'edit'}
              />
            </div>
            {userDialogMode === 'create' ? (
              <div className="grid gap-2">
                <Label>{t('auth.password')}</Label>
                <Input
                  type="password"
                  value={userForm.password}
                  onChange={(e) => setUserForm((s) => ({ ...s, password: e.target.value }))}
                />
              </div>
            ) : (
              <div className="grid gap-2">
                <Label>{t('common.status')}</Label>
                <Select
                  value={String(userForm.status)}
                  onValueChange={(v) => setUserForm((s) => ({ ...s, status: Number(v) }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">{t('system.user.statusNormal')}</SelectItem>
                    <SelectItem value="0">{t('common.disabled')}</SelectItem>
                    <SelectItem value="2">{t('system.user.statusPending')}</SelectItem>
                    <SelectItem value="3">{t('system.user.statusRejected')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="grid gap-2">
              <Label>{t('system.auth.nickname')}</Label>
              <Input value={userForm.nickname} onChange={(e) => setUserForm((s) => ({ ...s, nickname: e.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>Email</Label>
              <Input value={userForm.email} onChange={(e) => setUserForm((s) => ({ ...s, email: e.target.value }))} />
            </div>
            <div className="grid gap-2 md:col-span-2">
              <Label>{t('system.auth.phone')}</Label>
              <Input value={userForm.phone} onChange={(e) => setUserForm((s) => ({ ...s, phone: e.target.value }))} />
            </div>

            {(profileConfig.fields || []).length > 0 ? (
              <div className="grid gap-3 md:col-span-2">
                <Label>{t('system.user.customProfile')}</Label>
                <UserProfileForm
                  config={profileConfig}
                  value={userForm.profile}
                  onChange={(profile) => setUserForm((s) => ({ ...s, profile }))}
                />
              </div>
            ) : null}

            <div className="grid gap-2">
              <Label>{t('system.user.roles')}</Label>
              <MultiSelect
                options={roleOptions}
                value={userForm.roleIds}
                onChange={(ids) => setUserForm((s) => ({ ...s, roleIds: ids as number[] }))}
                placeholder={t('system.user.selectRoles')}
                searchPlaceholder={t('system.user.searchRoles')}
                emptyText={roles.length === 0 ? t('system.user.noRolesAvailable') : t('system.common.noMatches')}
              />
            </div>

            <div className="grid gap-2">
              <Label>{t('system.common.team')}</Label>
              <MultiSelect
                options={flatTeams}
                value={userForm.teamIds}
                onChange={(ids) => setUserForm((s) => ({ ...s, teamIds: ids as number[] }))}
                placeholder={t('system.user.selectTeams')}
                searchPlaceholder={t('system.user.searchTeams')}
                emptyText={flatTeams.length === 0 ? t('system.common.noTeams') : t('system.common.noMatches')}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              onClick={async () => {
                if (!session) return
                setUserDialogError(null)
                try {
                  if (userDialogMode === 'create') {
                    await apiFetch('/api/v1/users/create', {
                      method: 'POST',
                      session,
                      tenantId: targetTenantId,
                      body: JSON.stringify({
                        username: userForm.username,
                        password: userForm.password,
                        nickname: userForm.nickname || undefined,
                        email: userForm.email || undefined,
                        phone: userForm.phone || undefined,
                        profile: userForm.profile,
                        status: userForm.status,
                        roleIds: userForm.roleIds,
                        teamIds: userForm.teamIds,
                      }),
                    })
                  } else if (userForm.id) {
                    await apiFetch(`/api/v1/users/${userForm.id}`, {
                      method: 'PUT',
                      session,
                      tenantId: targetTenantId,
                      body: JSON.stringify({
                        nickname: userForm.nickname || undefined,
                        email: userForm.email || undefined,
                        phone: userForm.phone || undefined,
                        profile: userForm.profile,
                        status: userForm.status,
                        roleIds: userForm.roleIds,
                        teamIds: userForm.teamIds,
                      }),
                    })
                  }
                  setUserDialogOpen(false)
                  await loadUsers()
                } catch (err) {
                  setUserDialogError(err instanceof ApiError ? err.message : t('system.common.saveFailed'))
                }
              }}
            >
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={resetOpen} onOpenChange={setResetOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('system.user.resetPassword')}</DialogTitle>
            <DialogDescription>{t('system.user.resetPasswordDescription')}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label>{t('system.user.newPassword')}</Label>
            <Input type="password" value={resetPassword} onChange={(e) => setResetPassword(e.target.value)} />
          </div>
          {resetError ? <div className="text-sm text-destructive">{resetError}</div> : null}
          <DialogFooter>
            <Button
              onClick={async () => {
                if (!session || !resetUserId) return
                setResetError(null)
                try {
                  await apiFetch(`/api/v1/users/${resetUserId}/reset-password`, {
                    method: 'POST',
                    session,
                    tenantId: targetTenantId,
                    body: JSON.stringify({ newPassword: resetPassword }),
                  })
                  setResetOpen(false)
                } catch (err) {
                  setResetError(err instanceof ApiError ? err.message : t('system.user.resetFailed'))
                }
              }}
            >
              {t('common.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={auditOpen} onOpenChange={setAuditOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{t('system.user.auditUser')}</DialogTitle>
            <DialogDescription>{t('system.user.auditDescription')}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid gap-2">
              <Label>{t('system.user.auditResult')}</Label>
              <Select value={auditApproved ? 'approve' : 'reject'} onValueChange={(v) => setAuditApproved(v !== 'reject')}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="approve">{t('system.user.approve')}</SelectItem>
                  <SelectItem value="reject">{t('system.user.reject')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>{t('system.common.remark')}</Label>
              <Textarea value={auditRemark} onChange={(e) => setAuditRemark(e.target.value)} />
            </div>
            {auditError ? <div className="text-sm text-destructive">{auditError}</div> : null}
          </div>
          <DialogFooter>
            <Button
              onClick={async () => {
                if (!session || !auditUserId) return
                setAuditError(null)
                try {
                  await apiFetch(`/api/v1/users/${auditUserId}/audit`, {
                    method: 'POST',
                    session,
                    tenantId: targetTenantId,
                    body: JSON.stringify({ approved: auditApproved, remark: auditRemark || undefined }),
                  })
                  setAuditOpen(false)
                  await loadUsers()
                } catch (err) {
                  setAuditError(err instanceof ApiError ? err.message : t('system.user.auditFailed'))
                }
              }}
            >
              {t('common.submit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
