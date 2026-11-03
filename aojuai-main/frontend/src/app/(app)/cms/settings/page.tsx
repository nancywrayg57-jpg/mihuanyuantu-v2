'use client'

import { Settings } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { PageHeader } from '@/components/page/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/hooks/useAuth'
import { hasAnyPermission } from '@/lib/auth'
import { useT } from '@/lib/i18n'
import {
  getAdminSettings,
  getCmsAiConfig,
  updateCmsAiConfig,
  updateSettings,
  type CmsAiConfig,
  type SiteSettings,
} from '@/lib/cms-api'

export default function CmsSettingsPage() {
  const t = useT()
  const { session } = useAuth()
  const [s, setS] = useState<SiteSettings>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const canUpdate = hasAnyPermission(session, ['cms:settings:update'])

  const [ai, setAi] = useState<CmsAiConfig>({ mode: 'inherit' })
  const [aiKey, setAiKey] = useState('')
  const [aiSaving, setAiSaving] = useState(false)
  const [aiMsg, setAiMsg] = useState('')

  const reload = useCallback(async () => {
    if (!session) return
    setLoading(true)
    try {
      const [res, aiRes] = await Promise.all([getAdminSettings(session), getCmsAiConfig(session)])
      setS(res.settings || {})
      setAi(aiRes)
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t('cms.common.loadFailed'))
    } finally {
      setLoading(false)
    }
  }, [session, t])

  async function onSaveAi() {
    setAiSaving(true)
    setAiMsg('')
    try {
      const saved = await updateCmsAiConfig(session, {
        mode: ai.mode,
        baseUrl: ai.baseUrl || undefined,
        model: ai.model || undefined,
        temperature: ai.temperature ?? undefined,
        maxTokens: ai.maxTokens ?? undefined,
        apiKey: aiKey || undefined,
      })
      setAi(saved)
      setAiKey('')
      setAiMsg(t('cms.settings.aiSaved'))
    } catch (e) {
      setAiMsg(e instanceof Error ? e.message : t('cms.common.saveFailed'))
    } finally {
      setAiSaving(false)
    }
  }

  useEffect(() => {
    void reload()
  }, [reload])

  function set<K extends keyof SiteSettings>(k: K, v: SiteSettings[K]) {
    setS((prev) => ({ ...prev, [k]: v }))
  }
  function setSocial(k: 'github' | 'x' | 'linkedin', v: string) {
    setS((prev) => ({ ...prev, social: { ...(prev.social || {}), [k]: v } }))
  }

  async function onSave() {
    setSaving(true)
    setMsg('')
    try {
      await updateSettings(session, s)
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
        title={t('cms.settings.title')}
        description={t('cms.settings.description')}
        icon={<Settings className="h-4 w-4" />}
        actions={canUpdate ? <Button size="sm" onClick={onSave} disabled={saving}>{saving ? t('cms.common.saving') : t('common.save')}</Button> : null}
      />
      {msg ? <div className="rounded-lg border border-border/60 bg-muted/40 px-3 py-2 text-sm">{msg}</div> : null}
      {loading ? (
        <div className="flex justify-center py-16"><div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle className="text-base">{t('cms.settings.brand')}</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div><Label>{t('cms.settings.brandName')}</Label><Input value={s.brandName || ''} disabled={!canUpdate} onChange={(e) => set('brandName', e.target.value)} /></div>
              <div><Label>{t('cms.settings.tagline')}</Label><Input value={s.tagline || ''} disabled={!canUpdate} onChange={(e) => set('tagline', e.target.value)} /></div>
              <div><Label>Logo URL</Label><Input value={s.logo || ''} disabled={!canUpdate} onChange={(e) => set('logo', e.target.value)} /></div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">{t('cms.settings.contactSection')}</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div><Label>{t('cms.settings.contactEmail')}</Label><Input value={s.contactEmail || ''} disabled={!canUpdate} onChange={(e) => set('contactEmail', e.target.value)} /></div>
              <div><Label>{t('cms.settings.footerText')}</Label><Textarea rows={2} value={s.footerText || ''} disabled={!canUpdate} onChange={(e) => set('footerText', e.target.value)} /></div>
              <div className="grid grid-cols-3 gap-2">
                <div><Label>GitHub</Label><Input value={s.social?.github || ''} disabled={!canUpdate} onChange={(e) => setSocial('github', e.target.value)} /></div>
                <div><Label>X</Label><Input value={s.social?.x || ''} disabled={!canUpdate} onChange={(e) => setSocial('x', e.target.value)} /></div>
                <div><Label>LinkedIn</Label><Input value={s.social?.linkedin || ''} disabled={!canUpdate} onChange={(e) => setSocial('linkedin', e.target.value)} /></div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">{t('cms.settings.i18nSection')}</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div>
                <Label>{t('cms.settings.enabledLocales')}</Label>
                <Input
                  value={(s.locales || []).join(', ')}
                  disabled={!canUpdate}
                  placeholder="zh-CN, en-US"
                  onChange={(e) => set('locales', e.target.value.split(',').map((x) => x.trim()).filter(Boolean))}
                />
              </div>
              <div>
                <Label>{t('cms.settings.defaultLocale')}</Label>
                <Input value={s.defaultLocale || ''} disabled={!canUpdate} placeholder="zh-CN" onChange={(e) => set('defaultLocale', e.target.value.trim())} />
              </div>
              <p className="text-xs text-muted-foreground">{t('cms.settings.i18nHint')}</p>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader><CardTitle className="text-base">{t('cms.settings.scriptsSection')}</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
                {t('cms.settings.scriptsWarning')}
              </p>
              <div>
                <Label>{t('cms.settings.headHtml')}</Label>
                <Textarea rows={5} className="font-mono text-xs" disabled={!canUpdate} value={s.headHtml || ''} onChange={(e) => set('headHtml', e.target.value)} placeholder={t('cms.settings.headPlaceholder')} />
              </div>
              <div>
                <Label>{t('cms.settings.bodyHtml')}</Label>
                <Textarea rows={5} className="font-mono text-xs" disabled={!canUpdate} value={s.bodyHtml || ''} onChange={(e) => set('bodyHtml', e.target.value)} placeholder={t('cms.settings.bodyPlaceholder')} />
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">{t('cms.settings.aiSection')}</CardTitle>
              {canUpdate ? (
                <Button size="sm" onClick={onSaveAi} disabled={aiSaving}>
                  {aiSaving ? t('cms.common.saving') : t('cms.settings.aiSave')}
                </Button>
              ) : null}
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-xs text-muted-foreground">
                {t('cms.settings.aiHintPrefix')} <b>{t('cms.settings.aiHintInherit')}</b>
                {t('cms.settings.aiHintSuffix').replace(
                  '{state}',
                  ai.systemConfigured ? t('cms.settings.aiConfigured') : t('cms.settings.aiNotConfigured'),
                )}
              </p>
              {aiMsg ? <div className="rounded-lg border border-border/60 bg-muted/40 px-3 py-2 text-sm">{aiMsg}</div> : null}
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input type="radio" disabled={!canUpdate} checked={(ai.mode || 'inherit') === 'inherit'} onChange={() => setAi((a) => ({ ...a, mode: 'inherit' }))} />
                  {t('cms.settings.aiInherit')}
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="radio" disabled={!canUpdate} checked={ai.mode === 'custom'} onChange={() => setAi((a) => ({ ...a, mode: 'custom' }))} />
                  {t('cms.settings.aiCustom')}
                </label>
              </div>
              {ai.mode === 'custom' ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <Label>{t('cms.settings.aiBaseUrl')}</Label>
                    <Input disabled={!canUpdate} value={ai.baseUrl || ''} onChange={(e) => setAi((a) => ({ ...a, baseUrl: e.target.value }))} placeholder="https://api.openai.com/v1" />
                  </div>
                  <div>
                    <Label>{t('cms.settings.aiModel')}</Label>
                    <Input disabled={!canUpdate} value={ai.model || ''} onChange={(e) => setAi((a) => ({ ...a, model: e.target.value }))} placeholder="gpt-4o-mini / claude-… " />
                  </div>
                  <div>
                    <Label>
                      {t('cms.settings.aiApiKey')}
                      {ai.hasApiKey ? t('cms.settings.aiApiKeySet') : ''}
                    </Label>
                    <Input type="password" disabled={!canUpdate} value={aiKey} onChange={(e) => setAiKey(e.target.value)} placeholder={ai.hasApiKey ? '••••••••' : 'sk-…'} />
                  </div>
                  <div>
                    <Label>temperature</Label>
                    <Input type="number" step="0.1" disabled={!canUpdate} value={ai.temperature ?? ''} onChange={(e) => setAi((a) => ({ ...a, temperature: e.target.value === '' ? null : Number(e.target.value) }))} placeholder="0.4" />
                  </div>
                  <div>
                    <Label>max tokens</Label>
                    <Input type="number" disabled={!canUpdate} value={ai.maxTokens ?? ''} onChange={(e) => setAi((a) => ({ ...a, maxTokens: e.target.value === '' ? null : Number(e.target.value) }))} placeholder="4096" />
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
