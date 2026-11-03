'use client'

import { translateActive } from '@/lib/i18n/registry'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { ApiError } from '@/lib/api'
import {
  deleteCreditPriceItem,
  getCreditPricing,
  getCreditPricingReconciliation,
  updateCreditPriceAdjustment,
  updateCreditPricingMode,
  upsertCreditPriceItem,
  type CreditPriceItemUpsertPayload,
  type CreditPriceItemView,
  type CreditRateSchedule,
  type CreditPricingMode,
  type CreditPricingOverview,
  type CreditPricingReconciliation,
} from '@/lib/api/credits'

type RequestOpts = Parameters<typeof getCreditPricing>[0]

const t = (key: string) => translateActive(`app.system.credits.pricing.${key}`)

function errorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : err instanceof Error ? err.message : fallback
}

const EMPTY_FORM: CreditPriceItemUpsertPayload = {
  itemType: 'llm',
  matchKey: '',
  inputPointsPer1k: '',
  outputPointsPer1k: '',
  cachedPointsPer1k: '',
  cacheWritePointsPer1k: '',
  pointsPerUnit: '',
  unitDivisor: '',
  priority: 0,
  isActive: true,
  remark: '',
  rateSchedule: null,
}

function isTokenType(itemType: string) {
  return itemType === 'llm'
}

function RateCells({ item }: { item: CreditPriceItemView }) {
  if (isTokenType(item.itemType)) {
    return (
      <>
        <TableCell className="tabular-nums">{item.inputPointsPer1k}</TableCell>
        <TableCell className="tabular-nums">{item.outputPointsPer1k}</TableCell>
        <TableCell className="tabular-nums">{item.cachedPointsPer1k ?? '—'}</TableCell>
      </>
    )
  }
  return (
    <>
      <TableCell className="tabular-nums" colSpan={2}>
        {item.pointsPerUnit}
      </TableCell>
      <TableCell className="tabular-nums">{item.unitDivisor ?? '—'}</TableCell>
    </>
  )
}

function rateScheduleSummary(schedule: CreditRateSchedule | null | undefined) {
  if (!schedule?.bands?.length) return '—'
  return `${schedule.timezone} · ${schedule.bands.map((band) => `${band.key} ×${band.multiplier}`).join(', ')}`
}

