'use client'

import { useEffect, useMemo, useState } from 'react'
import { Mic, PencilLine, Plus, Save, Trash2, Volume2, Waves } from 'lucide-react'
import { toast } from 'sonner'

import { PageHeader } from '@/components/page/page-header'
import { SpeechVoiceClonePanel } from '@/components/speech/speech-voice-clone-panel'
import {
  buildProviderDraft,
  serializeProviderDraft,
  type ProviderDraft,
} from '@/components/speech/provider-form'
import { ConfigFieldGrid, StatusNote, SummaryPills, WorkspaceSwitch } from '@/components/speech/speech-settings-ui'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'
import { ApiError } from '@/lib/api'
import { useT } from '@/lib/i18n'
import { translateActive } from '@/lib/i18n/registry'
import {
  getSpeechConfig,
  listSpeechProviders,
  upsertSpeechConfig,
  type SpeechVoiceCloneWorkspaceItem,
  type SpeechProviderDescriptor,
  type SpeechTenantConfigView,
} from '@/lib/api/speech'

type PanelKey = 'tts' | 'stt' | 'barge-in' | 'voice-clone'
type BargeInMode = 'vad_onset' | 'asr_text' | 'stop_words' | 'client_abort'
type TtsProfileDraft = ProviderDraft & {
  id: string
  label: string
  allowVoiceClone: boolean
}

type SpeechSettingsShellProps = {
  initialPanel?: PanelKey
  embedded?: boolean
  onConfigSaved?: (config: SpeechTenantConfigView) => void | Promise<void>
}

function resolvePanel(value: string | null | undefined): PanelKey {
  if (value === 'stt') return 'stt'
  if (value === 'barge-in' || value === 'barge_in' || value === 'demo' || value === 'lab') return 'barge-in'
  if (value === 'voice-clone' || value === 'voice_clone' || value === 'voiceclone' || value === 'clone') return 'voice-clone'
  return 'tts'
}

function splitWordList(value: string) {
  return value
    .split(/\r?\n|,|，/u)
    .map((item) => item.trim())
    .filter(Boolean)
}

function providerSupportsVoiceClone(provider: SpeechProviderDescriptor | null | undefined) {
  return Boolean(provider?.category === 'tts' && provider.capabilities?.supportsVoiceClone)
}

function hasConfiguredSecrets(value: Record<string, boolean> | null | undefined) {
  return Boolean(value && Object.values(value).some(Boolean))
}

function getSecretsSet(config: SpeechTenantConfigView | null, section: 'tts' | 'stt') {
  const raw = config?.secretsSet
  if (!raw || typeof raw !== 'object') return {}
  const value = raw[section]
  return value && typeof value === 'object' ? (value as Record<string, boolean>) : {}
}

function getTtsProfileSecretsSet(config: SpeechTenantConfigView | null, profileId: string) {
  const fromProfiles = (config?.ttsProfiles || []).find((item) => item.id === profileId)?.secretsSet
  if (fromProfiles && typeof fromProfiles === 'object') return fromProfiles as Record<string, boolean>

  const raw = config?.secretsSet
  if (!raw || typeof raw !== 'object') return {}
  const value = raw.ttsProfiles
  if (!value || typeof value !== 'object') return {}
  const profileSecrets = (value as Record<string, unknown>)[profileId]
  return profileSecrets && typeof profileSecrets === 'object' ? (profileSecrets as Record<string, boolean>) : {}
}

function createTtsProfileId(seed?: string) {
  const normalized = String(seed || 'tts-profile')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
  const base = normalized || 'tts-profile'
  return `${base}-${Math.random().toString(36).slice(2, 8)}`
}

function createEmptyTtsProfileDraft(label = translateActive('system.speech.newModel')): TtsProfileDraft {
  return {
    id: createTtsProfileId(label),
    label,
    allowVoiceClone: false,
    providerId: '',
    settings: {},
    secretDrafts: {},
    secretsSet: {},
  }
}

