'use client'

import { useEffect, useState } from 'react'
import { Pencil, Plus, RefreshCcw, Trash2 } from 'lucide-react'

import { SimplePagination } from '@/components/list/simple-pagination'
import { PageHeader } from '@/components/page/page-header'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, apiFetch } from '@/lib/api'
import { useT } from '@/lib/i18n'
import { useAuth } from '@/hooks/useAuth'

type PageResponse<T> = {
  list: T[]
  total: number
  pageSize: number
  currentPage: number
}

type TenantListItem = {
  id: number
  name: string
  code: string
  domain?: string | null
  description?: string | null
  isActive: boolean
  expiresAt?: string | null
  contactName?: string | null
  contactPhone?: string | null
  contactEmail?: string | null
  createdAt?: string | null
}

type TenantDetail = TenantListItem & {
  config?: {
    registration?: {
      enabled?: boolean
      requireAudit?: boolean
      defaultRole?: string
    }
  }
}

type TenantCreatePayload = {
  name: string
  code: string
  description?: string
  isActive: boolean
  initialAdmin?: {
    username: string
    password: string
    nickname?: string
    email?: string
    phone?: string
  }
}

export default function TenantsPage() {
  const t = useT()
  const { session } = useAuth()

  const [queryName, setQueryName] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<PageResponse<TenantListItem> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canManage = Boolean(session?.isSuperuser)

  async function load() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch<PageResponse<TenantListItem>>('/api/v1/tenants', {
        method: 'POST',
        session,
        body: JSON.stringify({
          currentPage: page,
          pageSize: 10,
          name: queryName || undefined,
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
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, session?.accessToken])

  const total = data?.total ?? 0
  const pageSize = data?.pageSize ?? 10
  const currentPage = data?.currentPage ?? page

  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState<TenantCreatePayload>({
    name: '',
    code: '',
    description: '',
    isActive: true,
  })
  const [createWithAdmin, setCreateWithAdmin] = useState(false)
  const [createAdmin, setCreateAdmin] = useState({
    username: '',
    password: '',
    nickname: '',
    email: '',
    phone: '',
  })

  const [editOpen, setEditOpen] = useState(false)
  const [editLoading, setEditLoading] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [editingTenant, setEditingTenant] = useState<TenantDetail | null>(null)

  async function openEdit(tenantId: number) {
    if (!session) return
    setEditOpen(true)
    setEditLoading(true)
    setEditError(null)
    try {
      const detail = await apiFetch<TenantDetail>(`/api/v1/tenants/${tenantId}`, {
        session,
      })
      setEditingTenant(detail)
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : t('system.tenantList.loadDetailFailed'))
    } finally {
      setEditLoading(false)
    }
  }

  if (!canManage) {
    return (
      <Card>
        <CardHeader>
          <PageHeader title={t('system.tenantList.title')} description={t('system.menu.adminOnly')} />
        </CardHeader>
      </Card>
    )
  }

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <PageHeader title={t('system.tenantList.title')} description={t('system.tenantList.description')} />
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="flex flex-1 items-center gap-2">
              <Input
                value={queryName}
                onChange={(e) => setQueryName(e.target.value)}
                placeholder={t('system.tenantList.searchPlaceholder')}
              />
              <Button
                variant="secondary"
                onClick={() => {
                  setPage(1)
                  void load()
                }}
                disabled={loading}
              >
                {t('common.search')}
              </Button>
              <Button variant="outline" onClick={load} disabled={loading}>
                <RefreshCcw className="mr-2 h-4 w-4" />
                {t('common.refresh')}
              </Button>
            </div>

            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  {t('system.tenantList.create')}
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>{t('system.tenantList.create')}</DialogTitle>
                  <DialogDescription>{t('system.tenantList.createDescription')}</DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label>{t('system.tenantSettings.tenantName')}</Label>
                    <Input
                      value={createForm.name}
                      onChange={(e) => setCreateForm((s) => ({ ...s, name: e.target.value }))}
                      placeholder={t('system.tenantList.tenantNamePlaceholder')}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>{t('system.tenantList.tenantCode')}</Label>
                    <Input
                      value={createForm.code}
                      onChange={(e) => setCreateForm((s) => ({ ...s, code: e.target.value }))}
                      placeholder={t('system.auth.tenantCodePlaceholder')}
                    />
                  </div>
                  <div className="grid gap-2 md:col-span-2">
                    <Label>{t('common.description')}</Label>
                    <Textarea
                      value={createForm.description || ''}
                      onChange={(e) => setCreateForm((s) => ({ ...s, description: e.target.value }))}
                      placeholder={t('system.auth.optional')}
                    />
                  </div>

                  <label className="flex items-center gap-2 text-sm md:col-span-2">
                    <Checkbox
                      checked={createForm.isActive}
                      onCheckedChange={(v) => setCreateForm((s) => ({ ...s, isActive: Boolean(v) }))}
                    />
                    {t('system.tenantList.enableTenant')}
                  </label>

                  <label className="flex items-center gap-2 text-sm md:col-span-2">
                    <Checkbox checked={createWithAdmin} onCheckedChange={(v) => setCreateWithAdmin(Boolean(v))} />
                    {t('system.tenantList.createInitialAdmin')}
                  </label>

                  {createWithAdmin ? (
                    <>
                      <div className="grid gap-2">
                        <Label>{t('system.tenantList.adminUsername')}</Label>
                        <Input
                          value={createAdmin.username}
                          onChange={(e) => setCreateAdmin((s) => ({ ...s, username: e.target.value }))}
                          placeholder={t('system.tenantList.adminUsernamePlaceholder')}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label>{t('system.tenantList.adminPassword')}</Label>
                        <Input
                          type="password"
                          value={createAdmin.password}
                          onChange={(e) => setCreateAdmin((s) => ({ ...s, password: e.target.value }))}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label>{t('system.auth.nickname')}</Label>
                        <Input
                          value={createAdmin.nickname}
                          onChange={(e) => setCreateAdmin((s) => ({ ...s, nickname: e.target.value }))}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label>Email</Label>
                        <Input
                          value={createAdmin.email}
                          onChange={(e) => setCreateAdmin((s) => ({ ...s, email: e.target.value }))}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label>{t('system.auth.phone')}</Label>
                        <Input
                          value={createAdmin.phone}
                          onChange={(e) => setCreateAdmin((s) => ({ ...s, phone: e.target.value }))}
                        />
                      </div>
                    </>
                  ) : null}
                </div>
                <DialogFooter>
                  <Button
                    onClick={async () => {
                      if (!session) return
                      setError(null)
                      try {
                        const payload: TenantCreatePayload = {
                          name: createForm.name,
                          code: createForm.code,
                          description: createForm.description || undefined,
                          isActive: createForm.isActive,
                        }
                        if (createWithAdmin) {
                          payload.initialAdmin = {
                            username: createAdmin.username,
                            password: createAdmin.password,
                            nickname: createAdmin.nickname || undefined,
                            email: createAdmin.email || undefined,
                            phone: createAdmin.phone || undefined,
                          }
                        }
                        await apiFetch('/api/v1/tenants/create', {
                          method: 'POST',
                          session,
                          body: JSON.stringify(payload),
                        })
                        setCreateOpen(false)
                        setCreateForm({ name: '', code: '', description: '', isActive: true })
                        setCreateWithAdmin(false)
                        setCreateAdmin({ username: '', password: '', nickname: '', email: '', phone: '' })
                        await load()
                      } catch (err) {
                        setError(err instanceof ApiError ? err.message : t('system.tenantList.createFailed'))
                      }
                    }}
                    disabled={loading}
                  >
                    {t('common.create')}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          {error ? <div className="text-sm text-destructive">{error}</div> : null}

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="hidden w-[80px] md:table-cell">ID</TableHead>
                  <TableHead>{t('common.name')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('system.common.code')}</TableHead>
                  <TableHead>{t('common.status')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('common.createdAt')}</TableHead>
                  <TableHead className="w-[150px]">{t('common.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.list || []).map((tenant) => (
                  <TableRow key={tenant.id}>
                    <TableCell className="hidden md:table-cell">{tenant.id}</TableCell>
                    <TableCell>
                      <div className="font-medium">{tenant.name}</div>
                      <div className="text-xs text-muted-foreground md:hidden">{tenant.code}</div>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">{tenant.code}</TableCell>
                    <TableCell>
                      {tenant.isActive ? (
                        <Badge variant="secondary">{t('common.enabled')}</Badge>
                      ) : (
                        <Badge variant="outline">{t('common.disabled')}</Badge>
                      )}
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      {tenant.createdAt ? new Date(tenant.createdAt).toLocaleString() : ''}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => void openEdit(tenant.id)}
                        >
                          <Pencil className="mr-1 h-4 w-4" />
                          {t('common.edit')}
                        </Button>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button size="sm" variant="destructive">
                              <Trash2 className="mr-1 h-4 w-4" />
                              {t('common.delete')}
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>{t('system.tenantList.confirmDelete')}</AlertDialogTitle>
                              <AlertDialogDescription>{t('system.tenantList.deleteDescription')}</AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                              <AlertDialogAction
                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                onClick={async () => {
                                  if (!session) return
                                  setError(null)
                                  try {
                                    await apiFetch(`/api/v1/tenants/${tenant.id}`, {
                                      method: 'DELETE',
                                      session,
                                    })
                                    await load()
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
                      </div>
                    </TableCell>
                  </TableRow>
                ))}

                {!loading && (data?.list || []).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="py-6 text-center text-muted-foreground">
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

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{t('system.tenantList.edit')}</DialogTitle>
            <DialogDescription>{t('system.tenantList.editDescription')}</DialogDescription>
          </DialogHeader>

          {editLoading ? (
            <div className="text-sm text-muted-foreground">{t('common.loading')}</div>
          ) : editError ? (
            <div className="text-sm text-destructive">{editError}</div>
          ) : !editingTenant ? (
            <div className="text-sm text-muted-foreground">{t('system.tenantList.noTenantSelected')}</div>
          ) : (
            <Tabs defaultValue="basic">
              <TabsList>
                <TabsTrigger value="basic">{t('system.tenantSettings.tabProfile')}</TabsTrigger>
                <TabsTrigger value="registration">{t('system.tenantSettings.tabRegistration')}</TabsTrigger>
              </TabsList>

              <TabsContent value="basic" className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label>{t('system.tenantSettings.tenantName')}</Label>
                  <Input
                    value={editingTenant.name}
                    onChange={(e) => setEditingTenant((s) => (s ? { ...s, name: e.target.value } : s))}
                  />
                </div>
                <div className="grid gap-2">
                  <Label>{t('system.tenantList.tenantCode')}</Label>
                  <Input value={editingTenant.code} disabled />
                </div>
                <div className="grid gap-2 md:col-span-2">
                  <Label>{t('system.tenantList.domain')}</Label>
                  <Input
                    value={editingTenant.domain || ''}
                    onChange={(e) => setEditingTenant((s) => (s ? { ...s, domain: e.target.value } : s))}
                    placeholder={t('system.auth.optional')}
                  />
                </div>
                <div className="grid gap-2 md:col-span-2">
                  <Label>{t('common.description')}</Label>
                  <Textarea
                    value={editingTenant.description || ''}
                    onChange={(e) => setEditingTenant((s) => (s ? { ...s, description: e.target.value } : s))}
                  />
                </div>
                <label className="flex items-center gap-2 text-sm md:col-span-2">
                  <Checkbox
                    checked={editingTenant.isActive}
                    onCheckedChange={(v) => setEditingTenant((s) => (s ? { ...s, isActive: Boolean(v) } : s))}
                  />
                  {t('system.tenantList.enableTenant')}
                </label>
                <div className="grid gap-2">
                  <Label>{t('system.tenantSettings.contactName')}</Label>
                  <Input
                    value={editingTenant.contactName || ''}
                    onChange={(e) => setEditingTenant((s) => (s ? { ...s, contactName: e.target.value } : s))}
                  />
                </div>
                <div className="grid gap-2">
                  <Label>{t('system.tenantSettings.contactPhone')}</Label>
                  <Input
                    value={editingTenant.contactPhone || ''}
                    onChange={(e) => setEditingTenant((s) => (s ? { ...s, contactPhone: e.target.value } : s))}
                  />
                </div>
                <div className="grid gap-2 md:col-span-2">
                  <Label>{t('system.tenantSettings.contactEmail')}</Label>
                  <Input
                    value={editingTenant.contactEmail || ''}
                    onChange={(e) => setEditingTenant((s) => (s ? { ...s, contactEmail: e.target.value } : s))}
                  />
                </div>
              </TabsContent>

              <TabsContent value="registration" className="grid gap-4 md:grid-cols-2">
                <label className="flex items-center gap-2 text-sm md:col-span-2">
                  <Checkbox
                    checked={editingTenant.config?.registration?.enabled ?? true}
                    onCheckedChange={(v) =>
                      setEditingTenant((s) =>
                        s
                          ? {
                              ...s,
                              config: {
                                ...(s.config || {}),
                                registration: {
                                  ...(s.config?.registration || {}),
                                  enabled: Boolean(v),
                                },
                              },
                            }
                          : s,
                      )
                    }
                  />
                  {t('system.tenantList.allowTenantRegistration')}
                </label>
                <label className="flex items-center gap-2 text-sm md:col-span-2">
                  <Checkbox
                    checked={editingTenant.config?.registration?.requireAudit ?? true}
                    onCheckedChange={(v) =>
                      setEditingTenant((s) =>
                        s
                          ? {
                              ...s,
                              config: {
                                ...(s.config || {}),
                                registration: {
                                  ...(s.config?.registration || {}),
                                  requireAudit: Boolean(v),
                                },
                              },
                            }
                          : s,
                      )
                    }
                  />
                  {t('system.tenantList.requireNewUserAudit')}
                </label>
                <div className="grid gap-2 md:col-span-2">
                  <Label>{t('system.tenantSettings.defaultRole')}</Label>
                  <Input
                    value={editingTenant.config?.registration?.defaultRole || 'user'}
                    onChange={(e) =>
                      setEditingTenant((s) =>
                        s
                          ? {
                              ...s,
                              config: {
                                ...(s.config || {}),
                                registration: {
                                  ...(s.config?.registration || {}),
                                  defaultRole: e.target.value,
                                },
                              },
                            }
                          : s,
                      )
                    }
                  />
                </div>
              </TabsContent>
            </Tabs>
          )}

          <DialogFooter>
            <Button
              variant="secondary"
              onClick={() => setEditOpen(false)}
              disabled={editLoading}
            >
              {t('common.close')}
            </Button>
            <Button
              onClick={async () => {
                if (!session || !editingTenant) return
                setEditError(null)
                try {
                  await apiFetch(`/api/v1/tenants/${editingTenant.id}`, {
                    method: 'PUT',
                    session,
                    body: JSON.stringify({
                      name: editingTenant.name,
                      domain: editingTenant.domain || undefined,
                      description: editingTenant.description || undefined,
                      isActive: editingTenant.isActive,
                      contactName: editingTenant.contactName || undefined,
                      contactPhone: editingTenant.contactPhone || undefined,
                      contactEmail: editingTenant.contactEmail || undefined,
                    }),
                  })

                  await apiFetch(`/api/v1/tenants/${editingTenant.id}/registration`, {
                    method: 'PUT',
                    session,
                    body: JSON.stringify({
                      enabled: editingTenant.config?.registration?.enabled ?? true,
                      requireAudit: editingTenant.config?.registration?.requireAudit ?? true,
                      defaultRole: editingTenant.config?.registration?.defaultRole || 'user',
                    }),
                  })

                  setEditOpen(false)
                  await load()
                } catch (err) {
                  setEditError(err instanceof ApiError ? err.message : t('system.common.saveFailed'))
                }
              }}
              disabled={editLoading || !editingTenant}
            >
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
