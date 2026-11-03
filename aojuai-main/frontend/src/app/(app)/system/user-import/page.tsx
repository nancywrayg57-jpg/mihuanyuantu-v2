'use client'

import { useState } from 'react'
import { Download, FileUp, Play, ShieldAlert } from 'lucide-react'

import { PageHeader } from '@/components/page/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'
import { apiFetch } from '@/lib/api'
import { hasAnyPermission } from '@/lib/auth'
import { useT } from '@/lib/i18n'

type ImportRow = {
  line: number
  username: string
  status: 'created' | 'skipped' | 'error'
  message: string
  initialPassword: string | null
  team: string | null
  role: string | null
}

type ImportResult = {
  dryRun: boolean
  total: number
  created: number
  skipped: number
  failed: number
  headerErrors: string[]
  rows: ImportRow[]
}

export default function UserImportPage() {
  const t = useT()
  const { session } = useAuth()
  const { targetTenantId } = useTenant()
  const [content, setContent] = useState('')
  const [result, setResult] = useState<ImportResult | null>(null)
  const [busy, setBusy] = useState<'dry' | 'commit' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const canImport = hasAnyPermission(session, ['user:create'])

  async function run(dryRun: boolean) {
    if (!session) return
    setBusy(dryRun ? 'dry' : 'commit')
    setError(null)
    try {
      setResult(
        await apiFetch<ImportResult>('/api/v1/users/import', {
          session,
          tenantId: targetTenantId,
          method: 'POST',
          body: JSON.stringify({ content, dryRun }),
        }),
      )
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusy(null)
    }
  }

  /** 模板只有一个真源：后端。前端不再抄一份 CSV 字面量，改表头时不会漏掉一边。 */
  async function downloadTemplate() {
    if (!session) return
    try {
      const template = await apiFetch<{ filename: string; content: string }>(
        '/api/v1/users/import/template',
        { session, tenantId: targetTenantId },
      )
      // BOM：Excel 打开中文 CSV 不加 BOM 会乱码
      const blob = new Blob([`\ufeff${template.content}`], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = template.filename
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    }
  }

  async function readFile(file: File) {
    setContent(await file.text())
    setResult(null)
  }

  if (!session) return null

  if (!canImport) {
    return (
      <div className="space-y-4">
        <PageHeader title={t('userImport.title')} description={t('userImport.description')} />
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            {t('userImport.permissionDenied')}
          </CardContent>
        </Card>
      </div>
    )
  }

  const created = result?.rows.filter((row) => row.status === 'created') ?? []

  return (
    <div className="space-y-4">
      <PageHeader title={t('userImport.title')} description={t('userImport.description')} />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t('userImport.step1')}</CardTitle>
          <CardDescription>{t('userImport.step1Hint')}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => void downloadTemplate()}>
              <Download className="mr-1 h-4 w-4" />
              {t('userImport.downloadTemplate')}
            </Button>
            <Button variant="outline" size="sm" asChild>
              <label className="cursor-pointer">
                <FileUp className="mr-1 h-4 w-4" />
                {t('userImport.chooseFile')}
                <input
                  type="file"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={(event) => {
                    const file = event.target.files?.[0]
                    if (file) void readFile(file)
                  }}
                />
              </label>
            </Button>
          </div>
          <div className="grid gap-1">
            <Label htmlFor="import-content">{t('userImport.contentLabel')}</Label>
            <Textarea
              id="import-content"
              rows={8}
              value={content}
              onChange={(event) => {
                setContent(event.target.value)
                setResult(null)
              }}
              placeholder={t('userImport.contentPlaceholder')}
              className="font-mono text-xs"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t('userImport.step2')}</CardTitle>
          <CardDescription>{t('userImport.step2Hint')}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => run(true)} disabled={!content.trim() || busy !== null}>
              <Play className="mr-1 h-4 w-4" />
              {busy === 'dry' ? t('common.loading') : t('userImport.dryRun')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => run(false)}
              // 必须先预演、且预演有可建的行，才允许真的执行
              disabled={!result || result.dryRun !== true || result.created === 0 || busy !== null}
            >
              {busy === 'commit' ? t('common.loading') : t('userImport.commit')}
            </Button>
          </div>

          {error ? <p className="text-sm text-destructive">{error}</p> : null}

          {result ? (
            <div className="grid gap-3 text-sm">
              <p className="text-muted-foreground">
                {t('userImport.summary')
                  .replace('{total}', String(result.total))
                  .replace('{created}', String(result.created))
                  .replace('{skipped}', String(result.skipped))
                  .replace('{failed}', String(result.failed))}
                {result.dryRun ? ` · ${t('userImport.dryRunBadge')}` : ''}
              </p>

              {result.headerErrors.length > 0 ? (
                <ul className="list-disc rounded-md border border-destructive/40 bg-destructive/10 p-3 pl-6">
                  {result.headerErrors.map((message) => (
                    <li key={message}>{message}</li>
                  ))}
                </ul>
              ) : null}

              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] text-left">
                  <thead className="text-muted-foreground">
                    <tr>
                      <th className="p-2">{t('userImport.column.line')}</th>
                      <th className="p-2">{t('userImport.column.username')}</th>
                      <th className="p-2">{t('userImport.column.status')}</th>
                      <th className="p-2">{t('userImport.column.message')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row) => (
                      <tr key={`${row.line}-${row.username}`} className="border-t">
                        <td className="p-2">{row.line}</td>
                        <td className="p-2 font-medium">{row.username || '—'}</td>
                        <td className="p-2">{t(`userImport.status.${row.status}`)}</td>
                        <td className="p-2 text-muted-foreground">{row.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {created.some((row) => row.initialPassword) ? (
                <div className="grid gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3">
                  <p className="flex items-center gap-2 font-medium">
                    <ShieldAlert className="h-4 w-4" />
                    {t('userImport.passwordTitle')}
                  </p>
                  <p className="text-muted-foreground">{t('userImport.passwordHint')}</p>
                  <div className="overflow-x-auto">
                    <ul className="min-w-0 font-mono text-xs">
                      {created.map((row) => (
                        <li key={row.username}>
                          {row.username} · {row.initialPassword}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