function buildTtsProfileDrafts(
  providers: SpeechProviderDescriptor[],
  config: SpeechTenantConfigView | null,
) {
  const profiles =
    config?.ttsProfiles && config.ttsProfiles.length > 0
      ? config.ttsProfiles
      : config?.tts
        ? [
            {
              id: config.defaultTtsProfileId || config.tts.providerId || 'default-tts',
              label: translateActive('system.speech.defaultModel'),
              providerId: config.tts.providerId,
              settings: config.tts.settings,
              isDefault: true,
              allowVoiceClone: false,
              secretsSet: getSecretsSet(config, 'tts'),
            },
          ]
        : []

  const drafts = profiles.map((profile) => {
    const base = buildProviderDraft(
      providers,
      { providerId: profile.providerId, settings: profile.settings || {} },
      getTtsProfileSecretsSet(config, profile.id),
    )
    return {
      ...base,
      id: profile.id,
      label: profile.label || translateActive('system.speech.model'),
      allowVoiceClone: Boolean(profile.allowVoiceClone),
    }
  })

  if (drafts.length > 0) {
    return drafts
  }
  return [createEmptyTtsProfileDraft()]
}

export function SpeechSettingsShell({
  initialPanel,
  embedded = false,
  onConfigSaved,
}: SpeechSettingsShellProps) {
  const t = useT()
  const { session } = useAuth()
  const { targetTenantId, targetTenant } = useTenant()
  const effectiveTenantId = session?.isSuperuser ? targetTenantId : null

  const [activePanel, setActivePanel] = useState<PanelKey>(resolvePanel(initialPanel))
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [providers, setProviders] = useState<{ tts: SpeechProviderDescriptor[]; stt: SpeechProviderDescriptor[] }>({
    tts: [],
    stt: [],
  })
  const [, setConfig] = useState<SpeechTenantConfigView | null>(null)

  const [ttsProfiles, setTtsProfiles] = useState<TtsProfileDraft[]>([createEmptyTtsProfileDraft()])
  const [defaultTtsProfileId, setDefaultTtsProfileId] = useState('')
  const [editorProfileId, setEditorProfileId] = useState<string | null>(null)
  const [voiceCloneRefreshNonce, setVoiceCloneRefreshNonce] = useState(0)
  const [sttDraft, setSttDraft] = useState<ProviderDraft>({
    providerId: '',
    settings: {},
    secretDrafts: {},
    secretsSet: {},
  })
  const [bargeInEnabled, setBargeInEnabled] = useState(true)
  const [bargeInMode, setBargeInMode] = useState<BargeInMode>('vad_onset')
  const [bargeInStopWordsText, setBargeInStopWordsText] = useState('')
  const [bargeInWakeWordsText, setBargeInWakeWordsText] = useState('')

  const ttsProviderMap = useMemo(
    () => new Map(providers.tts.map((provider) => [provider.id, provider])),
    [providers.tts],
  )
  const sttProviderMap = useMemo(
    () => new Map(providers.stt.map((provider) => [provider.id, provider])),
    [providers.stt],
  )

  const editorProfile = useMemo(
    () => ttsProfiles.find((profile) => profile.id === editorProfileId) || null,
    [editorProfileId, ttsProfiles],
  )
  const editorProvider = editorProfile ? ttsProviderMap.get(editorProfile.providerId) || null : null
  const currentSttProvider = sttProviderMap.get(sttDraft.providerId) || null
  const configuredTtsProfiles = ttsProfiles.filter((profile) => profile.providerId)

  useEffect(() => {
    setActivePanel(resolvePanel(initialPanel))
  }, [initialPanel])

  useEffect(() => {
    if (!session) return
    if (session.isSuperuser && !effectiveTenantId) return

    let cancelled = false

    async function loadSpeechSettings() {
      setLoading(true)
      setLoadError(null)
      try {
        const [providerCatalog, configData] = await Promise.all([
          listSpeechProviders({ session, tenantId: effectiveTenantId }),
          getSpeechConfig({ session, tenantId: effectiveTenantId }),
        ])
        if (cancelled) return

        const nextProviders = {
          tts: providerCatalog.tts || [],
          stt: providerCatalog.stt || [],
        }
        setProviders(nextProviders)
        setConfig(configData)
        setTtsProfiles(buildTtsProfileDrafts(nextProviders.tts, configData))
        setDefaultTtsProfileId(
          configData.defaultTtsProfileId ||
            configData.ttsProfiles?.find((item) => item.isDefault)?.id ||
            configData.ttsProfiles?.[0]?.id ||
            '',
        )
        setSttDraft(
          buildProviderDraft(
            nextProviders.stt,
            configData.stt || configData.asr || null,
            getSecretsSet(configData, 'stt'),
          ),
        )
        setBargeInEnabled(configData.bargeIn?.enabled ?? true)
        setBargeInMode((configData.bargeIn?.mode as BargeInMode | undefined) || 'vad_onset')
        setBargeInStopWordsText((configData.bargeIn?.stopWords || []).join('\n'))
        setBargeInWakeWordsText((configData.bargeIn?.wakeWords || []).join('\n'))
      } catch (error) {
        if (cancelled) return
        const message = error instanceof ApiError ? error.message : t('system.speech.loadSettingsFailed')
        setLoadError(message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadSpeechSettings()
    return () => {
      cancelled = true
    }
  }, [effectiveTenantId, session])

  function updateTtsProfile(profileId: string, updater: (draft: TtsProfileDraft) => TtsProfileDraft) {
    setTtsProfiles((current) => current.map((item) => (item.id === profileId ? updater(item) : item)))
  }

  function getSharedTtsSecretsSet(providerId: string) {
    return (
      ttsProfiles.find((profile) => profile.providerId === providerId && hasConfiguredSecrets(profile.secretsSet))
        ?.secretsSet || {}
    )
  }

  function handleTtsProviderChange(profileId: string, providerId: string) {
    const provider = ttsProviderMap.get(providerId) || null
    const profile = ttsProfiles.find((item) => item.id === profileId) || createEmptyTtsProfileDraft()
    const nextDraft = buildProviderDraft(
      providers.tts,
      { providerId, settings: providerId === profile.providerId ? profile.settings : {} },
      providerId ? (providerId === profile.providerId ? profile.secretsSet : getSharedTtsSecretsSet(providerId)) : {},
    )
    updateTtsProfile(profileId, (current) => ({
      ...current,
      ...nextDraft,
      label: current.label,
      allowVoiceClone: providerSupportsVoiceClone(provider) ? current.allowVoiceClone : false,
    }))
    if (!defaultTtsProfileId && providerId) {
      setDefaultTtsProfileId(profileId)
    }
  }

  function updateTtsField(profileId: string, key: string, value: unknown, options?: { secret?: boolean }) {
    updateTtsProfile(profileId, (current) => {
      if (options?.secret) {
        return {
          ...current,
          secretDrafts: {
            ...current.secretDrafts,
            [key]: String(value ?? ''),
          },
        }
      }
      return {
        ...current,
        settings: {
          ...current.settings,
          [key]: value,
        },
      }
    })
  }

  function handleUseVoiceClone(item: SpeechVoiceCloneWorkspaceItem) {
    if (!item.clone) return

    const clone = item.clone
    const providerId = clone.providerId || 'aliyun_qwen_tts'
    const cloneLabel = clone.displayName || item.asset.displayName || t('system.speech.personalVoice')
    const editableProfiles = ttsProfiles.length > 0 ? [...ttsProfiles] : [createEmptyTtsProfileDraft()]
    const targetIndex = editableProfiles.findIndex(
      (profile) => profile.id === defaultTtsProfileId && profile.providerId === providerId,
    )
    const existingProviderIndex = targetIndex >= 0 ? targetIndex : editableProfiles.findIndex((profile) => profile.providerId === providerId)

    let nextProfiles = editableProfiles
    let nextDefaultProfileId = defaultTtsProfileId

    if (existingProviderIndex >= 0) {
      const targetProfile = editableProfiles[existingProviderIndex]
      nextDefaultProfileId = targetProfile.id
      nextProfiles = editableProfiles.map((profile, index) =>
        index === existingProviderIndex
          ? {
              ...profile,
              label: profile.label || cloneLabel,
              providerId,
              allowVoiceClone: true,
              settings: {
                ...targetProfile.settings,
                model: clone.synthesisModel,
                voice: clone.remoteVoiceId,
                voiceCloneId: clone.id,
                ...(clone.languageType ? { languageType: clone.languageType } : {}),
              },
            }
          : profile,
      )
    } else {
      const freshProfile = createEmptyTtsProfileDraft(cloneLabel)
      nextDefaultProfileId = freshProfile.id
      nextProfiles = [
        ...editableProfiles,
        {
          ...freshProfile,
          label: cloneLabel,
          providerId,
          allowVoiceClone: true,
          settings: {
            model: clone.synthesisModel,
            voice: clone.remoteVoiceId,
            voiceCloneId: clone.id,
            ...(clone.languageType ? { languageType: clone.languageType } : {}),
          },
        },
      ]
    }

    setTtsProfiles(nextProfiles)
    setDefaultTtsProfileId(nextDefaultProfileId)
    toast.success(t('system.speech.defaultDraftWritten'))
  }

  function addTtsProfile() {
    const nextProfile = createEmptyTtsProfileDraft(`${t('system.speech.newModel')} ${ttsProfiles.length + 1}`)
    setTtsProfiles((current) => [...current, nextProfile])
    setEditorProfileId(nextProfile.id)
  }

  function removeTtsProfile(profileId: string) {
    const nextProfiles = ttsProfiles.filter((profile) => profile.id !== profileId)
    setTtsProfiles(nextProfiles.length > 0 ? nextProfiles : [createEmptyTtsProfileDraft()])
    if (defaultTtsProfileId === profileId) {
      setDefaultTtsProfileId(nextProfiles.find((profile) => profile.providerId)?.id || '')
    }
    if (editorProfileId === profileId) {
      setEditorProfileId(null)
    }
  }

  function handleSttProviderChange(providerId: string) {
    setSttDraft(buildProviderDraft(providers.stt, providerId ? { providerId, settings: {} } : null, {}))
  }

  function updateSttField(key: string, value: unknown, options?: { secret?: boolean }) {
    setSttDraft((current) => {
      if (options?.secret) {
        return {
          ...current,
          secretDrafts: {
            ...current.secretDrafts,
            [key]: String(value ?? ''),
          },
        }
      }
      return {
        ...current,
        settings: {
          ...current.settings,
          [key]: value,
        },
      }
    })
  }

  async function persistConfig(options?: {
    closeEditor?: boolean
    successMessage?: string
    profilesOverride?: TtsProfileDraft[]
    defaultProfileIdOverride?: string
  }) {
    if (!session) return null
    if (session.isSuperuser && !effectiveTenantId) return null

    setSaving(true)
    try {
      const sourceProfiles = options?.profilesOverride || ttsProfiles
      const sourceDefaultProfileId = options?.defaultProfileIdOverride ?? defaultTtsProfileId
      const configuredProfiles = sourceProfiles.filter((profile) => profile.providerId)
      const knownSecretFlagsByProvider = new Map<string, Record<string, boolean>>()
      for (const profile of configuredProfiles) {
        if (!profile.providerId) continue
        const current = knownSecretFlagsByProvider.get(profile.providerId) || {}
        const next: Record<string, boolean> = { ...current }
        for (const [key, configured] of Object.entries(profile.secretsSet || {})) {
          if (configured || current[key]) next[key] = true
        }
        knownSecretFlagsByProvider.set(profile.providerId, next)
      }

      const resolvedDefaultProfileId =
        configuredProfiles.find((profile) => profile.id === sourceDefaultProfileId)?.id || configuredProfiles[0]?.id || null

      const ttsProfilesPayload = configuredProfiles.map((profile) => {
        const provider = ttsProviderMap.get(profile.providerId) || null
        const inheritedSecretsSet = knownSecretFlagsByProvider.get(profile.providerId) || {}
        const serialized = serializeProviderDraft(
          {
            ...profile,
            secretsSet: {
              ...profile.secretsSet,
              ...inheritedSecretsSet,
            },
          },
          provider,
        )
        return {
          id: profile.id,
          label: profile.label,
          providerId: serialized.providerId,
          settings: serialized.settings,
          secrets: serialized.secrets,
          isDefault: profile.id === resolvedDefaultProfileId,
          allowVoiceClone: profile.allowVoiceClone,
        }
      })

      const sttPayload = sttDraft.providerId
        ? (() => {
            const serialized = serializeProviderDraft(sttDraft, currentSttProvider)
            return {
              providerId: serialized.providerId,
              settings: serialized.settings,
              secrets: serialized.secrets,
            }
          })()
        : null

      const nextConfig = await upsertSpeechConfig(
        {
          ttsProfiles: ttsProfilesPayload,
          defaultTtsProfileId: resolvedDefaultProfileId,
          stt: sttPayload,
          bargeIn: {
            enabled: bargeInEnabled,
            mode: bargeInMode,
            stopWords: splitWordList(bargeInStopWordsText),
            wakeWords: splitWordList(bargeInWakeWordsText),
          },
        },
        { session, tenantId: effectiveTenantId },
      )

      setConfig(nextConfig)
      setTtsProfiles(buildTtsProfileDrafts(providers.tts, nextConfig))
      setDefaultTtsProfileId(nextConfig.defaultTtsProfileId || '')
      setSttDraft(buildProviderDraft(providers.stt, nextConfig.stt || nextConfig.asr || null, getSecretsSet(nextConfig, 'stt')))
      setBargeInEnabled(nextConfig.bargeIn?.enabled ?? true)
      setBargeInMode((nextConfig.bargeIn?.mode as BargeInMode | undefined) || 'vad_onset')
      setBargeInStopWordsText((nextConfig.bargeIn?.stopWords || []).join('\n'))
      setBargeInWakeWordsText((nextConfig.bargeIn?.wakeWords || []).join('\n'))
      setVoiceCloneRefreshNonce((value) => value + 1)
      if (options?.closeEditor) {
        setEditorProfileId(null)
      }
      toast.success(options?.successMessage || t('system.speech.settingsSaved'))
      if (onConfigSaved) {
        await onConfigSaved(nextConfig)
      }
      return nextConfig
    } catch (error) {
      const message = error instanceof ApiError ? error.message : error instanceof Error ? error.message : t('system.speech.saveSettingsFailed')
      toast.error(message)
      return null
    } finally {
      setSaving(false)
    }
  }

  async function saveConfig() {
    await persistConfig()
  }

  async function saveEditorProfile() {
    await persistConfig({ closeEditor: true, successMessage: t('system.speech.modelConfigSaved') })
  }

  async function removeAndSaveTtsProfile(profileId: string) {
    const nextProfiles = ttsProfiles.filter((profile) => profile.id !== profileId)
    const normalizedProfiles = nextProfiles.length > 0 ? nextProfiles : [createEmptyTtsProfileDraft()]
    const nextDefaultProfileId =
      defaultTtsProfileId === profileId || !normalizedProfiles.some((profile) => profile.id === defaultTtsProfileId)
        ? normalizedProfiles.find((profile) => profile.providerId)?.id || ''
        : defaultTtsProfileId
    setTtsProfiles(normalizedProfiles)
    setDefaultTtsProfileId(nextDefaultProfileId)
    setEditorProfileId(null)
    await persistConfig({
      closeEditor: true,
      successMessage: t('system.speech.modelDeletedSaved'),
      profilesOverride: normalizedProfiles,
      defaultProfileIdOverride: nextDefaultProfileId,
    })
  }

  return (
    <div className="grid gap-6">
      {!embedded ? (
        <PageHeader
          title={t('system.speech.settingsTitle')}
          description={t('system.speech.settingsDescription')}
        />
      ) : null}

      <Card className="border-dashed">
        <CardContent className="flex flex-col gap-3 px-6 py-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="grid gap-1">
            <div className="text-sm font-medium">
              {t('system.speech.workspace').replace(
                '{name}',
                targetTenant?.name || t('system.speech.tenantFallback').replace('{id}', String(effectiveTenantId ?? '')),
              )}
            </div>
            <div className="text-sm text-muted-foreground">
              {t('system.speech.workspaceDescription')}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void saveConfig()} disabled={saving || loading}>
              <Save className="h-4 w-4" />
              {saving ? t('system.common.saving') : t('system.speech.saveSettings')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {loadError ? <StatusNote tone="error">{loadError}</StatusNote> : null}
      {loading ? <StatusNote tone="info">{t('system.speech.loadingConfig')}</StatusNote> : null}

      <WorkspaceSwitch
        value={activePanel}
        onChange={setActivePanel}
        options={[
          { value: 'tts', label: t('system.speech.ttsDefaultModel') },
          { value: 'voice-clone', label: t('system.speech.voiceClone') },
          { value: 'stt', label: t('system.speech.sttDefaultService') },
          { value: 'barge-in', label: t('system.speech.bargeInRules') },
        ]}
      />

      {activePanel === 'tts' ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Volume2 className="h-5 w-5" />
              {t('system.speech.ttsDefaultModel')}
            </CardTitle>
            <CardDescription>
              {t('system.speech.ttsDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            {configuredTtsProfiles.length === 0 ? (
              <StatusNote tone="warn">{t('system.speech.noTtsModel')}</StatusNote>
            ) : null}

            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={addTtsProfile}>
                <Plus className="h-4 w-4" />
                {t('system.speech.addModel')}
              </Button>
            </div>

            <div className="divide-y rounded-xl border">
              {ttsProfiles.map((profile) => {
                const provider = ttsProviderMap.get(profile.providerId) || null
                const isDefault = Boolean(profile.providerId) && profile.id === defaultTtsProfileId
                return (
                  <div key={profile.id} className="grid gap-3 px-4 py-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                    <div className="min-w-0 grid gap-2">
                      <div className="flex min-w-0 flex-wrap items-center gap-2">
                        <div className="truncate text-sm font-medium md:text-base">{profile.label}</div>
                        {isDefault ? <Badge>{t('system.speech.defaultBadge')}</Badge> : null}
                        {providerSupportsVoiceClone(provider) && profile.allowVoiceClone ? <Badge variant="secondary">{t('system.speech.cloneableBadge')}</Badge> : null}
                        {provider ? <Badge variant="outline">{provider.name}</Badge> : <Badge variant="outline">{t('system.common.unselected')}</Badge>}
                      </div>
                      <SummaryPills settings={profile.settings} />
                    </div>
                    <div className="flex flex-wrap gap-2 md:justify-end">
                      <Button variant="outline" size="sm" onClick={() => setEditorProfileId(profile.id)}>
                        <PencilLine className="h-4 w-4" />
                        {t('system.speech.edit')}
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => removeTtsProfile(profile.id)} disabled={ttsProfiles.length <= 1} aria-label={t('system.speech.deleteModel')}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {activePanel === 'stt' ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mic className="h-5 w-5" />
              {t('system.speech.sttDefaultService')}
            </CardTitle>
            <CardDescription>{t('system.speech.sttDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-2 md:max-w-md">
              <Label>{t('system.speech.recognitionProvider')}</Label>
              <Select value={sttDraft.providerId || '__none__'} onValueChange={(value) => handleSttProviderChange(value === '__none__' ? '' : value)}>
                <SelectTrigger>
                  <SelectValue placeholder={t('system.speech.chooseSttProvider')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">{t('system.common.notConfigured')}</SelectItem>
                  {providers.stt.map((provider) => (
                    <SelectItem key={provider.id} value={provider.id}>
                      {provider.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {currentSttProvider ? (
              <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">{currentSttProvider.description || t('system.common.noExtraDescription')}</div>
            ) : null}

            <ConfigFieldGrid idPrefix="stt-default" provider={currentSttProvider} draft={sttDraft} onChange={updateSttField} />
          </CardContent>
        </Card>
      ) : null}

      {activePanel === 'voice-clone' ? <SpeechVoiceClonePanel refreshNonce={voiceCloneRefreshNonce} onUseClone={handleUseVoiceClone} /> : null}

      {activePanel === 'barge-in' ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Waves className="h-5 w-5" />
              {t('system.speech.bargeInRules')}
            </CardTitle>
            <CardDescription>{t('system.speech.bargeInDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 lg:max-w-3xl">
            <div className="flex items-start gap-3 rounded-lg border p-3">
              <Checkbox id="speech-barge-enabled" checked={bargeInEnabled} onCheckedChange={(checked) => setBargeInEnabled(Boolean(checked))} />
              <div className="grid gap-1">
                <Label htmlFor="speech-barge-enabled">{t('system.speech.enableBargeIn')}</Label>
                <div className="text-xs text-muted-foreground">{t('system.speech.enableBargeInHint')}</div>
              </div>
            </div>

            <div className="grid gap-2 md:max-w-md">
              <Label>{t('system.speech.defaultMode')}</Label>
              <Select value={bargeInMode} onValueChange={(value) => setBargeInMode(value as BargeInMode)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="vad_onset">vad_onset</SelectItem>
                  <SelectItem value="asr_text">asr_text</SelectItem>
                  <SelectItem value="stop_words">stop_words</SelectItem>
                  <SelectItem value="client_abort">client_abort</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t('system.speech.stopWords')}</Label>
                <Textarea rows={6} value={bargeInStopWordsText} onChange={(event) => setBargeInStopWordsText(event.target.value)} />
              </div>
              <div className="grid gap-2">
                <Label>{t('system.speech.wakeWords')}</Label>
                <Textarea rows={6} value={bargeInWakeWordsText} onChange={(event) => setBargeInWakeWordsText(event.target.value)} />
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Sheet open={Boolean(editorProfileId)} onOpenChange={(open) => setEditorProfileId(open ? editorProfileId : null)}>
        <SheetContent side="right" className="w-full gap-0 p-0 sm:max-w-2xl">
          <div className="flex h-full flex-col">
            <SheetHeader className="border-b px-6 py-5">
              <SheetTitle>{editorProfile?.label || t('system.speech.configureModel')}</SheetTitle>
              <SheetDescription>{t('system.speech.configureModelDescription')}</SheetDescription>
            </SheetHeader>

            <ScrollArea className="min-h-0 flex-1">
              <div className="grid gap-4 px-6 py-5">
                {editorProfile ? (
                  <>
                    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
                      <div className="grid gap-2">
                        <Label>{t('system.speech.modelName')}</Label>
                        <Input
                          value={editorProfile.label}
                          onChange={(event) => updateTtsProfile(editorProfile.id, (current) => ({ ...current, label: event.target.value }))}
                          placeholder={t('system.speech.modelNamePlaceholder')}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label>{t('system.speech.provider')}</Label>
                        <Select
                          value={editorProfile.providerId || '__none__'}
                          onValueChange={(value) => handleTtsProviderChange(editorProfile.id, value === '__none__' ? '' : value)}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder={t('system.speech.chooseProvider')} />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="__none__">{t('system.common.notConfigured')}</SelectItem>
                            {providers.tts.map((provider) => (
                              <SelectItem key={provider.id} value={provider.id}>
                                {provider.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="grid gap-3 rounded-xl border p-3">
                      <div className="flex items-start gap-3">
                        <Checkbox
                          id={`tts-default-${editorProfile.id}`}
                          checked={Boolean(editorProfile.providerId) && editorProfile.id === defaultTtsProfileId}
                          disabled={!editorProfile.providerId}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setDefaultTtsProfileId(editorProfile.id)
                              return
                            }
                            if (defaultTtsProfileId === editorProfile.id) {
                              setDefaultTtsProfileId(configuredTtsProfiles.find((profile) => profile.id !== editorProfile.id)?.id || '')
                            }
                          }}
                        />
                        <div className="grid gap-1">
                          <Label htmlFor={`tts-default-${editorProfile.id}`}>{t('system.speech.setDefaultModel')}</Label>
                          <div className="text-xs text-muted-foreground">{t('system.speech.setDefaultModelHint')}</div>
                        </div>
                      </div>

                      <div className="flex items-start gap-3">
                        <Checkbox
                          id={`tts-clone-${editorProfile.id}`}
                          checked={providerSupportsVoiceClone(editorProvider) ? editorProfile.allowVoiceClone : false}
                          disabled={!providerSupportsVoiceClone(editorProvider)}
                          onCheckedChange={(checked) =>
                            updateTtsProfile(editorProfile.id, (current) => ({
                              ...current,
                              allowVoiceClone: Boolean(checked),
                            }))
                          }
                        />
                        <div className="grid gap-1">
                          <Label htmlFor={`tts-clone-${editorProfile.id}`}>{t('system.speech.allowVoiceClone')}</Label>
                          <div className="text-xs text-muted-foreground">
                            {providerSupportsVoiceClone(editorProvider)
                              ? t('system.speech.allowVoiceCloneHint')
                              : t('system.speech.voiceCloneUnsupportedHint')}
                          </div>
                        </div>
                      </div>
                    </div>

                    {editorProvider ? (
                      <div className="rounded-xl border bg-muted/30 p-3">
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <Badge variant="outline">{editorProvider.name}</Badge>
                          {providerSupportsVoiceClone(editorProvider) ? <Badge variant="secondary">{t('system.speech.voiceCloneAvailable')}</Badge> : null}
                          <span className="truncate text-sm text-muted-foreground">{editorProvider.description || t('system.common.noExtraDescription')}</span>
                        </div>
                      </div>
                    ) : null}

                    <ConfigFieldGrid
                      idPrefix={`tts-${editorProfile.id}`}
                      provider={editorProvider}
                      draft={editorProfile}
                      onChange={(key, value, options) => updateTtsField(editorProfile.id, key, value, options)}
                    />
                  </>
                ) : null}
              </div>
            </ScrollArea>

            <div className="flex flex-col gap-3 border-t px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
              <Button
                variant="outline"
                onClick={() => (editorProfile ? void removeAndSaveTtsProfile(editorProfile.id) : setEditorProfileId(null))}
                disabled={saving}
              >
                <Trash2 className="h-4 w-4" />
                {t('system.speech.deleteAndSave')}
              </Button>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <Button variant="ghost" onClick={() => setEditorProfileId(null)} disabled={saving}>
                  {t('common.close')}
                </Button>
                <Button onClick={() => void saveEditorProfile()} disabled={saving || !editorProfile?.providerId}>
                  <Save className="h-4 w-4" />
                  {saving ? t('system.common.saving') : t('system.speech.saveModel')}
                </Button>
              </div>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
