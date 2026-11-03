'use client'

import type { Data } from '@measured/puck'
import { ExternalLink, FileText, Plus, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { PageEditor } from '@/components/cms/page-editor'
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
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/hooks/useAuth'
import { hasAnyPermission } from '@/lib/auth'
import { useT } from '@/lib/i18n'
import { Textarea } from '@/components/ui/textarea'
import {
  aiGeneratePage,
  aiTranslatePage,
  createPage,
  deletePage,
  getPage,
  listLanguages,
  listPages,
  publishPage,
  updatePage,
  type CmsLanguage,
  type PageListItem,
} from '@/lib/cms-api'

export default function CmsPagesPage() {
  const t = useT()
  const { session } = useAuth()
  const [items, setItems] = useState<PageListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')

  const canCreate = hasAnyPermission(session, ['cms:page:create'])
  const canUpdate = hasAnyPermission(session, ['cms:page:update'])
  const canPublish = hasAnyPermission(session, ['cms:page:publish'])
  const canDelete = hasAnyPermission(session, ['cms:page:delete'])

  const [createOpen, setCreateOpen] = useState(false)
  const [newPage, setNewPage] = useState({ title: '', slug: '', locale: 'default' })
  const [creating, setCreating] = useState(false)

  const [aiOpen, setAiOpen] = useState(false)
  const [ai, setAi] = useState({ title: '', slug: '', prompt: '' })
  const [generating, setGenerating] = useState(false)

  const [languages, setLanguages] = useState<CmsLanguage[]>([])
  const siteLocales = languages.map((l) => l.code)
  const langName = (code: string) => languages.find((l) => l.code === code)?.name || code
  const [localeFilter, setLocaleFilter] = useState<string>('')
  const [trans, setTrans] = useState<{ source: PageListItem; locale: string; useAi: boolean } | null>(null)
  const [translating, setTranslating] = useState(false)

  const [editing, setEditing] = useState<{ id: number; title: string; data: Data } | null>(null)

  const reload = useCallback(async () => {
    if (!session) return
    setLoading(true)
    try {
      const res = await listPages(session)
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

  useEffect(() => {
    if (!session) return
    listLanguages(session)
      .then((r) => setLanguages(r.list || []))
      .catch(() => {})
  }, [session])

  async function onTranslate() {
    if (!trans) return
    setTranslating(true)
    setMsg('')
    try {
      const src = await getPage(session, trans.source.id)
      let blocks = src.blocks
      let mode: 'ai' | 'copy' = 'copy'
      if (trans.useAi) {
        const res = await aiTranslatePage(session, trans.source.id, trans.locale)
        blocks = res.blocks
        mode = res.mode
      }
      const page = await createPage(session, {
        title: `${src.title} (${langName(trans.locale)})`,
        slug: src.slug,
        locale: trans.locale,
        status: 'draft',
        blocks,
        seo: src.seo || {},
      })
      setTrans(null)
      await reload()
      setMsg(
        trans.useAi && mode === 'ai'
          ? t('cms.pages.transAiDone').replace('{lang}', langName(trans.locale))
          : t('cms.pages.transCopyDone').replace('{lang}', langName(trans.locale)),
      )
      setEditing({ id: page.id, title: page.title, data: page.blocks as Data })
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.pages.transCreateFailed'))
    } finally {
      setTranslating(false)
    }
  }

  async function onCreate() {
    setCreating(true)
    setMsg('')
    try {
      const page = await createPage(session, {
        title: newPage.title,
        slug: newPage.slug,
        locale: newPage.locale || 'default',
        status: 'draft',
        blocks: { content: [], root: { props: {} }, zones: {} },
        seo: {},
      })
      setCreateOpen(false)
      setNewPage({ title: '', slug: '', locale: 'default' })
      await reload()
      // open editor right away
      setEditing({ id: page.id, title: page.title, data: page.blocks as Data })
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.createFailed'))
    } finally {
      setCreating(false)
    }
  }

  async function onGenerate() {
    setGenerating(true)
    setMsg('')
    try {
      const res = await aiGeneratePage(session, ai.prompt)
      const page = await createPage(session, {
        title: ai.title || ai.prompt.slice(0, 20),
        slug: ai.slug,
        status: 'draft',
        blocks: res.blocks,
        seo: {},
      })
      setAiOpen(false)
      setAi({ title: '', slug: '', prompt: '' })
      await reload()
      setMsg(res.mode === 'ai' ? t('cms.pages.aiGenerated') : t('cms.pages.aiFallback'))
      setEditing({ id: page.id, title: page.title, data: page.blocks as Data })
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.generateFailed'))
    } finally {
      setGenerating(false)
    }
  }

  async function openEditor(id: number) {
    try {
      const page = await getPage(session, id)
      setEditing({ id: page.id, title: page.title, data: page.blocks as Data })
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.openFailed'))
    }
  }

  async function onSave(data: Data) {
    if (!editing) return
    try {
      await updatePage(session, editing.id, { blocks: data })
      setEditing(null)
      await reload()
      setMsg(t('cms.common.saved'))
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.saveFailed'))
    }
  }

  async function togglePublish(p: PageListItem) {
    try {
      await publishPage(session, p.id, p.status !== 'published')
      await reload()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.actionFailed'))
    }
  }

  // 确认走 AlertDialog：原生 confirm 的按钮文字跟随系统语言，多语言直接失效。
  async function onDelete(p: PageListItem) {
    try {
      await deletePage(session, p.id)
      await reload()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.deleteFailed'))
    }
  }

  const sorted = useMemo(
    () =>
      [...items]
        .filter((p) => !localeFilter || p.locale === localeFilter)
        .sort((a, b) => a.sortOrder - b.sortOrder),
    [items, localeFilter],
  )

  return (
    <div className="grid gap-4">
      <PageHeader
        title={t('cms.pages.title')}
        description={t('cms.pages.description')}
        icon={<FileText className="h-4 w-4" />}
        actions={
          <div className="flex items-center gap-2">
            {siteLocales.length > 0 ? (
              <select
                className="h-9 rounded-md border border-border/60 bg-background px-2 text-sm"
                value={localeFilter}
                onChange={(e) => setLocaleFilter(e.target.value)}
              >
                <option value="">{t('cms.common.allLanguages')}</option>
                {siteLocales.map((l) => (
                  <option key={l} value={l}>
                    {langName(l)}
                  </option>
                ))}
              </select>
            ) : null}
            {canCreate ? (
              <>
                <Button onClick={() => setAiOpen(true)} size="sm" variant="outline">
                  <Sparkles className="mr-1 h-4 w-4" /> {t('cms.pages.aiGenerate')}
                </Button>
                <Button onClick={() => setCreateOpen(true)} size="sm">
                  <Plus className="mr-1 h-4 w-4" /> {t('cms.pages.new')}
                </Button>
              </>
            ) : null}
          </div>
        }
      />

      {msg ? <div className="rounded-lg border border-border/60 bg-muted/40 px-3 py-2 text-sm">{msg}</div> : null}

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex justify-center py-16">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
          ) : sorted.length === 0 ? (
            <p className="py-16 text-center text-sm text-muted-foreground">{t('cms.pages.empty')}</p>
          ) : (
            <div className="divide-y divide-border/50">
              {sorted.map((p) => (
                <div key={p.id} className="flex flex-wrap items-center gap-3 px-4 py-3.5">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-medium">{p.title}</span>
                      {p.isSystem ? <Badge variant="outline" className="text-[10px]">{t('cms.pages.system')}</Badge> : null}
                      {p.locale ? (
                        <Badge variant="outline" className="text-[10px]">{langName(p.locale)}</Badge>
                      ) : null}
                      <Badge variant={p.status === 'published' ? 'default' : 'secondary'} className="text-[10px]">
                        {p.status === 'published' ? t('cms.common.published') : t('cms.common.draft')}
                      </Badge>
                    </div>
                    <div className="mt-0.5 text-xs text-muted-foreground">/{p.slug === 'home' ? '' : p.slug}</div>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <a
                      href={p.slug === 'home' ? '/' : `/${p.slug}`}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex h-8 items-center gap-1 rounded-md px-2 text-xs text-muted-foreground hover:bg-muted"
                    >
                      <ExternalLink className="h-3.5 w-3.5" /> {t('cms.pages.preview')}
                    </a>
                    {canUpdate ? (
                      <Button size="sm" variant="outline" onClick={() => openEditor(p.id)}>
                        {t('common.edit')}
                      </Button>
                    ) : null}
                    {canCreate && siteLocales.length > 0 ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setTrans({ source: p, locale: siteLocales.find((l) => l !== p.locale) || siteLocales[0], useAi: true })}
                      >
                        {t('cms.pages.translate')}
                      </Button>
                    ) : null}
                    {canPublish ? (
                      <Button size="sm" variant="ghost" onClick={() => togglePublish(p)}>
                        {p.status === 'published' ? t('cms.common.toDraft') : t('cms.common.publish')}
                      </Button>
                    ) : null}
                    {canDelete && !p.isSystem ? (
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button size="sm" variant="ghost" className="text-destructive">
                            {t('common.delete')}
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>{t('common.delete')}</AlertDialogTitle>
                            <AlertDialogDescription>
                              {t('cms.pages.confirmDelete').replace('{title}', p.title)}
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                            <AlertDialogAction
                              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                              onClick={() => void onDelete(p)}
                            >
                              {t('common.delete')}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('cms.pages.new')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>{t('cms.common.title')}</Label>
              <Input value={newPage.title} onChange={(e) => setNewPage((s) => ({ ...s, title: e.target.value }))} placeholder={t('cms.pages.titlePlaceholder')} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>{t('cms.common.slug')}</Label>
                <Input
                  value={newPage.slug}
                  onChange={(e) => setNewPage((s) => ({ ...s, slug: e.target.value }))}
                  placeholder="solutions"
                />
              </div>
              <div>
                <Label>{t('cms.common.language')}</Label>
                <Input
                  value={newPage.locale}
                  onChange={(e) => setNewPage((s) => ({ ...s, locale: e.target.value }))}
                  placeholder="default / zh-CN / en-US"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={onCreate} disabled={creating || !newPage.title || !newPage.slug}>
              {creating ? t('cms.common.creating') : t('cms.pages.createAndEdit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={aiOpen} onOpenChange={setAiOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-1.5">
              <Sparkles className="h-4 w-4 text-primary" /> {t('cms.pages.aiDialogTitle')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              {t('cms.pages.aiHint')}
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>{t('cms.common.title')}</Label>
                <Input value={ai.title} onChange={(e) => setAi((s) => ({ ...s, title: e.target.value }))} placeholder={t('cms.pages.aiTitlePlaceholder')} />
              </div>
              <div>
                <Label>{t('cms.common.slug')}</Label>
                <Input value={ai.slug} onChange={(e) => setAi((s) => ({ ...s, slug: e.target.value }))} placeholder="solutions" />
              </div>
            </div>
            <div>
              <Label>{t('cms.pages.aiPrompt')}</Label>
              <Textarea
                rows={4}
                value={ai.prompt}
                onChange={(e) => setAi((s) => ({ ...s, prompt: e.target.value }))}
                placeholder={t('cms.pages.aiPromptPlaceholder')}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAiOpen(false)}>{t('common.cancel')}</Button>
            <Button onClick={onGenerate} disabled={generating || !ai.slug || ai.prompt.length < 4}>
              {generating ? t('cms.pages.generating') : t('cms.pages.generateDraft')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!trans} onOpenChange={(o) => !o && setTrans(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('cms.pages.transDialogTitle')}</DialogTitle>
          </DialogHeader>
          {trans ? (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {t('cms.pages.transHint')
                  .replace('{title}', trans.source.title)
                  .replace('{locale}', langName(trans.source.locale || ''))}
              </p>
              <div>
                <Label>{t('cms.pages.transTarget')}</Label>
                <select
                  className="mt-1 h-9 w-full rounded-md border border-border/60 bg-background px-2 text-sm"
                  value={trans.locale}
                  onChange={(e) => setTrans((t) => (t ? { ...t, locale: e.target.value } : t))}
                >
                  {siteLocales.filter((l) => l !== trans.source.locale).map((l) => (
                    <option key={l} value={l}>
                      {langName(l)}
                    </option>
                  ))}
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={trans.useAi}
                  onChange={(e) => setTrans((t) => (t ? { ...t, useAi: e.target.checked } : t))}
                />
                {t('cms.pages.transUseAi')}
              </label>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setTrans(null)}>{t('common.cancel')}</Button>
            <Button onClick={onTranslate} disabled={translating}>
              {translating ? t('cms.common.creating') : t('cms.pages.transCreate')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {editing ? (
        <PageEditor
          title={editing.title}
          initialData={editing.data}
          onSave={onSave}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </div>
  )
}