export function CreditPricingPanel({
  requestOpts,
  canEdit,
  reconciliationAvailable = true,
}: {
  requestOpts: RequestOpts
  canEdit: boolean
  /** SQLite 轻量档等不支持对账 SQL 的部署下为 false：不请求、不渲染对账区块（见后端 dialect_features） */
  reconciliationAvailable?: boolean
}) {
  const [overview, setOverview] = useState<CreditPricingOverview | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [mode, setMode] = useState<CreditPricingMode>('legacy')
  const [marginPercent, setMarginPercent] = useState('30')
  const [cachedBilling, setCachedBilling] = useState<'passthrough' | 'full_price'>('passthrough')
  const [savingAdjustment, setSavingAdjustment] = useState(false)
  const [savingMode, setSavingMode] = useState(false)
  const [form, setForm] = useState<CreditPriceItemUpsertPayload>(EMPTY_FORM)
  const [rateScheduleText, setRateScheduleText] = useState('')
  const [savingItem, setSavingItem] = useState(false)
  const [platformFilter, setPlatformFilter] = useState<string>('all')
  const [recon, setRecon] = useState<CreditPricingReconciliation | null>(null)
  const [reconDays, setReconDays] = useState<number>(7)
  const [reconLoading, setReconLoading] = useState(false)

  const loadRecon = useCallback(async () => {
    if (!reconciliationAvailable) return
    setReconLoading(true)
    try {
      setRecon(await getCreditPricingReconciliation(reconDays, requestOpts))
    } catch (err) {
      setError(errorMessage(err, t('failed')))
    } finally {
      setReconLoading(false)
    }
  }, [reconDays, requestOpts, reconciliationAvailable])

  useEffect(() => {
    void loadRecon()
  }, [loadRecon])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getCreditPricing(requestOpts)
      setOverview(data)
      setMode(data.pricingMode)
      if (data.marginPercent != null) setMarginPercent(String(data.marginPercent))
      if (data.cachedBilling === 'full_price' || data.cachedBilling === 'passthrough') setCachedBilling(data.cachedBilling)
    } catch (err) {
      setError(errorMessage(err, t('failed')))
    } finally {
      setLoading(false)
    }
  }, [requestOpts])

  useEffect(() => {
    void load()
  }, [load])

  const platformRows = useMemo(() => {
    const rows = overview?.platformItems ?? []
    return platformFilter === 'all' ? rows : rows.filter((row) => row.itemType === platformFilter)
  }, [overview, platformFilter])

  const modeLabel = (value: CreditPricingMode) =>
    value === 'legacy' ? t('modeLegacy') : value === 'shadow' ? t('modeShadow') : t('modeUnified')

  const saveMode = async () => {
    setSavingMode(true)
    setError(null)
    setNotice(null)
    try {
      const data = await updateCreditPricingMode(mode, requestOpts)
      setOverview(data)
      setNotice(t('saved'))
    } catch (err) {
      setError(errorMessage(err, t('failed')))
    } finally {
      setSavingMode(false)
    }
  }

  const saveAdjustment = async () => {
    setSavingAdjustment(true)
    setError(null)
    setNotice(null)
    try {
      await updateCreditPriceAdjustment({ marginPercent, cachedBilling }, requestOpts)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    } finally {
      setSavingAdjustment(false)
    }
  }

  const submitItem = async () => {
    if (!form.matchKey.trim()) return
    setSavingItem(true)
    setError(null)
    setNotice(null)
    try {
      const payload: CreditPriceItemUpsertPayload = {
        itemType: form.itemType,
        matchKey: form.matchKey.trim(),
        priority: Number(form.priority || 0),
        isActive: form.isActive !== false,
        remark: form.remark ?? '',
      }
      if (rateScheduleText.trim()) {
        try {
          payload.rateSchedule = JSON.parse(rateScheduleText) as CreditRateSchedule
        } catch {
          throw new Error(t('scheduleInvalid'))
        }
      } else {
        payload.rateSchedule = null
      }
      if (isTokenType(form.itemType)) {
        payload.inputPointsPer1k = form.inputPointsPer1k || '0'
        payload.outputPointsPer1k = form.outputPointsPer1k || '0'
        payload.cachedPointsPer1k = form.cachedPointsPer1k ? form.cachedPointsPer1k : null
        payload.cacheWritePointsPer1k = form.cacheWritePointsPer1k ? form.cacheWritePointsPer1k : null
      } else {
        payload.pointsPerUnit = form.pointsPerUnit || '0'
        payload.unitDivisor = form.unitDivisor ? form.unitDivisor : null
      }
      await upsertCreditPriceItem(payload, requestOpts)
      setForm(EMPTY_FORM)
      setRateScheduleText('')
      setNotice(t('saved'))
      await load()
    } catch (err) {
      setError(errorMessage(err, t('failed')))
    } finally {
      setSavingItem(false)
    }
  }

  const editItem = (item: CreditPriceItemView) => {
    setForm({
      itemType: item.itemType,
      matchKey: item.matchKey,
      inputPointsPer1k: item.inputPointsPer1k,
      outputPointsPer1k: item.outputPointsPer1k,
      cachedPointsPer1k: item.cachedPointsPer1k ?? '',
      cacheWritePointsPer1k: item.cacheWritePointsPer1k ?? '',
      pointsPerUnit: item.pointsPerUnit,
      unitDivisor: item.unitDivisor ?? '',
      priority: item.priority,
      isActive: item.isActive,
      remark: item.remark,
      rateSchedule: item.rateSchedule,
    })
    setRateScheduleText(item.rateSchedule ? JSON.stringify(item.rateSchedule, null, 2) : '')
  }

  const removeItem = async (item: CreditPriceItemView) => {
    if (item.id == null) return
    setError(null)
    setNotice(null)
    try {
      await deleteCreditPriceItem(item.id, requestOpts)
      setNotice(t('deleted'))
      await load()
    } catch (err) {
      setError(errorMessage(err, t('failed')))
    }
  }

  const itemTypes = overview?.itemTypes ?? ['llm', 'image', 'tool_call', 'tts', 'asr', 'flat']

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader className="space-y-1 px-4 py-3">
          <CardTitle className="text-base">{t('title')}</CardTitle>
          <CardDescription>{t('desc')}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 px-4 pb-4">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
            <div className="grid gap-2">
              <Label>{t('mode')}</Label>
              <Select value={mode} onValueChange={(value) => setMode(value as CreditPricingMode)} disabled={!canEdit}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(overview?.availableModes ?? ['legacy', 'shadow', 'unified']).map((value) => (
                    <SelectItem key={value} value={value}>
                      {modeLabel(value)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {canEdit ? (
              <Button onClick={saveMode} disabled={savingMode || loading || !overview || mode === overview.pricingMode}>
                {t('saveMode')}
              </Button>
            ) : null}
          </div>
          <div className="grid gap-3 md:grid-cols-[auto_auto_auto] md:items-end">
            <div className="grid gap-2">
              <Label>{t('marginPercent')}</Label>
              <Input type="number" min={0} max={500} className="w-28" value={marginPercent} onChange={(event) => setMarginPercent(event.target.value)} disabled={!canEdit} />
              <p className="text-xs text-muted-foreground">{t('marginPercentHint')}</p>
            </div>
            <div className="grid gap-2">
              <Label>{t('cachedBilling')}</Label>
              <Select value={cachedBilling} onValueChange={(value) => setCachedBilling(value as 'passthrough' | 'full_price')} disabled={!canEdit}>
                <SelectTrigger className="w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="passthrough">{t('cachedPassthrough')}</SelectItem>
                  <SelectItem value="full_price">{t('cachedFullPrice')}</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">{t('cachedBillingHint')}</p>
            </div>
            {canEdit ? (
              <Button onClick={() => void saveAdjustment()} disabled={savingAdjustment || loading}>
                {t('saveAdjustment')}
              </Button>
            ) : null}
          </div>
          <div className="text-xs text-muted-foreground">
            {t('pricebook')} · {t('pricebookVersion')} <code>{overview?.pricebookVersion ?? '—'}</code>
          </div>
          <div className="text-xs text-muted-foreground">
            {t('tenantTimezone')}：<code>{overview?.tenantTimezone ?? '—'}</code>
            {overview?.currentTenantTime ? ` · ${t('tenantLocalTime')} ${overview.currentTenantTime}` : ''}
          </div>
          {error ? <div className="text-sm text-destructive">{error}</div> : null}
          {!error && notice ? <div className="text-sm text-emerald-600">{notice}</div> : null}
        </CardContent>
      </Card>

      {canEdit ? (
        <Card>
          <CardHeader className="space-y-1 px-4 py-3">
            <CardTitle className="text-base">{t('addOverride')}</CardTitle>
            <CardDescription>{t('hintMatch')}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 px-4 pb-4">
            <div className="grid gap-3 md:grid-cols-[160px_minmax(0,1fr)_120px]">
              <div className="grid gap-2">
                <Label>{t('itemType')}</Label>
                <Select value={form.itemType} onValueChange={(value) => setForm((current) => ({ ...current, itemType: value }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {itemTypes.map((value) => (
                      <SelectItem key={value} value={value}>
                        {value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>{t('matchKey')}</Label>
                <Input value={form.matchKey} onChange={(event) => setForm((current) => ({ ...current, matchKey: event.target.value }))} placeholder="gpt-5* / deepseek-* / gpt-image-2/1024x1024/high / web_search" />
              </div>
              <div className="grid gap-2">
                <Label>{t('priority')}</Label>
                <Input type="number" value={form.priority ?? 0} onChange={(event) => setForm((current) => ({ ...current, priority: Number(event.target.value || 0) }))} />
              </div>
            </div>
            {isTokenType(form.itemType) ? (
              <div className="grid gap-3 md:grid-cols-4">
                <div className="grid gap-2">
                  <Label>{t('inputRate')}</Label>
                  <Input inputMode="decimal" value={form.inputPointsPer1k ?? ''} onChange={(event) => setForm((current) => ({ ...current, inputPointsPer1k: event.target.value }))} />
                </div>
                <div className="grid gap-2">
                  <Label>{t('outputRate')}</Label>
                  <Input inputMode="decimal" value={form.outputPointsPer1k ?? ''} onChange={(event) => setForm((current) => ({ ...current, outputPointsPer1k: event.target.value }))} />
                </div>
                <div className="grid gap-2">
                  <Label>{t('cachedRate')}</Label>
                  <Input inputMode="decimal" value={form.cachedPointsPer1k ?? ''} onChange={(event) => setForm((current) => ({ ...current, cachedPointsPer1k: event.target.value }))} />
                </div>
                <div className="grid gap-2">
                  <Label>{t('cacheWriteRate')}</Label>
                  <Input inputMode="decimal" value={form.cacheWritePointsPer1k ?? ''} onChange={(event) => setForm((current) => ({ ...current, cacheWritePointsPer1k: event.target.value }))} />
                </div>
              </div>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label>{t('unitRate')}</Label>
                  <Input inputMode="decimal" value={form.pointsPerUnit ?? ''} onChange={(event) => setForm((current) => ({ ...current, pointsPerUnit: event.target.value }))} />
                </div>
                <div className="grid gap-2">
                  <Label>{t('unitDivisor')}</Label>
                  <Input inputMode="decimal" value={form.unitDivisor ?? ''} onChange={(event) => setForm((current) => ({ ...current, unitDivisor: event.target.value }))} />
                </div>
              </div>
            )}
            <div className="grid gap-2">
              <Label>{t('remark')}</Label>
              <Input value={form.remark ?? ''} onChange={(event) => setForm((current) => ({ ...current, remark: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>{t('rateSchedule')}</Label>
              <Textarea
                className="min-h-36 font-mono text-xs"
                value={rateScheduleText}
                onChange={(event) => setRateScheduleText(event.target.value)}
                placeholder='{"timezone":"tenant","defaultBand":"off_peak","bands":[{"key":"peak","multiplier":"1.5","weekdays":[1,2,3,4,5],"windows":[["09:00","18:00"]]}]}'
              />
              <div className="text-xs text-muted-foreground">{t('rateScheduleHint')}</div>
            </div>
            <div className="text-xs text-muted-foreground">{t('hintUnits')}</div>
            <div className="flex gap-2">
              <Button onClick={submitItem} disabled={savingItem || !form.matchKey.trim()}>
                {t('save')}
              </Button>
              <Button variant="outline" onClick={() => { setForm(EMPTY_FORM); setRateScheduleText('') }} disabled={savingItem}>
                {t('cancel')}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="space-y-1 px-4 py-3">
          <CardTitle className="text-base">{t('overrides')}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          {overview && overview.tenantOverrides.length === 0 ? (
            <div className="text-sm text-muted-foreground">{t('noOverrides')}</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('itemType')}</TableHead>
                  <TableHead>{t('matchKey')}</TableHead>
                  <TableHead>{t('inputRate')} / {t('unitRate')}</TableHead>
                  <TableHead>{t('outputRate')}</TableHead>
                  <TableHead>{t('cachedRate')} / {t('unitDivisor')}</TableHead>
                  <TableHead>{t('rateSchedule')}</TableHead>
                  <TableHead>{t('priority')}</TableHead>
                  <TableHead>{t('remark')}</TableHead>
                  {canEdit ? <TableHead>{t('actions')}</TableHead> : null}
                </TableRow>
              </TableHeader>
              <TableBody>
                {(overview?.tenantOverrides ?? []).map((item) => (
                  <TableRow key={item.id ?? `${item.itemType}:${item.matchKey}`}>
                    <TableCell><Badge variant="outline">{item.itemType}</Badge></TableCell>
                    <TableCell className="font-mono text-xs">{item.matchKey}</TableCell>
                    <RateCells item={item} />
                    <TableCell className="max-w-[240px] text-xs" title={JSON.stringify(item.rateSchedule || {})}>{rateScheduleSummary(item.rateSchedule)}</TableCell>
                    <TableCell>{item.priority}</TableCell>
                    <TableCell className="max-w-[240px] truncate" title={item.remark}>{item.remark}</TableCell>
                    {canEdit ? (
                      <TableCell className="space-x-2 whitespace-nowrap">
                        <Button size="sm" variant="outline" onClick={() => editItem(item)}>{t('edit')}</Button>
                        <Button size="sm" variant="destructive" onClick={() => void removeItem(item)}>{t('delete')}</Button>
                      </TableCell>
                    ) : null}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="space-y-1 px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-base">{t('pricebook')}</CardTitle>
            <Select value={platformFilter} onValueChange={setPlatformFilter}>
              <SelectTrigger className="w-[160px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">*</SelectItem>
                {itemTypes.map((value) => (
                  <SelectItem key={value} value={value}>{value}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('itemType')}</TableHead>
                <TableHead>{t('matchKey')}</TableHead>
                <TableHead>{t('inputRate')} / {t('unitRate')}</TableHead>
                <TableHead>{t('outputRate')}</TableHead>
                <TableHead>{t('cachedRate')} / {t('unitDivisor')}</TableHead>
                <TableHead>{t('rateSchedule')}</TableHead>
                <TableHead>{t('priority')}</TableHead>
                <TableHead>{t('remark')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {platformRows.map((item) => (
                <TableRow key={`${item.itemType}:${item.matchKey}`}>
                  <TableCell><Badge variant="secondary">{item.itemType}</Badge></TableCell>
                  <TableCell className="font-mono text-xs">{item.matchKey}</TableCell>
                  <RateCells item={item} />
                  <TableCell className="max-w-[240px] text-xs" title={JSON.stringify(item.rateSchedule || {})}>{rateScheduleSummary(item.rateSchedule)}</TableCell>
                  <TableCell>{item.priority}</TableCell>
                  <TableCell className="max-w-[280px] truncate" title={item.remark}>{item.remark}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {reconciliationAvailable ? (
        <Card>
          <CardHeader className="space-y-1 px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle className="text-base">{t('recon')}</CardTitle>
                <CardDescription>{t('reconDesc')}</CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Label className="text-xs">{t('reconDays')}</Label>
                <Input type="number" className="w-20" value={reconDays} min={1} max={90} onChange={(event) => setReconDays(Math.max(1, Math.min(90, Number(event.target.value || 7))))} />
                <Button size="sm" variant="outline" onClick={() => void loadRecon()} disabled={reconLoading}>{t('reconLoad')}</Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="grid gap-3 px-4 pb-4">
            {recon ? (
              <div className="grid gap-2 text-sm sm:grid-cols-3 xl:grid-cols-5">
                <div><span className="text-muted-foreground">{t('coverage')}</span>：{recon.coverage.billingCoverage == null ? '—' : `${Math.round(recon.coverage.billingCoverage * 100)}%`} ({recon.coverage.withBilling}/{recon.coverage.txCount})</div>
                <div><span className="text-muted-foreground">{t('estimatedItems')}</span>：{recon.coverage.estimatedItems}/{recon.coverage.usageItems}</div>
                <div><span className="text-muted-foreground">{t('emptyModel')}</span>：{recon.coverage.emptyModelItems}</div>
                <div><span className="text-muted-foreground">{t('fallbackRows')}</span>：{recon.coverage.fallbackRateRows}</div>
                <div><span className="text-muted-foreground">{t('flatRows')}</span>：{recon.coverage.flatFallbackRows}</div>
              </div>
            ) : null}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('refType')}</TableHead>
                  <TableHead>{t('txCount')}</TableHead>
                  <TableHead>{t('modes')}</TableHead>
                  <TableHead>{t('chargedOut')}</TableHead>
                  <TableHead>{t('shadowLegacy')}</TableHead>
                  <TableHead>{t('shadowUnified')}</TableHead>
                  <TableHead>{t('shadowDelta')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(recon?.rows ?? []).map((row) => (
                  <TableRow key={row.referenceType}>
                    <TableCell className="font-mono text-xs">{row.referenceType}</TableCell>
                    <TableCell className="tabular-nums">{row.txCount}</TableCell>
                    <TableCell className="tabular-nums">{row.legacyRows}/{row.shadowRows}/{row.unifiedRows}</TableCell>
                    <TableCell className="tabular-nums">{row.chargedOut}</TableCell>
                    <TableCell className="tabular-nums">{row.shadowLegacySum}</TableCell>
                    <TableCell className="tabular-nums">{row.shadowUnifiedSum}</TableCell>
                    <TableCell className={`tabular-nums ${Number(row.shadowDelta) > 0 ? 'text-amber-600' : Number(row.shadowDelta) < 0 ? 'text-emerald-600' : ''}`}>{row.shadowDelta}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
