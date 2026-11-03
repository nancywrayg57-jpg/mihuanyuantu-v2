'use client'

import { useEffect, useMemo, useState } from 'react'
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ApiError, apiFetch } from '@/lib/api'
import { useTenant } from '@/hooks/useTenant'
import { useT } from '@/lib/i18n'
import { translateActive } from '@/lib/i18n/registry'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'

type PageResponse<T> = {
  list: T[]
  total: number
  pageSize: number
  currentPage: number
}

type MenuItem = {
  id: number
  title: string
  path?: string | null
  component?: string | null
  parentId?: number | null
  sortOrder: number
  menuType: string
  perms?: string | null
  isVisible: boolean
  isActive: boolean
  createdAt?: string | null
}

type MenuForm = {
  id?: number
  title: string
  path: string
  component: string
  parentId: number | null
  menuType: string
  perms: string
  sortOrder: string
  isVisible: boolean
  isActive: boolean
}

const emptyForm: MenuForm = {
  title: '',
  path: '',
  component: '',
  parentId: null,
  menuType: '1',
  perms: '',
  sortOrder: '0',
  isVisible: true,
  isActive: true,
}

function buildMenuOptions(items: MenuItem[]) {
  const byParent = new Map<number | null, MenuItem[]>()
  for (const item of items) {
    const pid = item.parentId ?? null
    const list = byParent.get(pid) || []
    list.push(item)
    byParent.set(pid, list)
  }
  for (const [k, list] of byParent.entries()) {
    byParent.set(
      k,
      list.sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0)),
    )
  }

  const out: Array<{ id: number; label: string; depth: number }> = []
  function dfs(parentId: number | null, depth: number) {
    const children = byParent.get(parentId) || []
    for (const child of children) {
      out.push({ id: child.id, label: child.title, depth })
      dfs(child.id, depth + 1)
    }
  }
  dfs(null, 0)
  return out
}

function menuTypeLabel(menuType: string) {
  switch (menuType) {
    case '0':
      return translateActive('system.menu.directory')
    case '1':
      return translateActive('system.menu.menu')
    case '2':
      return translateActive('system.menu.button')
    default:
      return menuType
  }
}

