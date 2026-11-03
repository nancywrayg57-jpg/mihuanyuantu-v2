'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, LoaderCircle, Mic2, Play, Sparkles, Square, Trash2, Upload, Volume2 } from 'lucide-react'
import { toast } from 'sonner'

import { StatusNote } from '@/components/speech/speech-settings-ui'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'
import { ApiError } from '@/lib/api'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import {
  createSpeechVoiceClone,
  deleteSpeechVoiceClone,
  fetchSpeechVoiceCloneAssetSource,
  listSpeechVoiceCloneWorkspace,
  previewSpeechVoiceClone,
  type SpeechVoiceCloneWorkspaceItem,
  type SpeechVoiceCloneWorkspacePayload,
} from '@/lib/api/speech'

type SpeechVoiceClonePanelProps = {
  refreshNonce?: number
  onUseClone?: (item: SpeechVoiceCloneWorkspaceItem) => void
  onChanged?: () => void
  compact?: boolean
}

function formatBytes(bytes: number) {
  if (bytes <= 0) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

function formatDuration(durationMs: number) {
  const totalSeconds = Math.max(Math.round(durationMs / 1000), 0)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  if (minutes <= 0) return `${seconds}s`
  return `${minutes}m ${String(seconds).padStart(2, '0')}s`
}

function formatDate(value: string | null | undefined) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function readAudioDurationMs(file: File) {
  if (typeof window === 'undefined') {
    return Promise.resolve<number | null>(null)
  }

  return new Promise<number | null>((resolve) => {
    const objectUrl = URL.createObjectURL(file)
    const audio = document.createElement('audio')
    let settled = false
    let timeoutId: number | null = null

    const finalize = (value: number | null) => {
      if (settled) return
      settled = true
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId)
      }
      audio.onloadedmetadata = null
      audio.onerror = null
      audio.src = ''
      URL.revokeObjectURL(objectUrl)
      resolve(value)
    }

    audio.preload = 'metadata'
    audio.onloadedmetadata = () => {
      const duration = Number(audio.duration)
      finalize(Number.isFinite(duration) && duration > 0 ? Math.round(duration * 1000) : null)
    }
    audio.onerror = () => finalize(null)
    timeoutId = window.setTimeout(() => finalize(null), 5000)
    audio.src = objectUrl
  })
}

