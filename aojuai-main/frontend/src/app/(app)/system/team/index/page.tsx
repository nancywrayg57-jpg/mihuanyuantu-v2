'use client'

import { useEffect, useMemo, useState } from 'react'
import { Pencil, Plus, RefreshCcw, Trash2 } from 'lucide-react'

import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, apiFetch } from '@/lib/api'
import { hasAnyPermission } from '@/lib/auth'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'

type TeamNode = {
  id: number
  name: string
  code: string
  status: number
  sortOrder?: number | null
  description?: string | null
  parentId?: number | null
  children?: TeamNode[]
}

type TeamOption = {
  value: number
  label: string
  disabled?: boolean
  children?: TeamOption[]
}

type FlattenedTeam = TeamNode & { depth: number }

function flattenTree(nodes: TeamNode[], depth = 0): FlattenedTeam[] {
  const out: FlattenedTeam[] = []
  for (const n of nodes) {
    out.push({ ...n, depth })
    if (n.children?.length) out.push(...flattenTree(n.children, depth + 1))
  }
  return out
}

function flattenOptions(nodes: TeamOption[], depth = 0): Array<{ value: number; label: string; depth: number; disabled: boolean }> {
  const out: Array<{ value: number; label: string; depth: number; disabled: boolean }> = []
  for (const n of nodes) {
    out.push({ value: n.value, label: n.label, depth, disabled: Boolean(n.disabled) })
    if (n.children?.length) out.push(...flattenOptions(n.children, depth + 1))
  }
  return out
}

type TeamForm = {
  id?: number
  name: string
  code: string
  status: number
  sortOrder: string
  parentId: number | null
  description: string
}

const emptyForm: TeamForm = {
  name: '',
  code: '',
  status: 1,
  sortOrder: '0',
  parentId: null,
  description: '',
}

