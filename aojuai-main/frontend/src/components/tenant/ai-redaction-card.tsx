'use client'

import { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/hooks/useAuth'
import { ApiError, apiFetch } from '@/lib/api'
import { useT } from '@/lib/i18n'

type PresetLevel = 'off' | 'basic' | 'standard' | 'strict'
type RedactionLevel = PresetLevel | 'custom'

type PolicyView = {
  version: number
  level: RedactionLevel
  rules: Record<string, unknown>
  approvedBy: string
  approvedAt: string
  note: string
}

type SettingsPayload = {
  scope: string
  scopes: string[]
  active: PolicyView | null
  effective: PolicyView
  presets: Record<'basic' | 'standard' | 'strict', Record<string, unknown>>
}

const LEVELS: PresetLevel[] = ['off', 'basic', 'standard', 'strict']

const OFF_PRESET: Record<string, unknown> = {
  schemaVersion: 1,
  level: 'off',
  fieldRules: {},
  detectors: [],
  generalizeAmountInText: false,
  derivePersonAliases: false,
  deriveOrgPrefixes: false,
  allowTerms: [],
  guardOnViolation: 'warn',
}

function isPresetLevel(value: unknown): value is PresetLevel {
  return LEVELS.includes(value as PresetLevel)
}

function prettyRules(value: Record<string, unknown>): string {
  const rules = { ...value }
  delete rules.approvedBy
  delete rules.approvedAt
  delete rules.note
  return JSON.stringify(rules, null, 2)
}

function formatApprovedAt(value: string): string {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

export function AIRedactionCard() {
  const t = useT()
  const { session } = useAuth()
  const [scope, setScope] = useState('*')
  const [settings, setSettings] = useState<SettingsPayload | null>(null)
  const [history, setHistory] = useState<PolicyView[]>([])
  const [baseLevel, setBaseLevel] = useState<PresetLevel>('standard')
  const [custom, setCustom] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [rulesText, setRulesText] = useState('{}')
  const [approvedBy, setApprovedBy] = useState('')
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function rulesForLevel(level: PresetLevel, payload = settings): Record<string, unknown> {
    if (level === 'off') return OFF_PRESET
    return payload?.presets[level] || {}
  }

  async function load(currentScope = scope) {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const encodedScope = encodeURIComponent(currentScope)
      const [payload, versions] = await Promise.all([
        apiFetch<SettingsPayload>(
          `/api/v1/tenant/profile/settings/ai-redaction?scope=${encodedScope}`,
          { session },
        ),
        apiFetch<PolicyView[]>(
          `/api/v1/tenant/profile/settings/ai-redaction/versions?scope=${encodedScope}&limit=20`,
          { session },
        ),
      ])
      setSettings(payload)
      setHistory(versions)

      const current = payload.active || payload.effective
      const currentBase =
        current.level === 'custom' && isPresetLevel(current.rules.baseLevel)
          ? current.rules.baseLevel
          : isPresetLevel(current.level)
            ? current.level
            : 'standard'
      setBaseLevel(currentBase)
      setCustom(current.level === 'custom')
      setRulesText(prettyRules(current.rules))
      setApprovedBy(current.approvedBy || session.nickname || session.username || '')
      setNote(current.note || '')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('app.system.aiRedaction.loadFailed'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load(scope)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, session?.accessToken])

  function selectLevel(level: PresetLevel) {
    setBaseLevel(level)
    setCustom(false)
    setRulesText(prettyRules(rulesForLevel(level)))
  }

  async function save() {
    if (!session || !approvedBy.trim()) return
    let parsed: Record<string, unknown>
    try {
      const value: unknown = JSON.parse(rulesText || '{}')
      if (!value || typeof value !== 'object' || Array.isArray(value)) {
        throw new Error('rules must be an object')
      }
      parsed = value as Record<string, unknown>
    } catch {
      const message = t('app.system.aiRedaction.invalidJson')
      setError(message)
      toast.error(message)
      return
    }

    const outgoingRules = custom
      ? { ...parsed, baseLevel }
      : {
          ...(Object.prototype.hasOwnProperty.call(parsed, 'allowTerms')
            ? { allowTerms: parsed.allowTerms }
            : {}),
          ...(Object.prototype.hasOwnProperty.call(parsed, 'fieldRules')
            ? { fieldRules: parsed.fieldRules }
            : {}),
        }

    setSaving(true)
    setError(null)
    const toastId = toast.loading(t('app.system.aiRedaction.saving'))
    try {
      await apiFetch<SettingsPayload>('/api/v1/tenant/profile/settings/ai-redaction', {
        method: 'PUT',
        session,
        body: JSON.stringify({
          scope,
          level: custom ? 'custom' : baseLevel,
          rules: outgoingRules,
          approvedBy: approvedBy.trim(),
          note: note.trim(),
        }),
      })
      toast.success(t('app.system.aiRedaction.saved'), { id: toastId })
      await load(scope)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : t('app.system.aiRedaction.saveFailed')
      setError(message)
      toast.error(message, { id: toastId })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>{t('app.system.aiRedaction.title')}</CardTitle>
          {custom ? <Badge variant="secondary">{t('app.system.aiRedaction.custom')}</Badge> : null}
        </div>
        <CardDescription>{t('app.system.aiRedaction.description')}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-5">
        <div className="grid gap-2 md:max-w-md">
          <Label>{t('app.system.aiRedaction.scope')}</Label>
          <Select value={scope} onValueChange={setScope} disabled={loading}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(settings?.scopes || ['*']).map((item) => (
                <SelectItem key={item} value={item}>
                  {item === '*' ? t('app.system.aiRedaction.sharedScope') : item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <fieldset className="grid gap-3" disabled={loading}>
          <legend className="text-sm font-medium">{t('app.system.aiRedaction.level')}</legend>
          <div className="grid gap-3 lg:grid-cols-4">
            {LEVELS.map((level) => (
              <label
                key={level}
                className="flex cursor-pointer gap-3 rounded-lg border p-3 has-[:checked]:border-primary has-[:checked]:bg-primary/5"
              >
                <input
                  type="radio"
                  name="ai-redaction-level"
                  value={level}
                  checked={baseLevel === level}
                  onChange={() => selectLevel(level)}
                  className="mt-1"
                />
                <span className="grid gap-1">
                  <span className="text-sm font-medium">{t(`app.system.aiRedaction.level.${level}`)}</span>
                  <span className="text-xs text-muted-foreground">
                    {t(`app.system.aiRedaction.level.${level}.description`)}
                  </span>
                </span>
              </label>
            ))}
          </div>
          {baseLevel === 'off' ? (
            <p className="text-xs text-destructive">{t('app.system.aiRedaction.offWarning')}</p>
          ) : null}
        </fieldset>

        <div className="rounded-lg border">
          <Button
            type="button"
            variant="ghost"
            className="w-full justify-start"
            onClick={() => setAdvancedOpen((value) => !value)}
          >
            {advancedOpen ? <ChevronDown /> : <ChevronRight />}
            {t('app.system.aiRedaction.advanced')}
            {custom ? <Badge variant="outline">{t('app.system.aiRedaction.custom')}</Badge> : null}
          </Button>
          {advancedOpen || custom ? (
            <div className="grid gap-2 border-t p-3">
              <p className="text-xs text-muted-foreground">{t('app.system.aiRedaction.advancedHint')}</p>
              <Textarea
                className="min-h-64 font-mono text-xs"
                value={rulesText}
                onChange={(event) => {
                  setRulesText(event.target.value)
                  setCustom(true)
                }}
                spellCheck={false}
              />
            </div>
          ) : null}
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="ai-redaction-approved-by">{t('app.system.aiRedaction.approvedBy')}</Label>
            <Input
              id="ai-redaction-approved-by"
              value={approvedBy}
              onChange={(event) => setApprovedBy(event.target.value)}
              maxLength={64}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="ai-redaction-note">{t('app.system.aiRedaction.note')}</Label>
            <Input
              id="ai-redaction-note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              maxLength={2000}
            />
          </div>
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <div>
          <Button onClick={() => void save()} disabled={loading || saving || !approvedBy.trim()}>
            {saving ? t('app.system.aiRedaction.saving') : t('app.system.aiRedaction.save')}
          </Button>
        </div>

        <div className="grid gap-2">
          <h3 className="text-sm font-medium">{t('app.system.aiRedaction.history')}</h3>
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('app.system.aiRedaction.version')}</TableHead>
                  <TableHead>{t('app.system.aiRedaction.level')}</TableHead>
                  <TableHead>{t('app.system.aiRedaction.approvedBy')}</TableHead>
                  <TableHead>{t('app.system.aiRedaction.approvedAt')}</TableHead>
                  <TableHead>{t('app.system.aiRedaction.note')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.length > 0 ? (
                  history.map((item) => (
                    <TableRow key={item.version}>
                      <TableCell>{item.version}</TableCell>
                      <TableCell>{t(`app.system.aiRedaction.level.${item.level}`)}</TableCell>
                      <TableCell>{item.approvedBy || '-'}</TableCell>
                      <TableCell className="whitespace-nowrap">{formatApprovedAt(item.approvedAt)}</TableCell>
                      <TableCell>{item.note || '-'}</TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={5} className="py-6 text-center text-muted-foreground">
                      {loading ? t('app.system.aiRedaction.loading') : t('app.system.aiRedaction.noHistory')}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