export function SpeechVoiceClonePanel({ refreshNonce = 0, onUseClone, onChanged, compact = false }: SpeechVoiceClonePanelProps) {
  const t = useT()
  const { session } = useAuth()
  const { targetTenantId } = useTenant()
  const effectiveTenantId = session?.isSuperuser ? targetTenantId : null

  const [workspace, setWorkspace] = useState<SpeechVoiceCloneWorkspacePayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [playingLabel, setPlayingLabel] = useState<string | null>(null)

  const [file, setFile] = useState<File | null>(null)
  const [displayName, setDisplayName] = useState('')
  const [transcriptText, setTranscriptText] = useState('')
  const [languageType, setLanguageType] = useState('auto')
  const [previewText, setPreviewText] = useState(() => t('system.speech.clone.previewText'))
  const [recording, setRecording] = useState(false)
  const [recordingStartedAt, setRecordingStartedAt] = useState<number | null>(null)
  const [recordingDurationMs, setRecordingDurationMs] = useState(0)
  const [recordingError, setRecordingError] = useState<string | null>(null)

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const audioUrlRef = useRef<string | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const recordingChunksRef = useRef<Blob[]>([])
  const defaultPreviewText = t('system.speech.clone.previewText')
  const languageOptions = useMemo(
    () => [
      { value: 'auto', label: t('system.speech.clone.language.auto') },
      { value: 'zh', label: t('system.speech.clone.language.zh') },
      { value: 'en', label: t('system.speech.clone.language.en') },
      { value: 'ja', label: t('system.speech.clone.language.ja') },
      { value: 'ko', label: t('system.speech.clone.language.ko') },
    ],
    [t],
  )

  const stopPlayback = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.src = ''
      audioRef.current = null
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current)
      audioUrlRef.current = null
    }
    setPlayingLabel(null)
  }, [])

  const loadWorkspace = useCallback(async () => {
    if (!session) return
    if (session.isSuperuser && !effectiveTenantId) return

    setLoading(true)
    setLoadError(null)
    try {
      const nextWorkspace = await listSpeechVoiceCloneWorkspace({
        session,
        tenantId: effectiveTenantId,
      })
      setWorkspace(nextWorkspace)
    } catch (error) {
      const message = error instanceof ApiError ? error.message : t('system.speech.clone.loadFailed')
      setLoadError(message)
    } finally {
      setLoading(false)
    }
  }, [effectiveTenantId, session])

  useEffect(() => {
    void loadWorkspace()
  }, [loadWorkspace, refreshNonce])

  useEffect(() => stopPlayback, [stopPlayback])

  useEffect(() => {
    if (!recordingStartedAt) return
    const timer = window.setInterval(() => {
      setRecordingDurationMs(Date.now() - recordingStartedAt)
    }, 500)
    return () => window.clearInterval(timer)
  }, [recordingStartedAt])

  useEffect(() => {
    return () => {
      mediaRecorderRef.current?.stop()
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  async function playBlob(loader: () => Promise<Blob>, label: string, key: string) {
    setBusyKey(key)
    try {
      const blob = await loader()
      stopPlayback()
      const objectUrl = URL.createObjectURL(blob)
      const audio = new Audio(objectUrl)
      audioRef.current = audio
      audioUrlRef.current = objectUrl
      audio.onended = () => {
        if (audioRef.current === audio) {
          stopPlayback()
        }
      }
      audio.onerror = () => {
        if (audioRef.current === audio) {
          stopPlayback()
        }
      }
      setPlayingLabel(label)
      await audio.play()
    } catch (error) {
      stopPlayback()
      const message = error instanceof ApiError ? error.message : t('system.speech.clone.playFailed')
      toast.error(message)
    } finally {
      setBusyKey((current) => (current === key ? null : current))
    }
  }

  async function handleCreate() {
    if (!session) return
    if (session.isSuperuser && !effectiveTenantId) return
    if (!file) {
      toast.error(t('system.speech.clone.selectAudioFirst'))
      return
    }

    setSubmitting(true)
    try {
      const durationMs = await readAudioDurationMs(file)
      await createSpeechVoiceClone(
        {
          file,
          displayName: displayName.trim() || t('system.speech.clone.myVoice'),
          transcriptText: transcriptText.trim() || null,
          languageType: languageType === 'auto' ? null : languageType,
          sourceDurationMs: durationMs,
        },
        { session, tenantId: effectiveTenantId },
      )
      toast.success(t('system.speech.clone.added'))
      setFile(null)
      setDisplayName('')
      setTranscriptText('')
      setLanguageType('auto')
      await loadWorkspace()
      onChanged?.()
    } catch (error) {
      const message = error instanceof ApiError ? error.message : t('system.speech.clone.createFailed')
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  async function startRecording() {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setRecordingError(t('system.speech.clone.recordUnsupported'))
      return
    }
    setRecordingError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      recordingChunksRef.current = []
      mediaStreamRef.current = stream
      mediaRecorderRef.current = recorder
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) recordingChunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        const mimeType = recorder.mimeType || 'audio/webm'
        const blob = new Blob(recordingChunksRef.current, { type: mimeType })
        const extension = mimeType.includes('mp4') ? 'm4a' : mimeType.includes('wav') ? 'wav' : 'webm'
        const recordedFile = new File([blob], `voice-recording-${Date.now()}.${extension}`, { type: mimeType })
        setFile(recordedFile)
        if (!displayName.trim()) setDisplayName(t('system.speech.clone.myRecording'))
        setRecording(false)
        setRecordingStartedAt(null)
        mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
        mediaStreamRef.current = null
        mediaRecorderRef.current = null
      }
      recorder.start()
      setRecording(true)
      setRecordingStartedAt(Date.now())
      setRecordingDurationMs(0)
    } catch (error) {
      setRecordingError(error instanceof Error ? error.message : t('system.speech.clone.microphoneFailed'))
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
      mediaStreamRef.current = null
      mediaRecorderRef.current = null
    }
  }

  function stopRecording() {
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
      return
    }
    setRecording(false)
    setRecordingStartedAt(null)
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
    mediaStreamRef.current = null
    mediaRecorderRef.current = null
  }

  async function handleDelete(item: SpeechVoiceCloneWorkspaceItem) {
    if (!session || !item.clone) return
    if (session.isSuperuser && !effectiveTenantId) return
    if (!window.confirm(t('system.speech.clone.confirmDelete').replace('{name}', item.clone.displayName || item.asset.displayName))) {
      return
    }

    const key = `delete-${item.clone.id}`
    setBusyKey(key)
    try {
      await deleteSpeechVoiceClone(item.clone.id, {
        session,
        tenantId: effectiveTenantId,
      })
      toast.success(t('system.speech.clone.deleted'))
      stopPlayback()
      await loadWorkspace()
      onChanged?.()
    } catch (error) {
      const message = error instanceof ApiError ? error.message : t('system.speech.clone.deleteFailed')
      toast.error(message)
    } finally {
      setBusyKey((current) => (current === key ? null : current))
    }
  }

  const support = workspace?.support
  const items = workspace?.items || []

  return (
    <div className={compact ? 'grid gap-3' : 'grid gap-4'}>
      <Card>
        <CardHeader className={compact ? 'space-y-1 px-4 py-3' : undefined}>
          <CardTitle className="flex items-center gap-2">
            <Mic2 className="h-5 w-5" />
            {t('system.speech.clone.title')}
          </CardTitle>
          <CardDescription>{t('system.speech.clone.description')}</CardDescription>
        </CardHeader>
        <CardContent className={compact ? 'grid gap-3 px-4 pb-4' : 'grid gap-4'}>
          {loadError ? <StatusNote tone="error">{loadError}</StatusNote> : null}
          {loading ? <StatusNote tone="info">{t('system.speech.clone.loading')}</StatusNote> : null}
          {!loading && support?.note ? (
            <StatusNote tone={support.enabled ? 'info' : 'warn'}>{support.note}</StatusNote>
          ) : null}

          <div className="flex flex-wrap gap-2">
            {support ? <Badge variant="outline">{t('system.speech.clone.maxSize').replace('{n}', String(Math.round(support.maxUploadBytes / 1024 / 1024)))}</Badge> : null}
            {support ? <Badge variant="outline">{t('system.speech.clone.maxDuration').replace('{n}', String(support.maxDurationSeconds))}</Badge> : null}
          </div>
          {recordingError ? <StatusNote tone="warn">{recordingError}</StatusNote> : null}

          <div className={cn('grid gap-4 rounded-xl border p-4', compact ? 'lg:grid-cols-[minmax(0,1fr)_160px]' : 'lg:grid-cols-[minmax(0,1fr)_180px_180px]')}>
            <div className="grid gap-2">
              <Label>{t('system.speech.clone.audioFile')}</Label>
              <Input
                type="file"
                accept=".mp3,.wav,.m4a,audio/*"
                onChange={(event) => {
                  const nextFile = event.target.files?.[0] || null
                  setFile(nextFile)
                }}
              />
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" variant={recording ? 'destructive' : 'outline'} onClick={() => (recording ? stopRecording() : void startRecording())}>
                  {recording ? <Square className="h-4 w-4" /> : <Mic2 className="h-4 w-4" />}
                  {recording
                    ? t('system.speech.clone.stopRecording').replace('{duration}', formatDuration(recordingDurationMs))
                    : t('system.speech.clone.recordWithMic')}
                </Button>
                {file ? <Badge variant="secondary">{t('system.speech.clone.audioSelected')}</Badge> : null}
              </div>
              <div className="text-xs text-muted-foreground">{t('system.speech.clone.recordingHint')}</div>
            </div>

            <div className="grid gap-2">
              <Label>{t('system.speech.clone.name')}</Label>
              <Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder={t('system.speech.clone.namePlaceholder')} />
            </div>

            <div className="grid gap-2">
              <Label>{t('system.speech.clone.language')}</Label>
              <Select value={languageType} onValueChange={setLanguageType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {languageOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className={cn('grid gap-2', compact ? 'lg:col-span-2' : 'lg:col-span-2')}>
              <Label>{t('system.speech.clone.transcript')}</Label>
              <Textarea
                rows={3}
                value={transcriptText}
                onChange={(event) => setTranscriptText(event.target.value)}
                placeholder={t('system.speech.clone.transcriptPlaceholder')}
              />
            </div>

            <div className={cn('grid gap-2', compact ? 'lg:col-span-2' : 'lg:col-span-1')}>
              <Label>{t('system.speech.clone.previewCopy')}</Label>
              <Textarea rows={3} value={previewText} onChange={(event) => setPreviewText(event.target.value)} />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={() => void handleCreate()} disabled={submitting || !support?.enabled}>
              {submitting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              {submitting ? t('system.common.submitting') : t('system.speech.clone.create')}
            </Button>
            {playingLabel ? <div className="text-sm text-muted-foreground">{t('system.speech.clone.playing').replace('{name}', playingLabel)}</div> : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className={compact ? 'space-y-1 px-4 py-3' : undefined}>
          <CardTitle className="flex items-center gap-2">
            <Volume2 className="h-5 w-5" />
            {t('system.speech.clone.myVoices')}
          </CardTitle>
          <CardDescription>{t('system.speech.clone.myVoicesDescription')}</CardDescription>
        </CardHeader>
        <CardContent className={compact ? 'grid gap-2 px-4 pb-4' : 'grid gap-3'}>
          {!items.length && !loading ? <StatusNote tone="info">{t('system.speech.clone.empty')}</StatusNote> : null}

          {items.map((item) => {
            const clone = item.clone
            const ready = clone?.status === 'ready'
            const playSourceKey = `source-${item.asset.id}`
            const previewKey = clone ? `preview-${clone.id}` : null
            const deleteKey = clone ? `delete-${clone.id}` : `delete-asset-${item.asset.id}`

            return (
              <div key={item.asset.id} className={cn('rounded-xl border', compact ? 'p-3' : 'p-4')}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="grid gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-medium">{clone?.displayName || item.asset.displayName}</div>
                      {ready ? (
                        <Badge variant="secondary" className="gap-1">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          {t('system.speech.clone.ready')}
                        </Badge>
                      ) : (
                        <Badge variant="outline">{clone?.status || item.asset.status}</Badge>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <span>{item.asset.sourceFileName}</span>
                      <span>{formatDuration(item.asset.sourceDurationMs)}</span>
                      <span>{formatBytes(item.asset.sourceFileSizeBytes)}</span>
                      <span>{formatDate(clone?.createdAt || item.asset.createdAt)}</span>
                    </div>

                    {item.asset.transcriptText ? (
                      <div className="text-sm text-muted-foreground line-clamp-2">{item.asset.transcriptText}</div>
                    ) : null}
                    {clone?.errorMessage || item.asset.lastError ? (
                      <StatusNote tone="warn">{clone?.errorMessage || item.asset.lastError}</StatusNote>
                    ) : null}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      title={t('system.speech.clone.playSourceTitle')}
                      disabled={busyKey === playSourceKey}
                      onClick={() =>
                        void playBlob(
                          () =>
                            fetchSpeechVoiceCloneAssetSource(item.asset.id, {
                              session,
                              tenantId: effectiveTenantId,
                            }),
                          t('system.speech.clone.sourceLabel').replace('{name}', item.asset.displayName),
                          playSourceKey,
                        )
                      }
                    >
                      {busyKey === playSourceKey ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                      {t('system.speech.clone.playSource')}
                    </Button>

                    <Button
                      size="sm"
                      title={t('system.speech.clone.previewTitle')}
                      disabled={!clone || !ready || busyKey === previewKey}
                      onClick={() =>
                        clone
                          ? void playBlob(
                              () =>
                                previewSpeechVoiceClone(
                                  clone.id,
                                  {
                                    text: previewText.trim() || defaultPreviewText,
                                  },
                                  {
                                    session,
                                    tenantId: effectiveTenantId,
                                  },
                                ),
                              t('system.speech.clone.previewLabel').replace('{name}', clone.displayName),
                              previewKey || '',
                            )
                          : undefined
                      }
                    >
                      {busyKey === previewKey ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                      {t('system.speech.clone.generatePreview')}
                    </Button>

                    <Button size="sm" variant="secondary" disabled={!clone || !ready} onClick={() => clone && onUseClone?.(item)}>
                      {t('system.speech.clone.useForDefault')}
                    </Button>

                    <Button size="sm" variant="ghost" disabled={!clone || busyKey === deleteKey} onClick={() => void handleDelete(item)}>
                      {busyKey === deleteKey ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                      {t('common.delete')}
                    </Button>
                  </div>
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>
    </div>
  )
}
