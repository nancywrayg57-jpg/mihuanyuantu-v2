'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ChevronLeft, ChevronRight, Plus, Trash2 } from 'lucide-react'

import { PageHeader } from '@/components/page/page-header'
import { apiFetch } from '@/lib/api'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'

type ScheduleType = 'morning' | 'noon' | 'evening'

type ScheduleItem = {
  id: string
  title: string
  type: ScheduleType
  startDate: string // YYYY-MM-DD
  endDate: string // YYYY-MM-DD
  remark: string
}

function pad2(n: number) {
  return String(n).padStart(2, '0')
}

function toYmd(d: Date) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

function parseYmd(s: string) {
  const [y, m, d] = s.split('-').map((x) => Number(x))
  return new Date(y, (m || 1) - 1, d || 1)
}

function startOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), 1)
}

function addMonths(d: Date, months: number) {
  return new Date(d.getFullYear(), d.getMonth() + months, 1)
}

function addDays(d: Date, days: number) {
  const next = new Date(d)
  next.setDate(next.getDate() + days)
  return next
}

function startOfWeekMonday(d: Date) {
  // 0=Sun, 1=Mon, ... 6=Sat
  const dow = d.getDay()
  const delta = dow === 0 ? -6 : 1 - dow
  return addDays(d, delta)
}

function isSameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}

function dateOnlyTs(s: string) {
  return parseYmd(s).setHours(0, 0, 0, 0)
}

function inRange(day: string, start: string, end: string) {
  const t = dateOnlyTs(day)
  return t >= dateOnlyTs(start) && t <= dateOnlyTs(end)
}

function randomId() {
  return Math.random().toString(36).slice(2, 10)
}

const legends: Array<{ type: ScheduleType; labelKey: string; bg: string; text: string }> = [
  { type: 'morning', labelKey: 'system.schedule.morningShift', bg: 'bg-emerald-50', text: 'text-emerald-700' },
  { type: 'noon', labelKey: 'system.schedule.noonShift', bg: 'bg-amber-50', text: 'text-amber-700' },
  { type: 'evening', labelKey: 'system.schedule.eveningShift', bg: 'bg-sky-50', text: 'text-sky-700' },
]

function createSeedItems(t: ReturnType<typeof useT>): ScheduleItem[] {
  return [
    { id: 's1', title: t('system.schedule.samplePersonA'), type: 'morning', startDate: toYmd(new Date()), endDate: toYmd(new Date()), remark: '' },
    {
      id: 's2',
      title: t('system.schedule.samplePersonB'),
      type: 'noon',
      startDate: toYmd(addDays(new Date(), 1)),
      endDate: toYmd(addDays(new Date(), 3)),
      remark: t('system.schedule.sampleRemark'),
    },
  ]
}

const weekdayKeys = [
  'system.schedule.weekdayMon',
  'system.schedule.weekdayTue',
  'system.schedule.weekdayWed',
  'system.schedule.weekdayThu',
  'system.schedule.weekdayFri',
  'system.schedule.weekdaySat',
  'system.schedule.weekdaySun',
]