export default function TeamsPage() {
  const t = useT()
  const { session } = useAuth()
  const { targetTenantId } = useTenant()

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tree, setTree] = useState<TeamNode[]>([])
  const [options, setOptions] = useState<TeamOption[]>([])

  const flatTeams = useMemo(() => flattenTree(tree), [tree])
  const flatOptions = useMemo(() => flattenOptions(options), [options])

  const canCreate = hasAnyPermission(session, ['team:create'])
  const canEdit = hasAnyPermission(session, ['team:update'])
  const canDelete = hasAnyPermission(session, ['team:delete'])

  async function load() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const [t, o] = await Promise.all([
        apiFetch<TeamNode[]>('/api/v1/teams/tree', { session, tenantId: targetTenantId }),
        apiFetch<TeamOption[]>('/api/v1/teams/options', { session, tenantId: targetTenantId }),
      ])
      setTree(t)
      setOptions(o)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('system.common.loadFailed'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken, targetTenantId])

  const [dialogOpen, setDialogOpen] = useState(false)
  const [form, setForm] = useState<TeamForm>(emptyForm)

  function openCreate() {
    setForm(emptyForm)
    setDialogOpen(true)
  }

  function openEdit(team: FlattenedTeam) {
    setForm({
      id: team.id,
      name: team.name,
      code: team.code,
      status: team.status,
      sortOrder: String(team.sortOrder ?? 0),
      parentId: team.parentId ?? null,
      description: team.description || '',
    })
    setDialogOpen(true)
  }

  if (!session) return null

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>{t('system.team.title')}</CardTitle>
          <CardDescription>{t('system.team.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="flex flex-1 items-center gap-2">
              <Button variant="outline" onClick={load} disabled={loading}>
                <RefreshCcw className="mr-2 h-4 w-4" />
                {t('common.refresh')}
              </Button>
              {error ? <div className="text-sm text-destructive">{error}</div> : null}
            </div>
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              {canCreate ? (
                <DialogTrigger asChild>
                  <Button onClick={openCreate}>
                    <Plus className="mr-2 h-4 w-4" />
                    {t('system.team.create')}
                  </Button>
                </DialogTrigger>
              ) : null}
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>{form.id ? t('system.team.edit') : t('system.team.create')}</DialogTitle>
                  <DialogDescription>{t('system.team.dialogDescription')}</DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label>{t('system.team.name')}</Label>
                    <Input value={form.name} onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))} />
                  </div>
                  <div className="grid gap-2">
                    <Label>{t('system.team.code')}</Label>
                    <Input value={form.code} onChange={(e) => setForm((s) => ({ ...s, code: e.target.value }))} />
                  </div>
                  <div className="grid gap-2">
                    <Label>{t('common.status')}</Label>
                    <Select value={String(form.status)} onValueChange={(v) => setForm((s) => ({ ...s, status: Number(v) }))}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1">{t('common.enabled')}</SelectItem>
                        <SelectItem value="0">{t('common.disabled')}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <Label>{t('system.common.sort')}</Label>
                    <Input value={form.sortOrder} onChange={(e) => setForm((s) => ({ ...s, sortOrder: e.target.value }))} />
                  </div>
                  <div className="grid gap-2 md:col-span-2">
                    <Label>{t('system.team.parent')}</Label>
                    <Select
                      value={form.parentId ? String(form.parentId) : '0'}
                      onValueChange={(v) =>
                        setForm((s) => ({ ...s, parentId: v === '0' ? null : Number(v) }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={t('system.team.rootPlaceholder')} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="0">{t('system.team.rootOption')}</SelectItem>
                        {flatOptions.map((o) => (
                          <SelectItem key={o.value} value={String(o.value)} disabled={o.disabled || (form.id ? o.value === form.id : false)}>
                            <span className={cn(o.depth ? 'pl-4' : '', 'truncate')}>
                              {o.depth ? `${'—'.repeat(o.depth)} ` : ''}
                              {o.label}
                            </span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2 md:col-span-2">
                    <Label>{t('common.description')}</Label>
                    <Textarea value={form.description} onChange={(e) => setForm((s) => ({ ...s, description: e.target.value }))} />
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    onClick={async () => {
                      if (!session) return
                      setError(null)
                      try {
                        const parentIdValue = form.id ? (form.parentId ?? 0) : (form.parentId ?? undefined)
                        const payload = {
                          name: form.name,
                          code: form.code,
                          status: form.status,
                          sort_order: Number(form.sortOrder) || 0,
                          parent_id: parentIdValue,
                          description: form.description || undefined,
                        }
                        if (form.id) {
                          await apiFetch(`/api/v1/teams/${form.id}`, {
                            method: 'PUT',
                            session,
                            tenantId: targetTenantId,
                            body: JSON.stringify(payload),
                          })
                        } else {
                          await apiFetch('/api/v1/teams', {
                            method: 'POST',
                            session,
                            tenantId: targetTenantId,
                            body: JSON.stringify(payload),
                          })
                        }
                        setDialogOpen(false)
                        await load()
                      } catch (err) {
                        setError(err instanceof ApiError ? err.message : t('system.common.saveFailed'))
                      }
                    }}
                  >
                    {t('common.save')}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="hidden w-[80px] md:table-cell">ID</TableHead>
                  <TableHead>{t('system.common.team')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('system.common.code')}</TableHead>
                  <TableHead>{t('common.status')}</TableHead>
                  <TableHead className="w-[140px]">{t('common.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {flatTeams.map((team) => (
                  <TableRow key={team.id}>
                    <TableCell className="hidden md:table-cell">{team.id}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="truncate font-medium" style={{ paddingLeft: `${team.depth * 12}px` }}>
                          {team.name}
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground md:hidden">{team.code}</div>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">{team.code}</TableCell>
                    <TableCell>
                      {team.status === 1 ? <Badge variant="secondary">{t('common.enabled')}</Badge> : <Badge variant="outline">{t('common.disabled')}</Badge>}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {canEdit ? (
                          <Button size="sm" variant="secondary" onClick={() => openEdit(team)}>
                            <Pencil className="mr-1 h-4 w-4" />
                            {t('common.edit')}
                          </Button>
                        ) : null}
                        {canDelete ? (
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button size="sm" variant="destructive">
                                <Trash2 className="mr-1 h-4 w-4" />
                                {t('common.delete')}
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>{t('system.team.confirmDelete')}</AlertDialogTitle>
                                <AlertDialogDescription>{t('system.team.deleteDescription')}</AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                                <AlertDialogAction
                                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                  onClick={async () => {
                                    if (!session) return
                                    setError(null)
                                    try {
                                      await apiFetch(`/api/v1/teams/${team.id}`, {
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
                        ) : null}
                        {!canEdit && !canDelete ? (
                          <span className="text-sm text-muted-foreground">-</span>
                        ) : null}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {!loading && flatTeams.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="py-6 text-center text-muted-foreground">
                      {t('system.common.noTeams')}
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
