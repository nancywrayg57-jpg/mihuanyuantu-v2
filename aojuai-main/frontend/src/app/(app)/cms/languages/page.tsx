'use client'

import { Globe, Plus, Star, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { PageHeader } from '@/components/page/page-header'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/hooks/useAuth'
import { hasAnyPermission } from '@/lib/auth'
import { useT } from '@/lib/i18n'
import {
  createLanguage,
  deleteLanguage,
  listLanguages,
  updateLanguage,
  type CmsLanguage,
} from '@/lib/cms-api'

export default function CmsLanguagesPage() {
  const t = useT()
  const { session } = useAuth()
  const [items, setItems] = useState<CmsLanguage[]>([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ code: '', name: '' })
  const [saving, setSaving] = useState(false)

  const canUpdate = hasAnyPermission(session, ['cms:settings:update'])

  const reload = useCallback(async () => {
    if (!session) return
    setLoading(true)
    try {
      const res = await listLanguages(session)
      setItems(res.list || [])
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.loadFailed'))
    } finally {
      setLoading(false)
    }
  }, [session, t])

  useEffect(() => {
    void reload()
  }, [reload])

  async function onCreate() {
    setSaving(true)
    setMsg('')
    try {
      await createLanguage(session, { code: form.code.trim(), name: form.name.trim() })
      setOpen(false)
      setForm({ code: '', name: '' })
      await reload()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.createFailed'))
    } finally {
      setSaving(false)
    }
  }

  async function setDefault(l: CmsLanguage) {
    try {
      await updateLanguage(session, l.id, { isDefault: true })
      await reload()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.actionFailed'))
    }
  }
  async function toggleActive(l: CmsLanguage) {
    try {
      await updateLanguage(session, l.id, { isActive: !l.isActive })
      await reload()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.actionFailed'))
    }
  }
  // 确认走 AlertDialog：原生 confirm 的按钮文字跟随系统语言、改不了，多语言直接失效
  // （见 guide_docs/FRONTEND_PAGE_SCAFFOLD_GUIDE.md §5）。
  async function onDelete(l: CmsLanguage) {
    if (l.isDefault) return
    try {
      await deleteLanguage(session, l.id)
      await reload()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.deleteFailed'))
    }
  }

  return (
    <div className="grid gap-4">
      <PageHeader
        title={t('cms.languages.title')}
        description={t('cms.languages.description')}
        icon={<Globe className="h-4 w-4" />}
        actions={canUpdate ? <Button size="sm" onClick={() => setOpen(true)}><Plus className="mr-1 h-4 w-4" />{t('cms.languages.new')}</Button> : null}
      />
      {msg ? <div className="rounded-lg border border-border/60 bg-muted/40 px-3 py-2 text-sm">{msg}</div> : null}

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex justify-center py-16"><div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div>
          ) : (
            <div className="divide-y divide-border/50">
              {items.map((l) => (
                <div key={l.id} className="flex flex-wrap items-center gap-3 px-4 py-3.5">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{l.name}</span>
                      <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{l.code}</code>
                      {l.isDefault ? <Badge className="text-[10px]">{t('cms.languages.default')}</Badge> : null}
                      {!l.isActive ? <Badge variant="secondary" className="text-[10px]">{t('cms.languages.inactive')}</Badge> : null}
                    </div>
                  </div>
                  {canUpdate ? (
                    <div className="flex items-center gap-1.5">
                      {!l.isDefault ? (
                        <Button size="sm" variant="ghost" onClick={() => setDefault(l)}>
                          <Star className="mr-1 h-3.5 w-3.5" />{t('cms.languages.setDefault')}
                        </Button>
                      ) : null}
                      <Button size="sm" variant="ghost" onClick={() => toggleActive(l)}>
                        {l.isActive ? t('cms.languages.disable') : t('cms.languages.enable')}
                      </Button>
                      {!l.isDefault ? (
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button size="sm" variant="ghost" className="text-destructive">
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>{t('common.delete')}</AlertDialogTitle>
                              <AlertDialogDescription>
                                {t('cms.languages.confirmDelete')
                                  .replace('{name}', l.name)
                                  .replace('{code}', l.code)}
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                              <AlertDialogAction
                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                onClick={() => void onDelete(l)}
                              >
                                {t('common.delete')}
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">{t('cms.languages.hint')}</p>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>{t('cms.languages.new')}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>{t('cms.languages.code')}</Label>
              <Input value={form.code} onChange={(e) => setForm((s) => ({ ...s, code: e.target.value }))} placeholder={t('cms.languages.codePlaceholder')} />
            </div>
            <div>
              <Label>{t('cms.languages.name')}</Label>
              <Input value={form.name} onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))} placeholder={t('cms.languages.namePlaceholder')} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>{t('common.cancel')}</Button>
            <Button onClick={onCreate} disabled={saving || !form.code || !form.name}>{saving ? t('cms.common.creating') : t('common.create')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
