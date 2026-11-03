'use client'

import { useCallback, useEffect, useState } from 'react'
import { Pencil, Plus, RefreshCcw, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'
import { ApiError } from '@/lib/api'
import { hasAnyPermission } from '@/lib/auth'
import { useT } from '@/lib/i18n'
import { sampleItemsApi, type SampleItem } from '@/lib/sample-items-api'

/**
 * 官方能力包样例页。它同时是**新模块要照抄的模板**，所以刻意遵守基座的几条约定：
 *
 * - 文案一律走 `t()`（语言包在 lib/i18n/locales/sample-items.ts），不写死中文
 * - 新建/编辑用 `Dialog` 表单，不用 `window.prompt`
 *   （原生弹窗一次只能填一个字段、样式不受控、按钮文字跟随系统语言改不了）
 * - 删除用确认 Dialog，不用 `window.confirm`
 * - 按钮按权限码渲染，权限不足直接不渲染，而不是点了再报错
 */
export default function SampleItemsPage() {
  const t = useT()
  const { session } = useAuth()
  const { targetTenantId } = useTenant()
  const [items, setItems] = useState<SampleItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState({ code: '', name: '', description: '' })
  const [editing, setEditing] = useState<SampleItem | null>(null)
  const [editName, setEditName] = useState('')
  const [removing, setRemoving] = useState<SampleItem | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const page = await sampleItemsApi.list({ session, tenantId: targetTenantId })
      setItems(page.list)
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : t('sampleItems.error.load'))
    } finally {
      setLoading(false)
    }
  }, [session, targetTenantId, t])

  useEffect(() => {
    void load()
  }, [load])

  if (!session) return null

  const canCreate = hasAnyPermission(session, ['sample_items:create'])
  const canUpdate = hasAnyPermission(session, ['sample_items:update'])
  const canDelete = hasAnyPermission(session, ['sample_items:delete'])
  const context = { session, tenantId: targetTenantId }

  async function submitCreate() {
    setSubmitting(true)
    setError(null)
    try {
      await sampleItemsApi.create(
        {
          code: createForm.code.trim(),
          name: createForm.name.trim(),
          description: createForm.description.trim() || undefined,
        },
        context,
      )
      setCreateOpen(false)
      setCreateForm({ code: '', name: '', description: '' })
      await load()
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : t('sampleItems.error.create'))
    } finally {
      setSubmitting(false)
    }
  }

  async function submitEdit() {
    if (!editing) return
    setSubmitting(true)
    setError(null)
    try {
      await sampleItemsApi.update(editing.id, { name: editName.trim() }, context)
      setEditing(null)
      await load()
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : t('sampleItems.error.update'))
    } finally {
      setSubmitting(false)
    }
  }

  async function submitRemove() {
    if (!removing) return
    setSubmitting(true)
    setError(null)
    try {
      await sampleItemsApi.remove(removing.id, context)
      setRemoving(null)
      await load()
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : t('sampleItems.error.delete'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{t('sampleItems.title')}</CardTitle>
          <CardDescription>{t('sampleItems.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={() => void load()} disabled={loading}>
                <RefreshCcw className="mr-2 h-4 w-4" />
                {t('sampleItems.action.refresh')}
              </Button>
              {error ? <span className="text-sm text-destructive">{error}</span> : null}
            </div>
            {canCreate ? (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                {t('sampleItems.action.create')}
              </Button>
            ) : null}
          </div>

          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('sampleItems.column.code')}</TableHead>
                  <TableHead>{t('sampleItems.column.name')}</TableHead>
                  <TableHead>{t('sampleItems.column.description')}</TableHead>
                  <TableHead className="text-right">{t('sampleItems.column.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center text-muted-foreground">
                      {loading ? t('sampleItems.loading') : t('sampleItems.empty')}
                    </TableCell>
                  </TableRow>
                ) : (
                  items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-mono">{item.code}</TableCell>
                      <TableCell>{item.name}</TableCell>
                      <TableCell>{item.description || '-'}</TableCell>
                      <TableCell className="space-x-2 text-right">
                        {canUpdate ? (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setEditing(item)
                              setEditName(item.name)
                            }}
                          >
                            <Pencil className="mr-1 h-3.5 w-3.5" />
                            {t('sampleItems.action.edit')}
                          </Button>
                        ) : null}
                        {canDelete ? (
                          <Button size="sm" variant="destructive" onClick={() => setRemoving(item)}>
                            <Trash2 className="mr-1 h-3.5 w-3.5" />
                            {t('sampleItems.action.delete')}
                          </Button>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('sampleItems.dialog.createTitle')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>{t('sampleItems.column.code')}</Label>
              <Input
                value={createForm.code}
                onChange={(e) => setCreateForm((s) => ({ ...s, code: e.target.value }))}
                placeholder={t('sampleItems.prompt.code')}
              />
            </div>
            <div>
              <Label>{t('sampleItems.column.name')}</Label>
              <Input
                value={createForm.name}
                onChange={(e) => setCreateForm((s) => ({ ...s, name: e.target.value }))}
              />
            </div>
            <div>
              <Label>{t('sampleItems.column.description')}</Label>
              <Input
                value={createForm.description}
                onChange={(e) => setCreateForm((s) => ({ ...s, description: e.target.value }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={submitting}>
              {t('sampleItems.action.cancel')}
            </Button>
            <Button
              onClick={() => void submitCreate()}
              disabled={submitting || !createForm.code.trim() || !createForm.name.trim()}
            >
              {t('sampleItems.action.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('sampleItems.dialog.editTitle')}</DialogTitle>
          </DialogHeader>
          <div>
            <Label>{t('sampleItems.column.name')}</Label>
            <Input value={editName} onChange={(e) => setEditName(e.target.value)} />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)} disabled={submitting}>
              {t('sampleItems.action.cancel')}
            </Button>
            <Button
              onClick={() => void submitEdit()}
              disabled={submitting || !editName.trim() || editName.trim() === editing?.name}
            >
              {t('sampleItems.action.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('sampleItems.dialog.deleteTitle')}</DialogTitle>
            <DialogDescription>
              {t('sampleItems.dialog.deleteConfirm').replace('{name}', removing?.name ?? '')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRemoving(null)} disabled={submitting}>
              {t('sampleItems.action.cancel')}
            </Button>
            <Button variant="destructive" onClick={() => void submitRemove()} disabled={submitting}>
              {t('sampleItems.action.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
