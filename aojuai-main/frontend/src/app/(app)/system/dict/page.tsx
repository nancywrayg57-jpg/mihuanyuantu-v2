'use client'

import { useMemo, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'

import { CollapsibleFilters } from '@/components/list/collapsible-filters'
import { FilterGrid } from '@/components/list/filter-grid'
import { SimplePagination } from '@/components/list/simple-pagination'
import { PageHeader } from '@/components/page/page-header'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'

type DictNode = {
  id: string
  name: string
  code: string
  children?: DictNode[]
}

type DictEntry = {
  id: string
  dictId: string
  label: string
  value: string
  status: 'enabled' | 'disabled'
  sort: number
  remark: string
  createdAt: string
}

const now = () => new Date().toISOString()

function createInitialDicts(t: (key: string) => string): DictNode[] {
  return [
    {
      id: 'sys',
      name: t('system.dict.systemDict'),
      code: 'system',
      children: [
        { id: 'user_status', name: t('system.dict.userStatus'), code: 'user_status' },
        { id: 'menu_type', name: t('system.dict.menuType'), code: 'menu_type' },
      ],
    },
    {
      id: 'biz',
      name: t('system.dict.businessDict'),
      code: 'business',
      children: [
        { id: 'order_status', name: t('system.dict.orderStatus'), code: 'order_status' },
        { id: 'attendance_mode', name: t('system.dict.attendanceMode'), code: 'attendance_mode' },
      ],
    },
  ]
}

function createInitialEntries(t: (key: string) => string): DictEntry[] {
  return [
    { id: '1', dictId: 'user_status', label: t('common.disabled'), value: '0', status: 'enabled', sort: 1, remark: '', createdAt: now() },
    { id: '2', dictId: 'user_status', label: t('system.dict.normal'), value: '1', status: 'enabled', sort: 2, remark: '', createdAt: now() },
    { id: '3', dictId: 'menu_type', label: t('system.menu.menu'), value: '0', status: 'enabled', sort: 1, remark: '', createdAt: now() },
    { id: '4', dictId: 'menu_type', label: t('system.menu.button'), value: '3', status: 'enabled', sort: 2, remark: '', createdAt: now() },
    { id: '5', dictId: 'order_status', label: t('system.dict.pendingPayment'), value: 'pending', status: 'enabled', sort: 1, remark: '', createdAt: now() },
    { id: '6', dictId: 'order_status', label: t('system.dict.paid'), value: 'paid', status: 'enabled', sort: 2, remark: '', createdAt: now() },
  ]
}

function flattenDictTree(nodes: DictNode[], depth = 0): Array<{ node: DictNode; depth: number }> {
  const out: Array<{ node: DictNode; depth: number }> = []
  for (const n of nodes) {
    out.push({ node: n, depth })
    if (n.children?.length) out.push(...flattenDictTree(n.children, depth + 1))
  }
  return out
}

function randomId() {
  return Math.random().toString(36).slice(2, 10)
}

export default function DictPage() {
  const t = useT()
  const isMobile = useIsMobile()

  const [dictSearch, setDictSearch] = useState('')
  const [dicts] = useState<DictNode[]>(() => createInitialDicts(t))
  const flatDicts = useMemo(() => flattenDictTree(dicts), [dicts])

  const visibleDicts = useMemo(() => {
    const q = dictSearch.trim().toLowerCase()
    if (!q) return flatDicts
    return flatDicts.filter(({ node }) => `${node.name} ${node.code}`.toLowerCase().includes(q))
  }, [dictSearch, flatDicts])

  const [selectedDictId, setSelectedDictId] = useState<string>(() => {
    const firstLeaf = visibleDicts.find((d) => !d.node.children?.length)
    return firstLeaf?.node.id || 'user_status'
  })

  const selectedDict = useMemo(() => {
    const item = flatDicts.find((d) => d.node.id === selectedDictId)
    return item?.node || null
  }, [flatDicts, selectedDictId])

  const [entrySearch, setEntrySearch] = useState('')
  const [entries, setEntries] = useState<DictEntry[]>(() => createInitialEntries(t))
  const [page, setPage] = useState(1)

  const filteredEntries = useMemo(() => {
    const q = entrySearch.trim().toLowerCase()
    return entries
      .filter((e) => e.dictId === selectedDictId)
      .filter((e) => (!q ? true : `${e.label} ${e.value} ${e.remark}`.toLowerCase().includes(q)))
      .slice()
      .sort((a, b) => a.sort - b.sort || Number(a.id) - Number(b.id))
  }, [entries, entrySearch, selectedDictId])

  const pageSize = 10
  const pagedEntries = useMemo(() => {
    const start = (page - 1) * pageSize
    return filteredEntries.slice(start, start + pageSize)
  }, [filteredEntries, page])

  const [editOpen, setEditOpen] = useState(false)
  const [editMode, setEditMode] = useState<'create' | 'edit'>('create')
  const [editId, setEditId] = useState<string | null>(null)
  const [formLabel, setFormLabel] = useState('')
  const [formValue, setFormValue] = useState('')
  const [formStatus, setFormStatus] = useState<'enabled' | 'disabled'>('enabled')
  const [formSort, setFormSort] = useState('1')
  const [formRemark, setFormRemark] = useState('')

  const openCreate = () => {
    setEditMode('create')
    setEditId(null)
    setFormLabel('')
    setFormValue('')
    setFormStatus('enabled')
    setFormSort(String(filteredEntries.length + 1))
    setFormRemark('')
    setEditOpen(true)
  }

  const openEdit = (entry: DictEntry) => {
    setEditMode('edit')
    setEditId(entry.id)
    setFormLabel(entry.label)
    setFormValue(entry.value)
    setFormStatus(entry.status)
    setFormSort(String(entry.sort))
    setFormRemark(entry.remark)
    setEditOpen(true)
  }

  const saveEntry = () => {
    const sort = Number(formSort)
    const nextSort = Number.isFinite(sort) ? sort : 1
    if (!formLabel.trim() || !formValue.trim()) return

    if (editMode === 'create') {
      const next: DictEntry = {
        id: randomId(),
        dictId: selectedDictId,
        label: formLabel.trim(),
        value: formValue.trim(),
        status: formStatus,
        sort: nextSort,
        remark: formRemark.trim(),
        createdAt: now(),
      }
      setEntries((prev) => [...prev, next])
    } else if (editId) {
      setEntries((prev) =>
        prev.map((e) =>
          e.id === editId
            ? {
                ...e,
                label: formLabel.trim(),
                value: formValue.trim(),
                status: formStatus,
                sort: nextSort,
                remark: formRemark.trim(),
              }
            : e,
        ),
      )
    }
    setEditOpen(false)
  }

  const deleteEntry = (id: string) => {
    setEntries((prev) => prev.filter((e) => e.id !== id))
  }

  return (
    <div className="grid gap-4">
      <PageHeader
            title={t('system.dict.title')}
            description={t('system.dict.description')}
            actions={<Badge variant="outline">Demo</Badge>}
      />

      <div className={cn('grid gap-4', isMobile ? 'grid-cols-1' : 'grid-cols-[260px_1fr]')}>
        <Card className="min-w-0">
          <CardHeader>
            <PageHeader
              title={t('system.dict.dict')}
              description={t('system.dict.chooseDescription')}
              actions={
                <div className="text-xs text-muted-foreground">
                  {t('system.dict.itemCount').replace('{n}', String(visibleDicts.filter((d) => !d.node.children?.length).length))}
                </div>
              }
            />
          </CardHeader>
          <CardContent className="grid gap-3">
            <Input value={dictSearch} onChange={(e) => setDictSearch(e.target.value)} placeholder={t('system.dict.searchPlaceholder')} />
            <ScrollArea className="h-[60vh] rounded-md border">
              <div className="p-2">
                {visibleDicts.map(({ node, depth }) => {
                  const isGroup = Boolean(node.children?.length)
                  const active = node.id === selectedDictId
                  return (
                    <button
                      key={node.id}
                      type="button"
                      className={cn(
                        'flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm hover:bg-accent',
                        active && 'bg-accent',
                        isGroup && 'font-medium',
                      )}
                      onClick={() => {
                        if (isGroup) return
                        setSelectedDictId(node.id)
                        setEntrySearch('')
                        setPage(1)
                      }}
                    >
                      <span className="shrink-0 text-muted-foreground" style={{ width: depth * 10 }} />
                      <span className="min-w-0 flex-1 truncate">{node.name}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">{node.code}</span>
                    </button>
                  )
                })}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader>
            <PageHeader
              title={
                <div className="flex items-center gap-2">
                  <span>{t('system.dict.detail')}</span>
                  {selectedDict ? <Badge variant="secondary">{selectedDict.code}</Badge> : null}
                </div>
              }
              description={selectedDict ? selectedDict.name : t('system.dict.notSelected')}
              actions={
                <Button disabled={!selectedDict || Boolean(selectedDict.children?.length)} onClick={openCreate}>
                  <Plus className="mr-2 h-4 w-4" />
                  {t('system.dict.addEntry')}
                </Button>
              }
            />
          </CardHeader>
          <CardContent className="grid gap-4">
            <CollapsibleFilters>
              <FilterGrid>
                <div className="grid gap-2">
                  <Label htmlFor="entrySearch">{t('common.search')}</Label>
                  <Input
                    id="entrySearch"
                    value={entrySearch}
                    onChange={(e) => {
                      setEntrySearch(e.target.value)
                      setPage(1)
                    }}
                    placeholder={t('system.dict.filterPlaceholder')}
                  />
                </div>
              </FilterGrid>
            </CollapsibleFilters>

            <div className="hidden md:block">
              <div className="overflow-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[180px]">{t('system.dict.label')}</TableHead>
                      <TableHead className="w-[140px]">{t('system.dict.value')}</TableHead>
                      <TableHead className="w-[90px]">{t('common.status')}</TableHead>
                      <TableHead className="w-[90px]">{t('system.common.sort')}</TableHead>
                      <TableHead>{t('system.common.remark')}</TableHead>
                      <TableHead className="w-[120px] text-right">{t('common.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pagedEntries.map((e) => (
                      <TableRow key={e.id}>
                        <TableCell className="font-medium">{e.label}</TableCell>
                        <TableCell>{e.value}</TableCell>
                        <TableCell>
                          <Badge variant={e.status === 'enabled' ? 'secondary' : 'outline'}>
                            {e.status === 'enabled' ? t('common.enabled') : t('common.disabled')}
                          </Badge>
                        </TableCell>
                        <TableCell>{e.sort}</TableCell>
                        <TableCell className="max-w-[420px] truncate text-muted-foreground">{e.remark || '-'}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button variant="outline" size="sm" onClick={() => openEdit(e)}>
                              {t('common.edit')}
                            </Button>
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <Button variant="destructive" size="sm">
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>{t('system.dict.confirmDelete')}</AlertDialogTitle>
                                  <AlertDialogDescription>{t('system.dict.deleteDescription').replace('{label}', e.label)}</AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => deleteEntry(e.id)}>{t('common.delete')}</AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                    {pagedEntries.length === 0 ? (
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
              {pagedEntries.map((e) => (
                <Card key={e.id}>
                  <CardContent className="grid gap-2 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0 font-medium">{e.label}</div>
                      <Badge variant={e.status === 'enabled' ? 'secondary' : 'outline'}>
                        {e.status === 'enabled' ? t('common.enabled') : t('common.disabled')}
                      </Badge>
                    </div>
                    <div className="text-sm text-muted-foreground">
                      value: <span className="font-mono text-foreground">{e.value}</span>
                    </div>
                    <div className="text-sm text-muted-foreground">sort: {e.sort}</div>
                    {e.remark ? <div className="text-sm text-muted-foreground">{e.remark}</div> : null}
                    <div className="flex gap-2 pt-1">
                      <Button variant="outline" size="sm" onClick={() => openEdit(e)} className="flex-1">
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
                            <AlertDialogTitle>{t('system.dict.confirmDelete')}</AlertDialogTitle>
                            <AlertDialogDescription>{t('system.dict.deleteDescription').replace('{label}', e.label)}</AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                            <AlertDialogAction onClick={() => deleteEntry(e.id)}>{t('common.delete')}</AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {pagedEntries.length === 0 ? <div className="py-6 text-center text-sm text-muted-foreground">{t('common.empty')}</div> : null}
            </div>

            <SimplePagination
              total={filteredEntries.length}
              currentPage={page}
              pageSize={pageSize}
              disabled={false}
              onChange={(p) => setPage(p)}
            />
          </CardContent>
        </Card>
      </div>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editMode === 'create' ? t('system.dict.addEntry') : t('system.dict.editEntry')}</DialogTitle>
            <DialogDescription>{t('system.dict.formDescription')}</DialogDescription>
          </DialogHeader>

          <div className="grid gap-3">
            <div className="grid gap-2">
              <Label htmlFor="label">{t('system.dict.label')}</Label>
              <Input id="label" value={formLabel} onChange={(e) => setFormLabel(e.target.value)} placeholder={t('system.dict.labelPlaceholder')} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="value">{t('system.dict.value')}</Label>
              <Input id="value" value={formValue} onChange={(e) => setFormValue(e.target.value)} placeholder={t('system.common.exampleIds').replace('{ids}', '1')} />
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t('common.status')}</Label>
                <Select value={formStatus} onValueChange={(v) => setFormStatus(v as 'enabled' | 'disabled')}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="enabled">{t('common.enabled')}</SelectItem>
                    <SelectItem value="disabled">{t('common.disabled')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="sort">{t('system.common.sort')}</Label>
                <Input id="sort" value={formSort} onChange={(e) => setFormSort(e.target.value)} inputMode="numeric" />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="remark">{t('system.common.remark')}</Label>
              <Textarea id="remark" value={formRemark} onChange={(e) => setFormRemark(e.target.value)} rows={3} />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={saveEntry} disabled={!formLabel.trim() || !formValue.trim()}>
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