export default function MenusPage() {
  const t = useT()
  const { session } = useAuth()
  const { targetTenantId } = useTenant()

  const [queryTitle, setQueryTitle] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<PageResponse<MenuItem> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isSuperuser = Boolean(session?.isSuperuser)

  const menuOptions = useMemo(() => buildMenuOptions(data?.list || []), [data?.list])

  async function load() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      // 菜单行逐租户一份，四个请求都要带目标租户，否则超管切了租户
      // 看到/改到的仍是自己那份。后端已按租户隔离，不带只会看错、不会串数据。
      const res = await apiFetch<PageResponse<MenuItem>>('/api/v1/menus', {
        method: 'POST',
        session,
        tenantId: targetTenantId,
        body: JSON.stringify({
          currentPage: page,
          pageSize: 200,
          title: queryTitle || undefined,
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
    // 切租户要重新拉：菜单逐租户一份，不重拉就还显示上一个租户的
  }, [page, session?.accessToken, targetTenantId])

  const total = data?.total ?? 0
  const pageSize = data?.pageSize ?? 10
  const currentPage = data?.currentPage ?? page

  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create')
  const [form, setForm] = useState<MenuForm>(emptyForm)
  const [dialogError, setDialogError] = useState<string | null>(null)

  function openCreate() {
    setDialogMode('create')
    setForm(emptyForm)
    setDialogError(null)
    setDialogOpen(true)
  }

  function openEdit(item: MenuItem) {
    setDialogMode('edit')
    setDialogError(null)
    setForm({
      id: item.id,
      title: item.title,
      path: item.path || '',
      component: item.component || '',
      parentId: item.parentId ?? null,
      menuType: item.menuType,
      perms: item.perms || '',
      sortOrder: String(item.sortOrder ?? 0),
      isVisible: item.isVisible,
      isActive: item.isActive,
    })
    setDialogOpen(true)
  }

  if (!isSuperuser) {
    return (
      <Card>
        <CardHeader>
          <PageHeader title={t('system.menu.title')} description={t('system.menu.adminOnly')} />
        </CardHeader>
      </Card>
    )
  }

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <PageHeader title={t('system.menu.title')} description={t('system.menu.description')} />
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="flex flex-1 items-center gap-2">
              <Input value={queryTitle} onChange={(e) => setQueryTitle(e.target.value)} placeholder={t('system.menu.searchPlaceholder')} />
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

            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button onClick={openCreate}>
                  <Plus className="mr-2 h-4 w-4" />
                  {t('system.menu.create')}
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-3xl">
                <DialogHeader>
                  <DialogTitle>{dialogMode === 'create' ? t('system.menu.create') : t('system.menu.edit')}</DialogTitle>
                  <DialogDescription>{t('system.menu.dialogDescription')}</DialogDescription>
                </DialogHeader>
                {dialogError ? <div className="text-sm text-destructive">{dialogError}</div> : null}
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="grid gap-2 md:col-span-2">
                    <Label>{t('system.menu.titleField')}</Label>
                    <Input value={form.title} onChange={(e) => setForm((s) => ({ ...s, title: e.target.value }))} />
                  </div>
                  {form.menuType !== '2' ? (
                    <>
                      <div className="grid gap-2">
                        <Label>{t('system.menu.pathField')}</Label>
                        <Input value={form.path} onChange={(e) => setForm((s) => ({ ...s, path: e.target.value }))} placeholder="/system/xxx" />
                      </div>
                      <div className="grid gap-2">
                        <Label>{t('system.menu.componentField')}</Label>
                        <Input value={form.component} onChange={(e) => setForm((s) => ({ ...s, component: e.target.value }))} placeholder="views/system/xxx" />
                      </div>
                    </>
                  ) : null}
                  <div className="grid gap-2">
                    <Label>{t('system.menu.typeField')}</Label>
                    <Select
                      value={form.menuType}
                      onValueChange={(v) =>
                        setForm((s) => ({
                          ...s,
                          menuType: v,
                          path: v === '2' ? '' : s.path,
                          component: v === '2' ? '' : s.component,
                          perms: v === '2' ? s.perms : '',
                        }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="0">{t('system.menu.directory')}</SelectItem>
                        <SelectItem value="1">{t('system.menu.menu')}</SelectItem>
                        <SelectItem value="2">{t('system.menu.button')}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <Label>{t('system.menu.sortField')}</Label>
                    <Input value={form.sortOrder} onChange={(e) => setForm((s) => ({ ...s, sortOrder: e.target.value }))} />
                  </div>
                  <div className="grid gap-2 md:col-span-2">
                    <Label>{t('system.menu.parentField')}</Label>
                    <Select
                      value={form.parentId ? String(form.parentId) : '0'}
                      onValueChange={(v) => setForm((s) => ({ ...s, parentId: v === '0' ? null : Number(v) }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={t('system.menu.rootPlaceholder')} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="0">{t('system.menu.rootOption')}</SelectItem>
                        {menuOptions.map((o) => (
                          <SelectItem key={o.id} value={String(o.id)} disabled={form.id ? o.id === form.id : false}>
                            <span className={cn(o.depth ? 'pl-4' : '', 'truncate')}>
                              {o.depth ? `${'—'.repeat(o.depth)} ` : ''}
                              {o.label}
                            </span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  {form.menuType === '2' ? (
                    <div className="grid gap-2 md:col-span-2">
                      <Label>{t('system.menu.permsField')}</Label>
                      <Input value={form.perms} onChange={(e) => setForm((s) => ({ ...s, perms: e.target.value }))} placeholder="user:read / role:create ..." />
                      <div className="text-xs text-muted-foreground">{t('system.menu.permsHint')}</div>
                    </div>
                  ) : null}
                  {form.menuType !== '2' ? (
                    <>
                      <label className="flex items-center gap-2 text-sm">
                        <Checkbox checked={form.isVisible} onCheckedChange={(v) => setForm((s) => ({ ...s, isVisible: Boolean(v) }))} />
                        {t('system.menu.visible')}
                      </label>
                      <label className="flex items-center gap-2 text-sm">
                        <Checkbox checked={form.isActive} onCheckedChange={(v) => setForm((s) => ({ ...s, isActive: Boolean(v) }))} />
                        {t('system.menu.active')}
                      </label>
                    </>
                  ) : (
                    <label className="flex items-center gap-2 text-sm md:col-span-2">
                      <Checkbox checked={form.isActive} onCheckedChange={(v) => setForm((s) => ({ ...s, isActive: Boolean(v) }))} />
                      {t('system.menu.buttonActive')}
                    </label>
                  )}
                </div>
                <DialogFooter>
                  <Button
                    onClick={async () => {
                      if (!session) return
                      setDialogError(null)
                      try {
                        const payload = {
                          title: form.title,
                          path: form.path || undefined,
                          component: form.component || undefined,
                          parentId: form.parentId || undefined,
                          menuType: form.menuType,
                          perms: form.perms || undefined,
                          sortOrder: Number(form.sortOrder) || 0,
                          isVisible: form.isVisible,
                          isActive: form.isActive,
                        }
                        if (dialogMode === 'create') {
                          await apiFetch('/api/v1/menus/create', {
                            method: 'POST',
                            session,
                            tenantId: targetTenantId,
                            body: JSON.stringify(payload),
                          })
                        } else if (form.id) {
                          await apiFetch(`/api/v1/menus/${form.id}`, {
                            method: 'PUT',
                            session,
                            tenantId: targetTenantId,
                            body: JSON.stringify(payload),
                          })
                        }
                        setDialogOpen(false)
                        await load()
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

          {error ? <div className="text-sm text-destructive">{error}</div> : null}

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="hidden w-[80px] md:table-cell">ID</TableHead>
                  <TableHead>{t('system.common.title')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('system.common.path')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('system.menu.permission')}</TableHead>
                  <TableHead>{t('system.common.type')}</TableHead>
                  <TableHead>{t('common.status')}</TableHead>
                  <TableHead className="w-[150px]">{t('common.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.list || []).map((m) => (
                  <TableRow key={m.id}>
                    <TableCell className="hidden md:table-cell">{m.id}</TableCell>
                    <TableCell>
                      <div className="font-medium">{m.title}</div>
                      <div className="text-xs text-muted-foreground md:hidden">{m.path || '-'}</div>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">{m.path || '-'}</TableCell>
                    <TableCell className="hidden md:table-cell">{m.perms || '-'}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{menuTypeLabel(m.menuType)}</Badge>
                    </TableCell>
                    <TableCell>
                      {m.isActive ? <Badge variant="secondary">{t('common.enabled')}</Badge> : <Badge variant="outline">{t('common.disabled')}</Badge>}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Button size="sm" variant="secondary" onClick={() => openEdit(m)}>
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
                              <AlertDialogTitle>{t('system.menu.confirmDelete')}</AlertDialogTitle>
                              <AlertDialogDescription>{t('system.menu.deleteDescription')}</AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                              <AlertDialogAction
                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                onClick={async () => {
                                  if (!session) return
                                  setError(null)
                                  try {
                                    await apiFetch(`/api/v1/menus/${m.id}`, {
                                      method: 'DELETE',
                                      session,
                                      tenantId: targetTenantId,
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
