'use client'

import { useEffect, useMemo, useState } from 'react'
import { Pencil, Plus, RefreshCcw, Trash2 } from 'lucide-react'

import { CollapsibleFilters } from '@/components/list/collapsible-filters'
import { FilterGrid } from '@/components/list/filter-grid'
import { SimplePagination } from '@/components/list/simple-pagination'
import { PageHeader } from '@/components/page/page-header'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { MultiSelect, type MultiSelectOption } from '@/components/ui/multi-select'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, apiFetch } from '@/lib/api'
import { hasAnyPermission } from '@/lib/auth'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'
import { useT } from '@/lib/i18n'

type PageResponse<T> = {
  list: T[]
  total: number
  pageSize: number
  currentPage: number
}

type RoleItem = {
  id: number
  name: string
  code: string
  description?: string | null
  isSystem: boolean
  isActive: boolean
  sortOrder: number
  menuIds: number[]
  dataRange: number
  dataPermissions: number
  teamPermissions: Array<{ id: number; permissions: number }>
  createdAt?: string | null
}

type MenuTreeItem = {
  value: number
  label: string
  children?: MenuTreeItem[]
}

type TeamOptionNode = {
  value: number
  label: string
  disabled?: boolean
  children?: TeamOptionNode[]
}

type TeamPermissionFormItem = {
  id: number
  permissions: number
}

const DATA_RANGE_OPTIONS = [
  { value: 0, labelKey: 'system.role.rangeSelf' },
  { value: 1, labelKey: 'system.role.rangeTeam' },
  { value: 2, labelKey: 'system.role.rangeTeamChildren' },
  { value: 3, labelKey: 'system.role.rangeCustomTeams' },
  { value: 4, labelKey: 'system.role.rangeAll' },
] as const

const DATA_PERMISSION_OPTIONS = [
  { value: 1, labelKey: 'system.role.permissionRead' },
  { value: 2, labelKey: 'common.edit' },
  { value: 4, labelKey: 'common.delete' },
] as const

function flattenMenuTree(nodes: MenuTreeItem[], depth = 0): MultiSelectOption[] {
  const out: MultiSelectOption[] = []
  for (const n of nodes) {
    out.push({ value: n.value, label: n.label, depth })
    if (n.children?.length) out.push(...flattenMenuTree(n.children, depth + 1))
  }
  return out
}

function flattenTeamOptions(nodes: TeamOptionNode[], depth = 0): MultiSelectOption[] {
  const out: MultiSelectOption[] = []
  for (const n of nodes) {
    out.push({ value: n.value, label: n.label, depth, disabled: n.disabled })
    if (n.children?.length) out.push(...flattenTeamOptions(n.children, depth + 1))
  }
  return out
}

function togglePermissionFlag(current: number, flag: number, checked: boolean) {
  return checked ? current | flag : current & ~flag
}

function hasPermissionFlag(current: number, flag: number) {
  return (current & flag) === flag
}

type RoleForm = {
  id?: number
  name: string
  code: string
  description: string
  isActive: boolean
  sortOrder: string
  menuIds: number[]
  dataRange: number
  dataPermissions: number
  teamPermissions: TeamPermissionFormItem[]
}

const emptyForm: RoleForm = {
  name: '',
  code: '',
  description: '',
  isActive: true,
  sortOrder: '0',
  menuIds: [],
  dataRange: 0,
  dataPermissions: 1,
  teamPermissions: [],
}

