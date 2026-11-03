'use client'

import { useMemo, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'

import { CollapsibleFilters } from '@/components/list/collapsible-filters'
import { FilterGrid } from '@/components/list/filter-grid'
import { SimplePagination } from '@/components/list/simple-pagination'
import { PageHeader } from '@/components/page/page-header'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { useT } from '@/lib/i18n'

type TenantPackage = {
  id: number
  name: string
  status: 'enabled' | 'disabled'
  quota: string
  remark: string
  createdAt: string
}

const now = () => new Date().toISOString()

function createInitialPackages(t: ReturnType<typeof useT>): TenantPackage[] {
  return [
    { id: 1, name: t('system.tenantPackage.basic'), status: 'enabled', quota: t('system.tenantPackage.quotaBasic'), remark: '', createdAt: now() },
    { id: 2, name: t('system.tenantPackage.pro'), status: 'enabled', quota: t('system.tenantPackage.quotaPro'), remark: t('system.tenantPackage.moreQuota'), createdAt: now() },
    { id: 3, name: t('system.tenantPackage.enterprise'), status: 'disabled', quota: t('system.tenantPackage.quotaEnterprise'), remark: t('system.tenantPackage.contactSales'), createdAt: now() },
  ]
}

export default function TenantPackagePage() {
  const t = useT()
  const [packages, setPackages] = useState<TenantPackage[]>(() => createInitialPackages(t))

  const [qName, setQName] = useState('')
  const [qStatus, setQStatus] = useState<'all' | 'enabled' | 'disabled'>('all')

  const [page, setPage] = useState(1)
  const pageSize = 10

  const filtered = useMemo(() => {
    const name = qName.trim().toLowerCase()
    return packages
      .filter((p) => (!name ? true : p.name.toLowerCase().includes(name)))
      .filter((p) => (qStatus === 'all' ? true : p.status === qStatus))
      .slice()
      .sort((a, b) => a.id - b.id)
  }, [packages, qName, qStatus])

  const paged = useMemo(() => {
    const start = (page - 1) * pageSize
    return filtered.slice(start, start + pageSize)
  }, [filtered, page])

  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create')
  const [editId, setEditId] = useState<number | null>(null)
  const [fName, setFName] = useState('')
  const [fStatus, setFStatus] = useState<'enabled' | 'disabled'>('enabled')
  const [fQuota, setFQuota] = useState('')
  const [fRemark, setFRemark] = useState('')

  const openCreate = () => {
    setDialogMode('create')
    setEditId(null)
    setFName('')
    setFStatus('enabled')
    setFQuota('')
    setFRemark('')
    setDialogOpen(true)
  }

  const openEdit = (p: TenantPackage) => {
    setDialogMode('edit')
    setEditId(p.id)
    setFName(p.name)
    setFStatus(p.status)
    setFQuota(p.quota)
    setFRemark(p.remark)
    setDialogOpen(true)
  }

  const save = () => {
    if (!fName.trim()) return
    if (dialogMode === 'create') {
      const nextId = Math.max(0, ...packages.map((p) => p.id)) + 1
      setPackages((prev) => [
        ...prev,
        { id: nextId, name: fName.trim(), status: fStatus, quota: fQuota.trim(), remark: fRemark.trim(), createdAt: now() },
      ])
    } else if (editId != null) {
      setPackages((prev) =>
        prev.map((p) =>
          p.id === editId ? { ...p, name: fName.trim(), status: fStatus, quota: fQuota.trim(), remark: fRemark.trim() } : p,
        ),
      )
    }
    setDialogOpen(false)
  }

  const remove = (id: number) => setPackages((prev) => prev.filter((p) => p.id !== id))

  return (
    <div className="grid gap-4">
      <PageHeader
        title={t('system.tenantPackage.title')}
        description={t('system.tenantPackage.description')}
        actions={<Badge variant="outline">Demo</Badge>}
      />

      <PageHeader
        title={t('system.tenantPackage.listTitle')}
        description={t('system.tenantPackage.listDescription')}
        actions={
          <Button onClick={openCreate}>
            <Plus className="mr-2 h-4 w-4" />
            {t('system.tenantPackage.create')}
          </Button>
        }
      />
      <Card>
        <CardContent className="grid gap-4">
          <CollapsibleFilters>
            <FilterGrid>
              <div className="grid gap-2">
                <Label htmlFor="qName">{t('system.tenantPackage.packageName')}</Label>
                <Input
                  id="qName"
                  value={qName}
                  onChange={(e) => {
                    setQName(e.target.value)
                    setPage(1)
                  }}
                  placeholder={t('system.tenantPackage.namePlaceholder')}
                />
              </div>
              <div className="grid gap-2">
                <Label>{t('common.status')}</Label>
                <Select
                  value={qStatus}
                  onValueChange={(v) => {
                    setQStatus(v as 'all' | 'enabled' | 'disabled')
                    setPage(1)
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('common.all')}</SelectItem>
                    <SelectItem value="enabled">{t('system.tenantPackage.enabledStatus')}</SelectItem>
                    <SelectItem value="disabled">{t('system.tenantPackage.disabledStatus')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setQName('')
                    setQStatus('all')
                    setPage(1)
                  }}
                >
                  {t('common.reset')}
                </Button>
              </div>
            </FilterGrid>
          </CollapsibleFilters>

          <div className="hidden md:block">
            <div className="overflow-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[80px]">ID</TableHead>
                    <TableHead className="w-[200px]">{t('common.name')}</TableHead>
                    <TableHead className="w-[110px]">{t('common.status')}</TableHead>
                    <TableHead className="w-[240px]">{t('system.tenantPackage.quota')}</TableHead>
                    <TableHead>{t('system.common.remark')}</TableHead>
                    <TableHead className="w-[140px] text-right">{t('common.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paged.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell className="font-mono text-xs text-muted-foreground">{p.id}</TableCell>
                      <TableCell className="font-medium">{p.name}</TableCell>
                      <TableCell>
                        <Badge variant={p.status === 'enabled' ? 'secondary' : 'outline'}>
                          {p.status === 'enabled' ? t('common.enabled') : t('system.tenantPackage.disabledVerb')}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">{p.quota || '-'}</TableCell>
                      <TableCell className="max-w-[420px] truncate text-sm text-muted-foreground">{p.remark || '-'}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button variant="outline" size="sm" onClick={() => openEdit(p)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button variant="destructive" size="sm">
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>{t('system.tenantPackage.confirmDelete')}</AlertDialogTitle>
                                <AlertDialogDescription>{t('system.tenantPackage.deleteDescription').replace('{name}', p.name)}</AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                                <AlertDialogAction onClick={() => remove(p.id)}>{t('common.delete')}</AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {paged.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                        {t('common.empty')}
                      </TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </div>
          </div>

          <div className="grid gap-3 md:hidden">
            {paged.map((p) => (
              <Card key={p.id}>
                <CardContent className="grid gap-2 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate font-medium">{p.name}</div>
                      <div className="text-xs text-muted-foreground">ID: {p.id}</div>
                    </div>
                    <Badge variant={p.status === 'enabled' ? 'secondary' : 'outline'}>
                      {p.status === 'enabled' ? t('common.enabled') : t('system.tenantPackage.disabledVerb')}
                    </Badge>
                  </div>
                  <div className="text-sm text-muted-foreground">{p.quota || '-'}</div>
                  {p.remark ? <div className="text-sm text-muted-foreground">{p.remark}</div> : null}
                  <div className="flex gap-2 pt-1">
                    <Button variant="outline" size="sm" onClick={() => openEdit(p)} className="flex-1">
                      {t('common.edit')}
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="destructive" size="sm" className="flex-1">
                          {t('common.delete')}
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>{t('system.tenantPackage.confirmDelete')}</AlertDialogTitle>
                          <AlertDialogDescription>{t('system.tenantPackage.deleteDescription').replace('{name}', p.name)}</AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                          <AlertDialogAction onClick={() => remove(p.id)}>{t('common.delete')}</AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </CardContent>
              </Card>
            ))}
            {paged.length === 0 ? <div className="py-6 text-center text-sm text-muted-foreground">{t('common.empty')}</div> : null}
          </div>

          <SimplePagination total={filtered.length} currentPage={page} pageSize={pageSize} onChange={setPage} />
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{dialogMode === 'create' ? t('system.tenantPackage.create') : t('system.tenantPackage.edit')}</DialogTitle>
            <DialogDescription>{t('system.dict.formDescription')}</DialogDescription>
          </DialogHeader>

          <div className="grid gap-3">
            <div className="grid gap-2">
              <Label htmlFor="name">{t('common.name')}</Label>
              <Input id="name" value={fName} onChange={(e) => setFName(e.target.value)} placeholder={t('system.tenantPackage.nameExample')} />
            </div>
            <div className="grid gap-2">
              <Label>{t('common.status')}</Label>
              <Select value={fStatus} onValueChange={(v) => setFStatus(v as 'enabled' | 'disabled')}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="enabled">{t('common.enabled')}</SelectItem>
                  <SelectItem value="disabled">{t('system.tenantPackage.disabledVerb')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="quota">{t('system.tenantPackage.quota')}</Label>
              <Input
                id="quota"
                value={fQuota}
                onChange={(e) => setFQuota(e.target.value)}
                placeholder={t('system.tenantPackage.quotaExample')}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="remark">{t('system.common.remark')}</Label>
              <Textarea id="remark" value={fRemark} onChange={(e) => setFRemark(e.target.value)} rows={3} />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={save} disabled={!fName.trim()}>
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
