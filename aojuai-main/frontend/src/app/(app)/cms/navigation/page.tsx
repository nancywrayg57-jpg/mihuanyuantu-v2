'use client'

import { ArrowDown, ArrowUp, GripVertical, Plus, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { PageHeader } from '@/components/page/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/hooks/useAuth'
import { hasAnyPermission } from '@/lib/auth'
import { useT } from '@/lib/i18n'
import { getAdminNavigation, updateNavigation, type NavItem } from '@/lib/cms-api'

function NavEditor({
  title,
  items,
  onChange,
  readOnly,
}: {
  title: string
  items: NavItem[]
  onChange: (items: NavItem[]) => void
  readOnly: boolean
}) {
  const t = useT()
  function update(i: number, patch: Partial<NavItem>) {
    onChange(items.map((it, idx) => (idx === i ? { ...it, ...patch } : it)))
  }
  function remove(i: number) {
    onChange(items.filter((_, idx) => idx !== i))
  }
  function move(i: number, dir: -1 | 1) {
    const j = i + dir
    if (j < 0 || j >= items.length) return
    const next = [...items]
    ;[next[i], next[j]] = [next[j], next[i]]
    onChange(next)
  }
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">{title}</CardTitle>
        {!readOnly ? (
          <Button size="sm" variant="outline" onClick={() => onChange([...items, { label: t('cms.navigation.newItem'), href: '/' }])}>
            <Plus className="mr-1 h-4 w-4" /> {t('cms.navigation.add')}
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-2">
        {items.length === 0 ? <p className="text-sm text-muted-foreground">{t('cms.navigation.empty')}</p> : null}
        {items.map((it, i) => (
          <div key={i} className="flex items-center gap-2 rounded-lg border border-border/50 p-2">
            <GripVertical className="h-4 w-4 shrink-0 text-muted-foreground" />
            <Input className="flex-1" placeholder={t('cms.navigation.itemLabel')} value={it.label} disabled={readOnly} onChange={(e) => update(i, { label: e.target.value })} />
            <Input className="flex-1" placeholder={t('cms.navigation.itemHref')} value={it.href} disabled={readOnly} onChange={(e) => update(i, { href: e.target.value })} />
            {!readOnly ? (
              <div className="flex items-center">
                <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => move(i, -1)}><ArrowUp className="h-4 w-4" /></Button>
                <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => move(i, 1)}><ArrowDown className="h-4 w-4" /></Button>
                <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={() => remove(i)}><Trash2 className="h-4 w-4" /></Button>
              </div>
            ) : null}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

export default function CmsNavigationPage() {
  const t = useT()
  const { session } = useAuth()
  const [header, setHeader] = useState<NavItem[]>([])
  const [footer, setFooter] = useState<NavItem[]>([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const [saving, setSaving] = useState(false)
  const canUpdate = hasAnyPermission(session, ['cms:nav:update'])

  const reload = useCallback(async () => {
    if (!session) return
    setLoading(true)
    try {
      const res = await getAdminNavigation(session)
      const h = res.list.find((x) => x.location === 'header')
      const f = res.list.find((x) => x.location === 'footer')
      setHeader(h?.items || [])
      setFooter(f?.items || [])
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.loadFailed'))
    } finally {
      setLoading(false)
    }
  }, [session, t])

  useEffect(() => {
    void reload()
  }, [reload])

  async function onSave() {
    setSaving(true)
    setMsg('')
    try {
      await updateNavigation(session, 'header', header)
      await updateNavigation(session, 'footer', footer)
      setMsg(t('cms.common.saved'))
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid gap-4">
      <PageHeader
        title={t('cms.navigation.title')}
        description={t('cms.navigation.description')}
        actions={canUpdate ? <Button size="sm" onClick={onSave} disabled={saving}>{saving ? t('cms.common.saving') : t('common.save')}</Button> : null}
      />
      {msg ? <div className="rounded-lg border border-border/60 bg-muted/40 px-3 py-2 text-sm">{msg}</div> : null}
      {loading ? (
        <div className="flex justify-center py-16"><div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <NavEditor title={t('cms.navigation.header')} items={header} onChange={setHeader} readOnly={!canUpdate} />
          <NavEditor title={t('cms.navigation.footer')} items={footer} onChange={setFooter} readOnly={!canUpdate} />
        </div>
      )}
    </div>
  )
}