export default function RolesPage() {
  const t = useT()
  const { session } = useAuth()
  const { targetTenantId } = useTenant()

  const [queryName, setQueryName] = useState('')
  const [queryCode, setQueryCode] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<PageResponse<RoleItem> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [menuTree, setMenuTree] = useState<MenuTreeItem[]>([])
  const flatMenus = useMemo(() => flattenMenuTree(menuTree), [menuTree])
  const [teamTree, setTeamTree] = useState<TeamOptionNode[]>([])
  const flatTeams = useMemo(() => flattenTeamOptions(teamTree), [teamTree])
  const teamLabelMap = useMemo(
    () => new Map(flatTeams.map((item) => [Number(item.value), item.label])),
    [flatTeams],
  )
  const dataRangeLabelMap = useMemo(
    () => new Map<number, string>(DATA_RANGE_OPTIONS.map((item) => [item.value, t(item.labelKey)])),
    [t],
  )

  const canCreate = hasAnyPermission(session, ['role:create'])
  const canEdit = hasAnyPermission(session, ['role:update'])
  const canDelete = hasAnyPermission(session, ['role:delete'])
  const canReadTeams = hasAnyPermission(session, ['team:read'])

  async function loadMenus() {
    if (!session) return
    try {
      // 必须带目标租户：菜单行逐租户一份，不带的话超管切到 B 租户
      // 却在用 A 租户的菜单树授权，勾出来的 menu_id 根本不属于 B。
      const res = await apiFetch<MenuTreeItem[]>('/api/v1/menus/tree/options', {
        session,
        tenantId: targetTenantId,
      })
      setMenuTree(res)
    } catch {
      setMenuTree([])
    }
  }

  async function loadTeams() {
    if (!session) return
    if (!canReadTeams) {
      setTeamTree([])
      return
    }
    try {
      const res = await apiFetch<TeamOptionNode[]>('/api/v1/teams/options', {
        session,
        tenantId: targetTenantId,
      })
      setTeamTree(res)
    } catch {
      setTeamTree([])
    }
  }

  async function loadRoles() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch<PageResponse<RoleItem>>('/api/v1/roles', {
        method: 'POST',
        session,
        tenantId: targetTenantId,
        body: JSON.stringify({
          currentPage: page,
          pageSize: 10,
          name: queryName || undefined,
          code: queryCode || undefined,
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
    void loadMenus()
    void loadTeams()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canReadTeams, session?.accessToken, targetTenantId])

  useEffect(() => {
    void loadRoles()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken, page, targetTenantId])

  const total = data?.total ?? 0
  const pageSize = data?.pageSize ?? 10
  const currentPage = data?.currentPage ?? page

  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create')
  const [form, setForm] = useState<RoleForm>(emptyForm)
  const [dialogError, setDialogError] = useState<string | null>(null)
  const selectedTeamIds = useMemo(() => form.teamPermissions.map((item) => item.id), [form.teamPermissions])

  function updateSelectedTeams(nextTeamIds: number[]) {
    setForm((prev) => {
      const seen = new Set<number>()
      const normalized = nextTeamIds
        .map((item) => Number(item))
        .filter((item) => {
          if (!Number.isInteger(item) || item <= 0 || seen.has(item)) return false
          seen.add(item)
          return true
        })
      const existing = new Map(prev.teamPermissions.map((item) => [item.id, item]))
      return {
        ...prev,
        teamPermissions: normalized.map((id) => existing.get(id) || { id, permissions: prev.dataPermissions || 1 }),
      }
    })
  }

  function updateTeamPermission(teamId: number, flag: number, checked: boolean) {
    setForm((prev) => ({
      ...prev,
      teamPermissions: prev.teamPermissions.map((item) => (
        item.id === teamId
          ? { ...item, permissions: togglePermissionFlag(item.permissions, flag, checked) }
          : item
      )),
    }))
  }

  function openCreate() {
    setDialogMode('create')
    setForm(emptyForm)
    setDialogError(null)
    setDialogOpen(true)
  }

  function openEdit(item: RoleItem) {
    setDialogMode('edit')
    setDialogError(null)
    setForm({
      id: item.id,
      name: item.name,
      code: item.code,
      description: item.description || '',
      isActive: item.isActive,
      sortOrder: String(item.sortOrder ?? 0),
      menuIds: item.menuIds || [],
      dataRange: item.dataRange ?? 0,
      dataPermissions: item.dataPermissions ?? 1,
      teamPermissions: item.teamPermissions || [],
    })
    setDialogOpen(true)
  }

  if (!session) return null

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <PageHeader title={t('system.role.title')} />
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3">
            <CollapsibleFilters>
              <FilterGrid>
                <Input value={queryName} onChange={(e) => setQueryName(e.target.value)} placeholder={t('system.role.name')} />
                <Input value={queryCode} onChange={(e) => setQueryCode(e.target.value)} placeholder={t('system.role.code')} />
              </FilterGrid>
            </CollapsibleFilters>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  onClick={() => {
                    setPage(1)
                    void loadRoles()
                  }}
                  disabled={loading}
                >
                  {t('common.search')}
                </Button>
                <Button variant="outline" onClick={loadRoles} disabled={loading}>
                  <RefreshCcw className="mr-2 h-4 w-4" />
                  {t('common.refresh')}
                </Button>
              </div>

              <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                {canCreate ? (
                  <DialogTrigger asChild>
                    <Button onClick={openCreate}>
                      <Plus className="mr-2 h-4 w-4" />
                      {t('system.role.create')}
                    </Button>
                  </DialogTrigger>
                ) : null}
                <DialogContent className="max-w-5xl">
                  <DialogHeader>
                    <DialogTitle>{dialogMode === 'create' ? t('system.role.create') : t('system.role.edit')}</DialogTitle>
                  </DialogHeader>
                  {dialogError ? <div className="text-sm text-destructive">{dialogError}</div> : null}

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="grid gap-2">
                      <Label>{t('system.role.name')}</Label>
                      <Input value={form.name} onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))} />
                    </div>
                    <div className="grid gap-2">
                      <Label>{t('system.role.code')}</Label>
                      <Input value={form.code} onChange={(e) => setForm((s) => ({ ...s, code: e.target.value }))} />
                    </div>
                    <label className="flex items-center gap-2 text-sm md:col-span-2">
                      <Checkbox checked={form.isActive} onCheckedChange={(v) => setForm((s) => ({ ...s, isActive: Boolean(v) }))} />
                      {t('system.role.enableRole')}
                    </label>
                    <div className="grid gap-2 md:col-span-2">
                      <Label>{t('common.description')}</Label>
                      <Textarea value={form.description} onChange={(e) => setForm((s) => ({ ...s, description: e.target.value }))} />
                    </div>
                    <div className="grid gap-2">
                      <Label>{t('system.role.dataRange')}</Label>
                      <Select
                        value={String(form.dataRange)}
                        onValueChange={(value: string) => setForm((s) => ({ ...s, dataRange: Number(value) }))}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder={t('system.role.dataRangePlaceholder')} />
                        </SelectTrigger>
                        <SelectContent>
                          {DATA_RANGE_OPTIONS.map((item) => (
                            <SelectItem key={item.value} value={String(item.value)}>
                              {t(item.labelKey)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label>{t('system.common.sort')}</Label>
                      <Input value={form.sortOrder} onChange={(e) => setForm((s) => ({ ...s, sortOrder: e.target.value }))} />
                    </div>
                    <div className="grid gap-2 md:col-span-2">
                      <Label>{t('system.role.dataPermissions')}</Label>
                      <div className="flex flex-wrap gap-4 rounded-md border p-3">
                        {DATA_PERMISSION_OPTIONS.map((item) => (
                          <label key={item.value} className="flex items-center gap-2 text-sm">
                            <Checkbox
                              checked={hasPermissionFlag(form.dataPermissions, item.value)}
                              onCheckedChange={(checked) =>
                                setForm((s) => ({
                                  ...s,
                                  dataPermissions: togglePermissionFlag(s.dataPermissions, item.value, Boolean(checked)),
                                }))
                              }
                            />
                            {t(item.labelKey)}
                          </label>
                        ))}
                      </div>
                    </div>
                    {form.dataRange === 3 ? (
                      <div className="grid gap-3 md:col-span-2">
                        <div className="grid gap-2">
                          <Label>{t('system.role.customTeamPermissions')}</Label>
                          <MultiSelect
                            options={flatTeams}
                            value={selectedTeamIds}
                            onChange={(ids) => updateSelectedTeams(ids as number[])}
                            placeholder={t('system.role.selectTeam')}
                            searchPlaceholder={t('system.role.searchTeam')}
                            emptyText={flatTeams.length === 0 ? t('system.role.noTeamsAvailable') : t('system.common.noMatches')}
                            maxDisplay={6}
                          />
                        </div>
                        <div className="grid gap-2">
                          {form.teamPermissions.length > 0 ? (
                            form.teamPermissions.map((item) => (
                              <div key={item.id} className="flex flex-col gap-2 rounded-md border p-3 md:flex-row md:items-center md:justify-between">
                                <div className="text-sm font-medium">{teamLabelMap.get(item.id) || t('system.role.teamFallback').replace('{id}', String(item.id))}</div>
                                <div className="flex flex-wrap gap-4">
                                  {DATA_PERMISSION_OPTIONS.map((permission) => (
                                    <label key={`${item.id}-${permission.value}`} className="flex items-center gap-2 text-sm">
                                      <Checkbox
                                        checked={hasPermissionFlag(item.permissions, permission.value)}
                                        onCheckedChange={(checked) => updateTeamPermission(item.id, permission.value, Boolean(checked))}
                                      />
                                      {t(permission.labelKey)}
                                    </label>
                                  ))}
                                </div>
                              </div>
                            ))
                          ) : null}
                        </div>
                      </div>
                    ) : null}
                    <div className="grid gap-2 md:col-span-2">
                      <Label>{t('system.role.menuPermissions')}</Label>
                      <MultiSelect
                        options={flatMenus}
                        value={form.menuIds}
                        onChange={(ids) => setForm((s) => ({ ...s, menuIds: ids as number[] }))}
                        placeholder={t('system.role.selectMenuPermissions')}
                        searchPlaceholder={t('system.role.searchMenus')}
                        emptyText={flatMenus.length === 0 ? t('system.common.noMenus') : t('system.common.noMatches')}
                        maxDisplay={6}
                      />
                    </div>
                  </div>

                  <DialogFooter>
                    <Button
                      onClick={async () => {
                        if (!session) return
                        setDialogError(null)
                        try {
                          const payload = {
                            name: form.name,
                            code: form.code,
                            description: form.description || undefined,
                            sortOrder: Number(form.sortOrder) || 0,
                            isActive: form.isActive,
                            menuIds: form.menuIds,
                            dataRange: form.dataRange,
                            dataPermissions: form.dataPermissions,
                            teamPermissions: form.dataRange === 3 ? form.teamPermissions : [],
                          }
                          if (dialogMode === 'create') {
                            await apiFetch('/api/v1/roles/create', {
                              method: 'POST',
                              session,
                              tenantId: targetTenantId,
                              body: JSON.stringify(payload),
                            })
                          } else if (form.id) {
                            await apiFetch(`/api/v1/roles/${form.id}`, {
                              method: 'PUT',
                              session,
                              tenantId: targetTenantId,
                              body: JSON.stringify(payload),
                            })
                          }
                          setDialogOpen(false)
                          await loadRoles()
                        } catch (err) {
                          setDialogError(err instanceof ApiError ? err.message : t('system.common.saveFailed'))
                        }
                      }}
                    >
                      {t('common.save')}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          {error ? <div className="text-sm text-destructive">{error}</div> : null}

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="hidden w-[80px] md:table-cell">ID</TableHead>
                  <TableHead>{t('system.role.role')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('system.common.code')}</TableHead>
                  <TableHead className="hidden lg:table-cell">{t('system.role.dataRange')}</TableHead>
                  <TableHead>{t('common.status')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('system.role.menuCount')}</TableHead>
                  <TableHead className="w-[150px]">{t('common.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.list || []).map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="hidden md:table-cell">{r.id}</TableCell>
                    <TableCell>
                      <div className="font-medium">{r.name}</div>
                      <div className="text-xs text-muted-foreground md:hidden">{r.code}</div>
                      <div className="text-xs text-muted-foreground lg:hidden">
                        {dataRangeLabelMap.get(r.dataRange) || t('system.role.rangeFallback').replace('{n}', String(r.dataRange))}
                      </div>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">{r.code}</TableCell>
                    <TableCell className="hidden lg:table-cell">
                      <Badge variant="outline">{dataRangeLabelMap.get(r.dataRange) || t('system.role.rangeFallback').replace('{n}', String(r.dataRange))}</Badge>
                    </TableCell>
                    <TableCell>
                      {r.isSystem ? (
                        <Badge variant="outline">{t('system.role.systemRole')}</Badge>
                      ) : r.isActive ? (
                        <Badge variant="secondary">{t('common.enabled')}</Badge>
                      ) : (
                        <Badge variant="outline">{t('common.disabled')}</Badge>
                      )}
                    </TableCell>
                    <TableCell className="hidden md:table-cell">{(r.menuIds || []).length}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {canEdit ? (
                          <Button size="sm" variant="secondary" onClick={() => openEdit(r)}>
                            <Pencil className="mr-1 h-4 w-4" />
                            {t('common.edit')}
                          </Button>
                        ) : null}
                        {canDelete ? (
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button size="sm" variant="destructive" disabled={r.isSystem}>
                                <Trash2 className="mr-1 h-4 w-4" />
                                {t('common.delete')}
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>{t('system.role.confirmDelete')}</AlertDialogTitle>
                                <AlertDialogDescription>{t('system.role.deleteDescription')}</AlertDialogDescription>
                                </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                                <AlertDialogAction
                                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                  onClick={async () => {
                                    if (!session) return
                                    setError(null)
                                    try {
                                      await apiFetch(`/api/v1/roles/${r.id}`, {
                                        method: 'DELETE',
                                        session,
                                        tenantId: targetTenantId,
                                      })
                                      await loadRoles()
                                    } catch (err) {
                                      setError(err instanceof ApiError ? err.message : t('system.common.deleteFailed'))
                                    }
                                  }}
                                >
                                  {t('common.delete')}
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        ) : null}
                        {!canEdit && !canDelete ? (
                          <span className="text-sm text-muted-foreground">-</span>
                        ) : null}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {!loading && (data?.list || []).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="py-6 text-center text-muted-foreground">
                      {t('common.empty')}
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>

          <SimplePagination
            total={total}
            currentPage={currentPage}
            pageSize={pageSize}
            disabled={loading}
            onChange={(p) => setPage(p)}
          />
        </CardContent>
      </Card>
    </div>
  )
}
