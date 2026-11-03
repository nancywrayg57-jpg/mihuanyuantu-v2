'use client'

import { Notebook, Plus } from 'lucide-react'
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
import { Textarea } from '@/components/ui/textarea'
import { VditorEditor } from '@/components/cms/vditor-editor'
import { useAuth } from '@/hooks/useAuth'
import { hasAnyPermission } from '@/lib/auth'
import { useT } from '@/lib/i18n'
import {
  createPost,
  deletePost,
  getPost,
  listPosts,
  publishPost,
  updatePost,
  type PostListItem,
} from '@/lib/cms-api'

type Form = {
  id?: number
  title: string
  slug: string
  excerpt: string
  coverImage: string
  tags: string
  body: string
}

const EMPTY: Form = { title: '', slug: '', excerpt: '', coverImage: '', tags: '', body: '' }

export default function CmsPostsPage() {
  const t = useT()
  const { session } = useAuth()
  const [items, setItems] = useState<PostListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<Form>(EMPTY)
  const [saving, setSaving] = useState(false)

  const canCreate = hasAnyPermission(session, ['cms:post:create'])
  const canUpdate = hasAnyPermission(session, ['cms:post:update'])
  const canPublish = hasAnyPermission(session, ['cms:post:publish'])
  const canDelete = hasAnyPermission(session, ['cms:post:delete'])

  const reload = useCallback(async () => {
    if (!session) return
    setLoading(true)
    try {
      const res = await listPosts(session)
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

  function openCreate() {
    setForm(EMPTY)
    setOpen(true)
  }

  async function openEdit(id: number) {
    try {
      const p = await getPost(session, id)
      setForm({
        id: p.id,
        title: p.title,
        slug: p.slug,
        excerpt: p.excerpt || '',
        coverImage: p.coverImage || '',
        tags: (p.tags || []).join(', '),
        body: p.body || '',
      })
      setOpen(true)
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.openFailed'))
    }
  }

  async function onSave() {
    setSaving(true)
    setMsg('')
    const body = {
      title: form.title,
      slug: form.slug,
      excerpt: form.excerpt,
      coverImage: form.coverImage,
      tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
      body: form.body,
    }
    try {
      if (form.id) await updatePost(session, form.id, body)
      else await createPost(session, { ...body, status: 'draft' })
      setOpen(false)
      await reload()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  async function togglePublish(p: PostListItem) {
    try {
      await publishPost(session, p.id, p.status !== 'published')
      await reload()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.actionFailed'))
    }
  }

  // 确认走 AlertDialog：原生 confirm 的按钮文字跟随系统语言，多语言直接失效。
  async function onDelete(p: PostListItem) {
    try {
      await deletePost(session, p.id)
      await reload()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.deleteFailed'))
    }
  }

  return (
    <div className="grid gap-4">
      <PageHeader
        title={t('cms.posts.title')}
        description={t('cms.posts.description')}
        icon={<Notebook className="h-4 w-4" />}
        actions={canCreate ? <Button size="sm" onClick={openCreate}><Plus className="mr-1 h-4 w-4" />{t('cms.posts.new')}</Button> : null}
      />
      {msg ? <div className="rounded-lg border border-border/60 bg-muted/40 px-3 py-2 text-sm">{msg}</div> : null}

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex justify-center py-16"><div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div>
          ) : items.length === 0 ? (
            <p className="py-16 text-center text-sm text-muted-foreground">{t('cms.posts.empty')}</p>
          ) : (
            <div className="divide-y divide-border/50">
              {items.map((p) => (
                <div key={p.id} className="flex flex-wrap items-center gap-3 px-4 py-3.5">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-medium">{p.title}</span>
                      <Badge variant={p.status === 'published' ? 'default' : 'secondary'} className="text-[10px]">
                        {p.status === 'published' ? t('cms.common.published') : t('cms.common.draft')}
                      </Badge>
                    </div>
                    <div className="mt-0.5 text-xs text-muted-foreground">/blog/{p.slug}</div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {canUpdate ? <Button size="sm" variant="outline" onClick={() => openEdit(p.id)}>{t('common.edit')}</Button> : null}
                    {canPublish ? <Button size="sm" variant="ghost" onClick={() => togglePublish(p)}>{p.status === 'published' ? t('cms.common.toDraft') : t('cms.common.publish')}</Button> : null}
                    {canDelete ? (
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
                              {t('cms.posts.confirmDelete').replace('{title}', p.title)}
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

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader><DialogTitle>{form.id ? t('cms.posts.editTitle') : t('cms.posts.new')}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div><Label>{t('cms.common.title')}</Label><Input value={form.title} onChange={(e) => setForm((s) => ({ ...s, title: e.target.value }))} /></div>
              <div><Label>slug</Label><Input value={form.slug} onChange={(e) => setForm((s) => ({ ...s, slug: e.target.value }))} /></div>
            </div>
            <div><Label>{t('cms.posts.excerpt')}</Label><Textarea rows={2} value={form.excerpt} onChange={(e) => setForm((s) => ({ ...s, excerpt: e.target.value }))} /></div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div><Label>{t('cms.posts.coverImage')}</Label><Input value={form.coverImage} onChange={(e) => setForm((s) => ({ ...s, coverImage: e.target.value }))} /></div>
              <div><Label>{t('cms.posts.tags')}</Label><Input value={form.tags} onChange={(e) => setForm((s) => ({ ...s, tags: e.target.value }))} /></div>
            </div>
            <div>
              <Label>{t('cms.posts.body')}</Label>
              {open ? (
                <VditorEditor
                  value={form.body}
                  onChange={(v) => setForm((s) => ({ ...s, body: v }))}
                  height={360}
                />
              ) : null}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>{t('common.cancel')}</Button>
            <Button onClick={onSave} disabled={saving || !form.title || !form.slug}>{saving ? t('cms.common.saving') : t('common.save')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