export default function SchedulePage() {
  const t = useT()
  const router = useRouter()
  const [blocked, setBlocked] = useState(false)
  const today = useMemo(() => new Date(), [])
  const [month, setMonth] = useState<Date>(() => startOfMonth(new Date()))
  const [items, setItems] = useState<ScheduleItem[]>(() => createSeedItems(t))

  useEffect(() => {
    void apiFetch<{ roleCodes?: string[] }>('/api/v1/realphotos/me')
      .then((data) => {
        const roles = data.roleCodes || []
        const business = new Set([
          'rp_merchant',
          'rp_order_support',
          'rp_tech_support',
          'rp_admin',
          'admin',
        ])
        if (roles.some((code) => business.has(code) || String(code).startsWith('rp_merchant'))) {
          setBlocked(true)
          router.replace('/welcome')
        }
      })
      .catch(() => undefined)
  }, [router])

  const monthValue = useMemo(() => `${month.getFullYear()}-${pad2(month.getMonth() + 1)}`, [month])
  if (blocked) {
    return (
      <main className="p-6 text-sm text-muted-foreground">
        当前业务角色无权访问演示页，已离开日程演示。
      </main>
    )
  }

  const gridDays = useMemo(() => {
    const first = startOfMonth(month)
    const start = startOfWeekMonday(first)
    return Array.from({ length: 42 }, (_, i) => {
      const date = addDays(start, i)
      const ymd = toYmd(date)
      return { date, ymd, inMonth: date.getMonth() === month.getMonth() }
    })
  }, [month])

  const itemsForDay = (ymd: string) => {
    return items.filter((it) => inRange(ymd, it.startDate, it.endDate))
  }

  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogMode, setDialogMode] = useState<'create' | 'view'>('create')
  const [activeItemId, setActiveItemId] = useState<string | null>(null)

  const activeItem = useMemo(() => items.find((it) => it.id === activeItemId) || null, [activeItemId, items])

  const [fTitle, setFTitle] = useState('')
  const [fType, setFType] = useState<ScheduleType>('morning')
  const [fStart, setFStart] = useState('')
  const [fEnd, setFEnd] = useState('')
  const [fRemark, setFRemark] = useState('')

  const openCreate = (date: string) => {
    setDialogMode('create')
    setActiveItemId(null)
    setFTitle('')
    setFType('morning')
    setFStart(date)
    setFEnd(date)
    setFRemark('')
    setDialogOpen(true)
  }

  const openView = (id: string) => {
    setDialogMode('view')
    setActiveItemId(id)
    setDialogOpen(true)
  }

  const save = () => {
    if (!fTitle.trim() || !fStart || !fEnd) return
    const start = dateOnlyTs(fStart)
    const end = dateOnlyTs(fEnd)
    const s = start <= end ? fStart : fEnd
    const e = start <= end ? fEnd : fStart
    setItems((prev) => [
      ...prev,
      { id: randomId(), title: fTitle.trim(), type: fType, startDate: s, endDate: e, remark: fRemark.trim() },
    ])
    setDialogOpen(false)
  }

  const remove = (id: string) => setItems((prev) => prev.filter((it) => it.id !== id))

  return (
    <div className="grid gap-4">
      <PageHeader
        title={t('system.schedule.title')}
        description={t('system.schedule.description')}
        actions={<Badge variant="outline">Demo</Badge>}
      />

      <PageHeader
        title={t('system.schedule.mySchedule')}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Input
              type="month"
              value={monthValue}
              onChange={(e) => {
                const v = e.target.value
                if (!v) return
                const [y, m] = v.split('-').map((x) => Number(x))
                setMonth(new Date(y, (m || 1) - 1, 1))
              }}
              className="w-[170px]"
            />
            <Button variant="outline" size="icon" onClick={() => setMonth((m) => addMonths(m, -1))}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" onClick={() => setMonth(startOfMonth(new Date()))}>
              {t('system.schedule.today')}
            </Button>
            <Button variant="outline" size="icon" onClick={() => setMonth((m) => addMonths(m, 1))}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        }
      />
      <Card>
        <CardContent className="grid gap-4">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {legends.map((l) => (
              <div key={l.type} className={cn('flex items-center gap-2 rounded-md px-2 py-1', l.bg, l.text)}>
                <span className="h-2 w-2 rounded-full bg-current opacity-70" />
                <span className="font-medium">{t(l.labelKey)}</span>
              </div>
            ))}
          </div>

          <div className="overflow-hidden rounded-md border">
            <div className="grid grid-cols-7 border-b bg-muted text-xs text-muted-foreground">
              {weekdayKeys.map((key) => (
                <div key={key} className="px-2 py-2 text-center font-medium">
                  {t(key)}
                </div>
              ))}
            </div>
            <div className="grid grid-cols-7">
              {gridDays.map(({ date, ymd, inMonth }) => {
                const list = itemsForDay(ymd)
                const isToday = isSameDay(date, today)
                return (
                  <div
                    key={ymd}
                    className={cn(
                      'min-h-[120px] border-r border-b p-2',
                      !inMonth && 'bg-muted/30 text-muted-foreground',
                      isToday && 'bg-accent/40',
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className={cn('text-sm font-medium', isToday && 'rounded bg-primary px-1 text-primary-foreground')}>
                        {date.getDate()}
                      </div>
                      {inMonth ? (
                        <Button variant="ghost" size="icon" onClick={() => openCreate(ymd)}>
                          <Plus className="h-4 w-4" />
                        </Button>
                      ) : null}
                    </div>

                    <div className="mt-1 max-h-[78px] space-y-1 overflow-auto">
                      {list.map((it) => {
                        const legend = legends.find((l) => l.type === it.type) || legends[0]
                        return (
                          <button
                            key={it.id}
                            type="button"
                            className={cn('w-full truncate rounded px-2 py-1 text-left text-xs', legend.bg, legend.text)}
                            onClick={() => openView(it.id)}
                            title={it.title}
                          >
                            {it.title}
                          </button>
                        )
                      })}
                      {list.length === 0 ? <div className="text-xs text-muted-foreground">{t('system.schedule.noSchedule')}</div> : null}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="text-xs text-muted-foreground">
            {t('system.schedule.hint')}
          </div>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          {dialogMode === 'create' ? (
            <>
              <DialogHeader>
                <DialogTitle>{t('system.schedule.create')}</DialogTitle>
                <DialogDescription>{t('system.schedule.createDescription')}</DialogDescription>
              </DialogHeader>

              <div className="grid gap-3">
                <div className="grid gap-2">
                  <Label htmlFor="title">{t('system.common.content')}</Label>
                  <Input id="title" value={fTitle} onChange={(e) => setFTitle(e.target.value)} placeholder={t('system.schedule.titlePlaceholder')} />
                </div>
                <div className="grid gap-2">
                  <Label>{t('system.common.type')}</Label>
                  <Select value={fType} onValueChange={(v) => setFType(v as ScheduleType)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="morning">{t('system.schedule.morningShift')}</SelectItem>
                      <SelectItem value="noon">{t('system.schedule.noonShift')}</SelectItem>
                      <SelectItem value="evening">{t('system.schedule.eveningShift')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label htmlFor="start">{t('system.schedule.startDate')}</Label>
                    <Input id="start" type="date" value={fStart} onChange={(e) => setFStart(e.target.value)} />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="end">{t('system.schedule.endDate')}</Label>
                    <Input id="end" type="date" value={fEnd} onChange={(e) => setFEnd(e.target.value)} />
                  </div>
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
                <Button onClick={save} disabled={!fTitle.trim() || !fStart || !fEnd}>
                  {t('common.save')}
                </Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle>{t('system.schedule.detail')}</DialogTitle>
                <DialogDescription>{t('system.schedule.detailDescription')}</DialogDescription>
              </DialogHeader>

              {activeItem ? (
                <div className="grid gap-3 text-sm">
                  <div>
                    <div className="text-xs text-muted-foreground">{t('system.common.content')}</div>
                    <div className="font-medium">{activeItem.title}</div>
                  </div>
                  <div className="grid gap-2 md:grid-cols-2">
                    <div>
                      <div className="text-xs text-muted-foreground">{t('system.schedule.start')}</div>
                      <div className="font-mono">{activeItem.startDate}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">{t('system.schedule.end')}</div>
                      <div className="font-mono">{activeItem.endDate}</div>
                    </div>
                  </div>
                  {activeItem.remark ? (
                    <div>
                      <div className="text-xs text-muted-foreground">{t('system.common.remark')}</div>
                      <div className="whitespace-pre-wrap">{activeItem.remark}</div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">{t('system.schedule.notFound')}</div>
              )}

              <DialogFooter>
                <Button variant="outline" onClick={() => setDialogOpen(false)}>
                  {t('common.close')}
                </Button>
                {activeItem ? (
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="destructive">
                        <Trash2 className="mr-2 h-4 w-4" />
                        {t('common.delete')}
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>{t('system.schedule.confirmDelete')}</AlertDialogTitle>
                        <AlertDialogDescription>{t('system.schedule.deleteDescription').replace('{name}', activeItem.title)}</AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={() => {
                            remove(activeItem.id)
                            setDialogOpen(false)
                          }}
                        >
                          {t('common.delete')}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                ) : null}
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
