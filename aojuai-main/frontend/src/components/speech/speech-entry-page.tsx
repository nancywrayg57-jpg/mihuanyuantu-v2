'use client'

import Link from 'next/link'
import { useEffect, useMemo, useRef, useState, type ChangeEvent, type MutableRefObject, type ReactNode } from 'react'
import { AudioLines, ExternalLink, Mic, Play, RefreshCcw, Square, Upload, Volume2, Waves } from 'lucide-react'
import { toast } from 'sonner'

import { PageHeader } from '@/components/page/page-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { ApiError } from '@/lib/api'
import {
  demoSpeechStt,
  demoSpeechTts,
  getSpeechConfig,
  listSpeechProviders,
  type SpeechProviderDescriptor,
  type SpeechTenantConfigView,
} from '@/lib/api/speech'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'
import { useT } from '@/lib/i18n'

export type PanelKey = 'tts' | 'stt' | 'barge-in'
type BargeInMode = 'vad_onset' | 'asr_text' | 'stop_words' | 'client_abort'

export type SpeechEntryPageProps = {
  initialPanel?: PanelKey
  embedded?: boolean
}

type BrowserSpeechRecognitionAlternative = {
  transcript: string
}

type BrowserSpeechRecognitionResult = {
  isFinal: boolean
  length: number
  [index: number]: BrowserSpeechRecognitionAlternative
}

type BrowserSpeechRecognitionResultList = {
  length: number
  [index: number]: BrowserSpeechRecognitionResult
}

type BrowserSpeechRecognitionEvent = Event & {
  resultIndex: number
  results: BrowserSpeechRecognitionResultList
}

type BrowserSpeechRecognitionErrorEvent = Event & {
  error: string
}

type BrowserSpeechRecognition = EventTarget & {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((event: BrowserSpeechRecognitionEvent) => void) | null
  onerror: ((event: BrowserSpeechRecognitionErrorEvent) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort?: () => void
}

type BrowserSpeechRecognitionCtor = new () => BrowserSpeechRecognition

function resolvePanel(value: string | null): PanelKey {
  return value === 'stt' || value === 'barge-in' ? value : 'tts'
}

function resolvePanelFromPath(pathname: string): PanelKey {
  const normalized = pathname.trim().toLowerCase()
  if (
    normalized.includes('/barge-in') ||
    normalized.includes('/barge_in') ||
    normalized.includes('/bargein') ||
    normalized.includes('/demo')
  ) {
    return 'barge-in'
  }
  if (normalized.includes('/stt')) {
    return 'stt'
  }
  return 'tts'
}

function splitWordList(value: string) {
  return value
    .split(/\r?\n|,|，/u)
    .map((item) => item.trim())
    .filter(Boolean)
}

function getSpeechRecognitionCtor(): BrowserSpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null
  const ctor = (window as Window & {
    SpeechRecognition?: BrowserSpeechRecognitionCtor
    webkitSpeechRecognition?: BrowserSpeechRecognitionCtor
  }).SpeechRecognition ||
    (window as Window & { webkitSpeechRecognition?: BrowserSpeechRecognitionCtor }).webkitSpeechRecognition
  return ctor || null
}

function getAudioContextCtor() {
  if (typeof window === 'undefined') return null
  const ctor =
    (window as Window & {
      AudioContext?: typeof AudioContext
      webkitAudioContext?: typeof AudioContext
    }).AudioContext ||
    (window as Window & {
      AudioContext?: typeof AudioContext
      webkitAudioContext?: typeof AudioContext
    }).webkitAudioContext
  return ctor || null
}

function collectRecognitionText(results: BrowserSpeechRecognitionResultList) {
  let finalText = ''
  let interimText = ''
  for (let index = 0; index < results.length; index += 1) {
    const chunk = results[index]
    const transcript = chunk?.[0]?.transcript || ''
    if (!transcript) continue
    if (chunk.isFinal) {
      finalText += transcript
    } else {
      interimText += transcript
    }
  }
  return { finalText: finalText.trim(), interimText: interimText.trim() }
}

function StatusNote({
  tone,
  children,
}: {
  tone: 'info' | 'warn' | 'error' | 'success'
  children: ReactNode
}) {
  const toneClass =
    tone === 'error'
      ? 'border-destructive/30 bg-destructive/5 text-destructive'
      : tone === 'warn'
        ? 'border-amber-500/30 bg-amber-500/5 text-amber-700 dark:text-amber-300'
        : tone === 'success'
          ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-700 dark:text-emerald-300'
          : 'border-border bg-muted/40 text-muted-foreground'

  return <div className={`rounded-md border px-3 py-2 text-sm ${toneClass}`}>{children}</div>
}

export default function SpeechEntryPage({
  initialPanel,
  embedded = false,
}: SpeechEntryPageProps = {}) {
  const t = useT()
  const { session } = useAuth()
  const { targetTenantId, targetTenant } = useTenant()
  const effectiveTenantId = session?.isSuperuser ? targetTenantId : null

  const [activePanel, setActivePanel] = useState<PanelKey>(initialPanel || 'tts')
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [providers, setProviders] = useState<{ tts: SpeechProviderDescriptor[]; stt: SpeechProviderDescriptor[] }>({
    tts: [],
    stt: [],
  })
  const [config, setConfig] = useState<SpeechTenantConfigView | null>(null)

  const [ttsText, setTtsText] = useState(() => t('system.speech.entry.ttsSample'))
  const [ttsOutputFormat, setTtsOutputFormat] = useState('wav')
  const [ttsServerLoading, setTtsServerLoading] = useState(false)
  const [ttsServerError, setTtsServerError] = useState<string | null>(null)
  const [ttsAudioUrl, setTtsAudioUrl] = useState<string | null>(null)

  const [browserVoices, setBrowserVoices] = useState<SpeechSynthesisVoice[]>([])
  const [browserVoiceName, setBrowserVoiceName] = useState('')
  const [browserTtsLanguage, setBrowserTtsLanguage] = useState('zh-CN')
  const [browserTtsSpeaking, setBrowserTtsSpeaking] = useState(false)
  const [browserTtsError, setBrowserTtsError] = useState<string | null>(null)

  const [sttLanguage, setSttLanguage] = useState('zh-CN')
  const [sttServerLoading, setSttServerLoading] = useState(false)
  const [sttServerError, setSttServerError] = useState<string | null>(null)
  const [sttServerResult, setSttServerResult] = useState<string>('')
  const [sttUploadFileName, setSttUploadFileName] = useState<string | null>(null)
  const [recording, setRecording] = useState(false)
  const [recordingError, setRecordingError] = useState<string | null>(null)
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null)
  const [recordedBlobUrl, setRecordedBlobUrl] = useState<string | null>(null)
  const [browserRecognitionListening, setBrowserRecognitionListening] = useState(false)
  const [browserRecognitionText, setBrowserRecognitionText] = useState('')
  const [browserRecognitionInterim, setBrowserRecognitionInterim] = useState('')
  const [browserRecognitionError, setBrowserRecognitionError] = useState<string | null>(null)

  const [bargeInText, setBargeInText] = useState(
    () => t('system.speech.entry.bargeInSample'),
  )
  const [bargeInMode, setBargeInMode] = useState<BargeInMode>('vad_onset')
  const [bargeInStopWordsText, setBargeInStopWordsText] = useState(() => t('system.speech.entry.defaultConfigStopWords'))
  const [bargeInWakeWordsText, setBargeInWakeWordsText] = useState(() => t('system.speech.entry.defaultWakeWords'))
  const [bargeInLanguage, setBargeInLanguage] = useState('zh-CN')
  const [bargeInActive, setBargeInActive] = useState(false)
  const [bargeInStatus, setBargeInStatus] = useState<string | null>(null)
  const [bargeInTranscript, setBargeInTranscript] = useState('')
  const [bargeInError, setBargeInError] = useState<string | null>(null)
  const [bargeInVadLevel, setBargeInVadLevel] = useState(0)
  const [bargeInVadThreshold, setBargeInVadThreshold] = useState('0.06')

  const searchPanelRef = useRef(false)
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const recordedChunksRef = useRef<Blob[]>([])
  const browserRecognitionRef = useRef<BrowserSpeechRecognition | null>(null)
  const browserTtsUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null)
  const bargeInRecognitionRef = useRef<BrowserSpeechRecognition | null>(null)
  const bargeInMicStreamRef = useRef<MediaStream | null>(null)
  const bargeInAudioContextRef = useRef<AudioContext | null>(null)
  const bargeInAnimationRef = useRef<number | null>(null)
  const bargeInActiveRef = useRef(false)
  const ttsAudioUrlRef = useRef<string | null>(null)
  const recordedBlobUrlRef = useRef<string | null>(null)

  const providerNameMap = useMemo(() => {
    return {
      tts: new Map(providers.tts.map((provider) => [provider.id, provider.name])),
      stt: new Map(providers.stt.map((provider) => [provider.id, provider.name])),
    }
  }, [providers.stt, providers.tts])

  const currentTtsProviderId = config?.tts?.providerId || null
  const currentSttProviderId = config?.stt?.providerId || config?.asr?.providerId || null
  const currentBargeInEnabled = config?.bargeIn?.enabled ?? true

  const recognitionSupported =
    typeof window !== 'undefined' && window.isSecureContext && getSpeechRecognitionCtor() !== null
  const browserTtsSupported =
    typeof window !== 'undefined' &&
    typeof window.speechSynthesis !== 'undefined' &&
    typeof window.SpeechSynthesisUtterance !== 'undefined'
  const recordingSupported =
    typeof window !== 'undefined' &&
    typeof window.MediaRecorder !== 'undefined' &&
    typeof navigator.mediaDevices?.getUserMedia === 'function'
  const vadSupported = recordingSupported && getAudioContextCtor() !== null

  const selectedBrowserVoice = useMemo(() => {
    return browserVoices.find((voice) => voice.name === browserVoiceName) || null
  }, [browserVoiceName, browserVoices])

  const activeStopWords = useMemo(() => {
    const parsed = splitWordList(bargeInStopWordsText)
    return parsed.length > 0 ? parsed : splitWordList(t('system.speech.entry.defaultStopWords'))
  }, [bargeInStopWordsText, t])

  useEffect(() => {
    if (initialPanel) {
      searchPanelRef.current = true
      setActivePanel(initialPanel)
      return
    }
    if (searchPanelRef.current) return
    searchPanelRef.current = true
    const searchValue = new URLSearchParams(window.location.search).get('panel')
    if (searchValue) {
      setActivePanel(resolvePanel(searchValue))
      return
    }
    setActivePanel(resolvePanelFromPath(window.location.pathname))
  }, [initialPanel])

  useEffect(() => {
    if (!session) return
    if (session.isSuperuser && !effectiveTenantId) return

    let cancelled = false

    async function loadSpeech() {
      setLoading(true)
      setLoadError(null)
      try {
        const [providersData, configData] = await Promise.all([
          listSpeechProviders({ session, tenantId: effectiveTenantId }),
          getSpeechConfig({ session, tenantId: effectiveTenantId }),
        ])
        if (cancelled) return
        setProviders({
          tts: providersData.tts || [],
          stt: providersData.stt || [],
        })
        setConfig(configData)
        setBargeInMode((configData.bargeIn?.mode as BargeInMode | undefined) || 'vad_onset')
        setBargeInStopWordsText((configData.bargeIn?.stopWords || splitWordList(t('system.speech.entry.defaultConfigStopWords'))).join('\n'))
        setBargeInWakeWordsText((configData.bargeIn?.wakeWords || []).join('\n'))
      } catch (error) {
        if (cancelled) return
        setLoadError(error instanceof ApiError ? error.message : t('system.speech.entry.loadConfigFailed'))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadSpeech()
    return () => {
      cancelled = true
    }
  }, [effectiveTenantId, session, t])

  useEffect(() => {
    if (!browserTtsSupported) return
    const synth = window.speechSynthesis
    const syncVoices = () => {
      const list = synth.getVoices()
      setBrowserVoices(list)
      if (!browserVoiceName) {
        const preferred = list.find((voice) => voice.lang.toLowerCase().startsWith('zh')) || list[0]
        if (preferred) {
          setBrowserVoiceName(preferred.name)
          setBrowserTtsLanguage(preferred.lang || 'zh-CN')
        }
      }
    }

    syncVoices()
    synth.addEventListener?.('voiceschanged', syncVoices)
    return () => {
      synth.removeEventListener?.('voiceschanged', syncVoices)
    }
  }, [browserTtsSupported, browserVoiceName])

  useEffect(() => {
    ttsAudioUrlRef.current = ttsAudioUrl
  }, [ttsAudioUrl])

  useEffect(() => {
    recordedBlobUrlRef.current = recordedBlobUrl
  }, [recordedBlobUrl])

  useEffect(() => {
    return () => {
      if (ttsAudioUrlRef.current) URL.revokeObjectURL(ttsAudioUrlRef.current)
      if (recordedBlobUrlRef.current) URL.revokeObjectURL(recordedBlobUrlRef.current)
      mediaRecorderRef.current?.stop()
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
      browserRecognitionRef.current?.stop()
      window.speechSynthesis?.cancel()
      cleanupBargeInResources({
        bargeInRecognitionRef,
        bargeInMicStreamRef,
        bargeInAudioContextRef,
        bargeInAnimationRef,
      })
    }
  }, [])

  function refreshPageData() {
    if (!session) return
    if (session.isSuperuser && !effectiveTenantId) return
    setLoadError(null)
    setLoading(true)
    void Promise.all([
      listSpeechProviders({ session, tenantId: effectiveTenantId }),
      getSpeechConfig({ session, tenantId: effectiveTenantId }),
    ])
      .then(([providersData, configData]) => {
        setProviders({
          tts: providersData.tts || [],
          stt: providersData.stt || [],
        })
        setConfig(configData)
        setBargeInMode((configData.bargeIn?.mode as BargeInMode | undefined) || 'vad_onset')
        setBargeInStopWordsText((configData.bargeIn?.stopWords || splitWordList(t('system.speech.entry.defaultConfigStopWords'))).join('\n'))
        setBargeInWakeWordsText((configData.bargeIn?.wakeWords || []).join('\n'))
        toast.success(t('system.speech.entry.contextRefreshed'))
      })
      .catch((error) => {
        setLoadError(error instanceof ApiError ? error.message : t('system.speech.entry.refreshFailed'))
        toast.error(error instanceof ApiError ? error.message : t('system.speech.entry.refreshFailed'))
      })
      .finally(() => {
        setLoading(false)
      })
  }

  function revokeAudioUrl(url: string | null) {
    if (url) URL.revokeObjectURL(url)
  }

  function stopBrowserTts() {
    if (typeof window === 'undefined' || !window.speechSynthesis) return
    window.speechSynthesis.cancel()
    browserTtsUtteranceRef.current = null
    setBrowserTtsSpeaking(false)
  }

  function stopServerAudioPlayback() {
    const element = ttsAudioRef.current
    if (!element) return
    element.pause()
    element.currentTime = 0
  }

  async function handleServerTtsDemo() {
    if (!session) return
    if (!currentTtsProviderId) {
      setTtsServerError(t('system.speech.entry.noTtsProvider'))
      return
    }
    if (currentTtsProviderId === 'system_tts') {
      setTtsServerError(t('system.speech.entry.systemTtsUseBrowser'))
      return
    }

    setTtsServerLoading(true)
    setTtsServerError(null)
    stopServerAudioPlayback()

    try {
      const audioBlob = await demoSpeechTts(
        {
          text: ttsText,
          outputFormat: ttsOutputFormat,
        },
        { session, tenantId: effectiveTenantId },
      )
      const nextUrl = URL.createObjectURL(audioBlob)
      setTtsAudioUrl((previous) => {
        revokeAudioUrl(previous)
        return nextUrl
      })
      toast.success(t('system.speech.entry.ttsGenerated'))
    } catch (error) {
      const message = error instanceof ApiError ? error.message : t('system.speech.entry.ttsDemoFailed')
      setTtsServerError(message)
      toast.error(message)
    } finally {
      setTtsServerLoading(false)
    }
  }

  function handleBrowserTtsPlay() {
    if (!browserTtsSupported) {
      setBrowserTtsError(t('system.speech.entry.browserTtsUnsupportedError'))
      return
    }
    setBrowserTtsError(null)
    stopBrowserTts()

    const utterance = new SpeechSynthesisUtterance(ttsText)
    utterance.lang = browserTtsLanguage || selectedBrowserVoice?.lang || 'zh-CN'
    if (selectedBrowserVoice) utterance.voice = selectedBrowserVoice
    utterance.onstart = () => setBrowserTtsSpeaking(true)
    utterance.onend = () => {
      setBrowserTtsSpeaking(false)
      browserTtsUtteranceRef.current = null
    }
    utterance.onerror = () => {
      setBrowserTtsSpeaking(false)
      setBrowserTtsError(t('system.speech.entry.browserTtsPlaybackFailed'))
      browserTtsUtteranceRef.current = null
    }
    browserTtsUtteranceRef.current = utterance
    window.speechSynthesis.speak(utterance)
  }

  async function handleServerSttDemo(file: File) {
    if (!session) return
    if (!currentSttProviderId) {
      setSttServerError(t('system.speech.entry.noSttProvider'))
      return
    }
    if (currentSttProviderId === 'system_stt') {
      setSttServerError(t('system.speech.entry.systemSttUseBrowser'))
      return
    }

    setSttServerLoading(true)
    setSttServerError(null)
    setSttUploadFileName(file.name)

    try {
      const payload = await demoSpeechStt(
        {
          file,
          language: sttLanguage,
        },
        { session, tenantId: effectiveTenantId },
      )
      setSttServerResult(payload.text || '')
      toast.success(t('system.speech.entry.sttCompleted').replace('{provider}', payload.providerId))
    } catch (error) {
      const message = error instanceof ApiError ? error.message : t('system.speech.entry.sttDemoFailed')
      setSttServerError(message)
      toast.error(message)
    } finally {
      setSttServerLoading(false)
    }
  }

  async function handleUploadSelection(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    await handleServerSttDemo(file)
    event.target.value = ''
  }

  async function startRecording() {
    if (!recordingSupported) {
      setRecordingError(t('system.speech.entry.recordingUnsupported'))
      return
    }

    setRecordingError(null)
    revokeAudioUrl(recordedBlobUrl)
    setRecordedBlob(null)
    setRecordedBlobUrl(null)

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      recordedChunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) recordedChunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        const nextBlob = new Blob(recordedChunksRef.current, {
          type: recorder.mimeType || 'audio/webm',
        })
        setRecordedBlob(nextBlob)
        setRecordedBlobUrl(URL.createObjectURL(nextBlob))
        stream.getTracks().forEach((track) => track.stop())
        mediaStreamRef.current = null
        mediaRecorderRef.current = null
        setRecording(false)
      }
      recorder.onerror = () => {
        setRecordingError(t('system.speech.entry.recordingFailed'))
        stream.getTracks().forEach((track) => track.stop())
        mediaStreamRef.current = null
        mediaRecorderRef.current = null
        setRecording(false)
      }

      mediaStreamRef.current = stream
      mediaRecorderRef.current = recorder
      recorder.start()
      setRecording(true)
    } catch (error) {
      setRecordingError(error instanceof Error ? error.message : t('system.speech.entry.startRecordingFailed'))
    }
  }

  function stopRecording() {
    const recorder = mediaRecorderRef.current
    if (!recorder || recorder.state === 'inactive') return
    recorder.stop()
  }

  async function sendRecordedAudioToServer() {
    if (!recordedBlob) {
      setSttServerError(t('system.speech.entry.recordBeforeSubmit'))
      return
    }
    const suffix = recordedBlob.type.includes('ogg')
      ? 'ogg'
      : recordedBlob.type.includes('mp4')
        ? 'mp4'
        : recordedBlob.type.includes('wav')
          ? 'wav'
          : 'webm'
    const file = new File([recordedBlob], `speech-recording.${suffix}`, {
      type: recordedBlob.type || 'audio/webm',
    })
    await handleServerSttDemo(file)
  }

  function stopBrowserRecognition() {
    const recognition = browserRecognitionRef.current
    browserRecognitionRef.current = null
    recognition?.stop()
    setBrowserRecognitionListening(false)
  }

  function startBrowserRecognition() {
    if (!recognitionSupported) {
      setBrowserRecognitionError(t('system.speech.entry.browserRecognitionSecureRequired'))
      return
    }

    const RecognitionCtor = getSpeechRecognitionCtor()
    if (!RecognitionCtor) {
      setBrowserRecognitionError(t('system.speech.entry.systemRecognitionUnsupported'))
      return
    }

    setBrowserRecognitionError(null)
    setBrowserRecognitionText('')
    setBrowserRecognitionInterim('')

    const recognition = new RecognitionCtor()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = sttLanguage || 'zh-CN'
    recognition.onresult = (event) => {
      const { finalText, interimText } = collectRecognitionText(event.results)
      setBrowserRecognitionText(finalText)
      setBrowserRecognitionInterim(interimText)
    }
    recognition.onerror = (event) => {
      setBrowserRecognitionError(t('system.speech.entry.browserRecognitionFailed').replace('{error}', event.error))
      setBrowserRecognitionListening(false)
      browserRecognitionRef.current = null
    }
    recognition.onend = () => {
      setBrowserRecognitionListening(false)
      browserRecognitionRef.current = null
    }

    try {
      browserRecognitionRef.current = recognition
      recognition.start()
      setBrowserRecognitionListening(true)
    } catch (error) {
      setBrowserRecognitionError(error instanceof Error ? error.message : t('system.speech.entry.browserRecognitionStartFailed'))
      browserRecognitionRef.current = null
    }
  }

  function finishBargeIn(message: string) {
    bargeInActiveRef.current = false
    setBargeInActive(false)
    setBargeInStatus(message)
    cleanupBargeInResources({
      bargeInRecognitionRef,
      bargeInMicStreamRef,
      bargeInAudioContextRef,
      bargeInAnimationRef,
    })
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel()
    }
  }

  async function startBargeInRecognition(mode: BargeInMode) {
    const RecognitionCtor = getSpeechRecognitionCtor()
    if (!RecognitionCtor) {
      throw new Error(t('system.speech.entry.bargeInRecognitionUnsupported'))
    }

    const recognition = new RecognitionCtor()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = bargeInLanguage || 'zh-CN'
    recognition.onresult = (event) => {
      const { finalText, interimText } = collectRecognitionText(event.results)
      const merged = [finalText, interimText].filter(Boolean).join(' ')
      setBargeInTranscript(merged)
      const normalized = merged.trim().toLowerCase()
      if (!normalized || !bargeInActiveRef.current) return

      if (mode === 'asr_text') {
        finishBargeIn(t('system.speech.entry.bargeInAsrDetected').replace('{text}', merged))
        return
      }

      const matchedWord = activeStopWords.find((word) => normalized.includes(word.toLowerCase()))
      if (matchedWord) {
        finishBargeIn(t('system.speech.entry.bargeInStopWordMatched').replace('{word}', matchedWord))
      }
    }
    recognition.onerror = (event) => {
      setBargeInError(t('system.speech.entry.bargeInRecognitionFailed').replace('{error}', event.error))
    }
    recognition.onend = () => {
      if (!bargeInActiveRef.current) return
      try {
        recognition.start()
      } catch {
        // keep current playback state, only surface the last transcript
      }
    }

    bargeInRecognitionRef.current = recognition
    recognition.start()
  }

  async function startBargeInVadMonitor() {
    const AudioContextCtor = getAudioContextCtor()
    if (!AudioContextCtor || !navigator.mediaDevices?.getUserMedia) {
      throw new Error(t('system.speech.entry.vadUnsupported'))
    }

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const audioContext = new AudioContextCtor()
    const source = audioContext.createMediaStreamSource(stream)
    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 2048
    source.connect(analyser)

    bargeInMicStreamRef.current = stream
    bargeInAudioContextRef.current = audioContext

    const buffer = new Uint8Array(analyser.fftSize)
    const threshold = Number.parseFloat(bargeInVadThreshold)
    const normalizedThreshold = Number.isFinite(threshold) ? threshold : 0.06
    let consecutiveHits = 0

    const loop = () => {
      analyser.getByteTimeDomainData(buffer)
      let sum = 0
      for (let index = 0; index < buffer.length; index += 1) {
        const sample = (buffer[index] - 128) / 128
        sum += sample * sample
      }
      const rms = Math.sqrt(sum / buffer.length)
      setBargeInVadLevel(rms)

      if (rms >= normalizedThreshold) {
        consecutiveHits += 1
      } else {
        consecutiveHits = 0
      }

      if (consecutiveHits >= 4 && bargeInActiveRef.current) {
        setBargeInTranscript(`VAD level=${rms.toFixed(3)}`)
        finishBargeIn(t('system.speech.entry.vadTriggered').replace('{level}', rms.toFixed(3)))
        return
      }

      if (bargeInActiveRef.current) {
        bargeInAnimationRef.current = window.requestAnimationFrame(loop)
      }
    }

    bargeInAnimationRef.current = window.requestAnimationFrame(loop)
  }

  async function startBargeIn() {
    if (!browserTtsSupported) {
      setBargeInError(t('system.speech.entry.bargeInTtsUnsupported'))
      return
    }

    setBargeInError(null)
    setBargeInStatus(t('system.speech.entry.bargeInPreparing'))
    setBargeInTranscript('')
    setBargeInVadLevel(0)

    try {
      if (bargeInMode === 'asr_text' || bargeInMode === 'stop_words') {
        await startBargeInRecognition(bargeInMode)
      } else if (bargeInMode === 'vad_onset') {
        await startBargeInVadMonitor()
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : t('system.speech.entry.bargeInStartFailed')
      setBargeInError(message)
      cleanupBargeInResources({
        bargeInRecognitionRef,
        bargeInMicStreamRef,
        bargeInAudioContextRef,
        bargeInAnimationRef,
      })
      return
    }

    const utterance = new SpeechSynthesisUtterance(bargeInText)
    utterance.lang = bargeInLanguage || selectedBrowserVoice?.lang || 'zh-CN'
    if (selectedBrowserVoice) utterance.voice = selectedBrowserVoice
    utterance.onstart = () => {
      bargeInActiveRef.current = true
      setBargeInActive(true)
      setBargeInStatus(
        bargeInMode === 'client_abort'
          ? t('system.speech.entry.bargeInClientAbortPlaying')
          : t('system.speech.entry.bargeInWaiting'),
      )
    }
    utterance.onend = () => {
      if (!bargeInActiveRef.current) return
      bargeInActiveRef.current = false
      setBargeInActive(false)
      setBargeInStatus(t('system.speech.entry.bargeInNaturalEnd'))
      cleanupBargeInResources({
        bargeInRecognitionRef,
        bargeInMicStreamRef,
        bargeInAudioContextRef,
        bargeInAnimationRef,
      })
    }
    utterance.onerror = () => {
      bargeInActiveRef.current = false
      setBargeInActive(false)
      setBargeInError(t('system.speech.entry.bargeInPlaybackFailed'))
      cleanupBargeInResources({
        bargeInRecognitionRef,
        bargeInMicStreamRef,
        bargeInAudioContextRef,
        bargeInAnimationRef,
      })
    }

    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(utterance)
  }

  if (!session) return null

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <PageHeader
            title={embedded ? t('system.speech.entry.titleEmbedded') : t('system.speech.entry.title')}
            description={
              embedded ? (
                <>
                  <div>{t('system.speech.entry.descriptionEmbedded')}</div>
                  {session.isSuperuser && targetTenant ? (
                    <div className="mt-1 text-xs text-muted-foreground">
                      {t('system.speech.entry.targetTenant')
                        .replace('{name}', targetTenant.name)
                        .replace('{code}', targetTenant.code)}
                    </div>
                  ) : null}
                </>
              ) : (
                <>
                  <div>{t('system.speech.entry.description')}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {t('system.speech.entry.configRouteHint')}
                  </div>
                  {session.isSuperuser && targetTenant ? (
                    <div className="mt-1 text-xs text-muted-foreground">
                      {t('system.speech.entry.targetTenant')
                        .replace('{name}', targetTenant.name)
                        .replace('{code}', targetTenant.code)}
                    </div>
                  ) : null}
                </>
              )
            }
            actions={
              <>
                <Button variant="outline" onClick={refreshPageData} disabled={loading}>
                  <RefreshCcw className="h-4 w-4" />
                  {t('system.speech.entry.refreshContext')}
                </Button>
                {embedded ? null : (
                  <Button asChild>
                    <Link href="/system/tenant-settings?tab=speech">
                      {t('system.speech.entry.openSpeechConfig')}
                      <ExternalLink className="h-4 w-4" />
                    </Link>
                  </Button>
                )}
              </>
            }
          />
        </CardHeader>
        <CardContent className="grid gap-4">
          {loadError ? <StatusNote tone="error">{loadError}</StatusNote> : null}
          <div className="grid gap-3 md:grid-cols-3">
            <Card className="border-dashed">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">{t('system.speech.entry.tenantTts')}</CardTitle>
                <CardDescription>{t('system.speech.entry.tenantTtsDescription')}</CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{currentTtsProviderId || t('system.common.notConfigured')}</Badge>
                  <span className="text-sm text-muted-foreground">
                    {currentTtsProviderId
                      ? providerNameMap.tts.get(currentTtsProviderId) || currentTtsProviderId
                      : t('system.speech.entry.chooseTtsProviderHint')}
                  </span>
                </div>
              </CardContent>
            </Card>
            <Card className="border-dashed">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">{t('system.speech.entry.tenantStt')}</CardTitle>
                <CardDescription>{t('system.speech.entry.tenantSttDescription')}</CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{currentSttProviderId || t('system.common.notConfigured')}</Badge>
                  <span className="text-sm text-muted-foreground">
                    {currentSttProviderId
                      ? providerNameMap.stt.get(currentSttProviderId) || currentSttProviderId
                      : t('system.speech.entry.chooseSttProviderHint')}
                  </span>
                </div>
              </CardContent>
            </Card>
            <Card className="border-dashed">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Barge-In</CardTitle>
                <CardDescription>{t('system.speech.entry.bargeInSnapshotDescription')}</CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={currentBargeInEnabled ? 'outline' : 'secondary'}>
                    {currentBargeInEnabled ? t('system.speech.entry.enabled') : t('system.speech.entry.disabled')}
                  </Badge>
                  <span className="text-sm text-muted-foreground">{config?.bargeIn?.mode || 'vad_onset'}</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </CardContent>
      </Card>

      <Tabs value={activePanel} onValueChange={(value) => setActivePanel(value as PanelKey)}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="tts">TTS</TabsTrigger>
          <TabsTrigger value="stt">STT</TabsTrigger>
          <TabsTrigger value="barge-in">Barge-In</TabsTrigger>
        </TabsList>

        <TabsContent value="tts" className="grid gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Volume2 className="h-5 w-5" />
                {t('system.speech.entry.serverTtsTitle')}
              </CardTitle>
              <CardDescription>{t('system.speech.entry.serverTtsDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              {currentTtsProviderId === 'system_tts' ? (
                <StatusNote tone="warn">{t('system.speech.entry.systemTtsWarning')}</StatusNote>
              ) : null}
              {ttsServerError ? <StatusNote tone="error">{ttsServerError}</StatusNote> : null}
              <div className="grid gap-2">
                <Label>{t('system.speech.entry.previewCopy')}</Label>
                <Textarea rows={5} value={ttsText} onChange={(event) => setTtsText(event.target.value)} />
              </div>
              <div className="grid gap-4 md:grid-cols-[220px_minmax(0,1fr)] md:items-end">
                <div className="grid gap-2">
                  <Label>{t('system.speech.entry.outputFormat')}</Label>
                  <Select value={ttsOutputFormat} onValueChange={setTtsOutputFormat}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="wav">wav</SelectItem>
                      <SelectItem value="mp3">mp3</SelectItem>
                      <SelectItem value="opus">opus</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button onClick={handleServerTtsDemo} title={t('system.speech.entry.generateCreditsTitle')} disabled={ttsServerLoading || !ttsText.trim()}>
                    <Play className="h-4 w-4" />
                    {ttsServerLoading ? t('system.speech.entry.generating') : t('system.speech.entry.generateAndPlay')}
                  </Button>
                  <Button variant="outline" onClick={stopServerAudioPlayback}>
                    <Square className="h-4 w-4" />
                    {t('system.speech.entry.stopAudio')}
                  </Button>
                </div>
              </div>
              {ttsAudioUrl ? (
                <audio ref={ttsAudioRef} controls className="w-full" src={ttsAudioUrl} />
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AudioLines className="h-5 w-5" />
                {t('system.speech.entry.browserTtsTitle')}
              </CardTitle>
              <CardDescription>{t('system.speech.entry.browserTtsDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              {!browserTtsSupported ? (
                <StatusNote tone="warn">{t('system.speech.entry.browserTtsUnsupportedWarning')}</StatusNote>
              ) : null}
              {browserTtsError ? <StatusNote tone="error">{browserTtsError}</StatusNote> : null}
              <div className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label>{t('system.speech.entry.browserVoice')}</Label>
                  <Select value={browserVoiceName || '__default__'} onValueChange={(value) => setBrowserVoiceName(value === '__default__' ? '' : value)}>
                    <SelectTrigger>
                      <SelectValue placeholder={t('system.speech.entry.defaultVoice')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__default__">{t('system.speech.entry.defaultBrowserVoice')}</SelectItem>
                      {browserVoices.map((voice) => (
                        <SelectItem key={`${voice.name}-${voice.lang}`} value={voice.name}>
                          {voice.name} ({voice.lang})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>{t('system.speech.language')}</Label>
                  <Input value={browserTtsLanguage} onChange={(event) => setBrowserTtsLanguage(event.target.value)} />
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={handleBrowserTtsPlay} disabled={!browserTtsSupported || !ttsText.trim()}>
                  <Volume2 className="h-4 w-4" />
                  {browserTtsSpeaking ? t('system.speech.entry.browserPlaying') : t('system.speech.entry.browserPlay')}
                </Button>
                <Button variant="outline" onClick={stopBrowserTts}>
                  <Square className="h-4 w-4" />
                  {t('system.speech.entry.stopBrowserPlay')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="stt" className="grid gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                {t('system.speech.entry.serverSttTitle')}
              </CardTitle>
              <CardDescription>{t('system.speech.entry.serverSttDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              {currentSttProviderId === 'system_stt' ? (
                <StatusNote tone="warn">{t('system.speech.entry.systemSttWarning')}</StatusNote>
              ) : null}
              {sttServerError ? <StatusNote tone="error">{sttServerError}</StatusNote> : null}
              <div className="grid gap-4 md:grid-cols-[220px_minmax(0,1fr)] md:items-end">
                <div className="grid gap-2">
                  <Label>{t('system.speech.entry.recognitionLanguage')}</Label>
                  <Input value={sttLanguage} onChange={(event) => setSttLanguage(event.target.value)} placeholder="zh-CN" />
                </div>
                <div className="flex flex-wrap gap-2">
                  <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium">
                    <Upload className="h-4 w-4" />
                    {t('system.speech.entry.uploadAudio')}
                    <input type="file" accept="audio/*" className="hidden" onChange={handleUploadSelection} />
                  </label>
                  <Button variant={recording ? 'destructive' : 'secondary'} onClick={recording ? stopRecording : startRecording}>
                    <Mic className="h-4 w-4" />
                    {recording ? t('system.speech.entry.stopRecording') : t('system.speech.entry.startRecording')}
                  </Button>
                  <Button variant="outline" onClick={sendRecordedAudioToServer} disabled={!recordedBlob || sttServerLoading}>
                    <Play className="h-4 w-4" />
                    {sttServerLoading ? t('system.speech.entry.recognizing') : t('system.speech.entry.submitRecording')}
                  </Button>
                </div>
              </div>
              {recordingError ? <StatusNote tone="error">{recordingError}</StatusNote> : null}
              {sttUploadFileName ? (
                <div className="text-sm text-muted-foreground">{t('system.speech.entry.lastSubmittedFile').replace('{name}', sttUploadFileName)}</div>
              ) : null}
              {recordedBlobUrl ? (
                <audio controls className="w-full" src={recordedBlobUrl} />
              ) : null}
              <div className="grid gap-2">
                <Label>{t('system.speech.entry.serverRecognitionResult')}</Label>
                <Textarea rows={6} readOnly value={sttServerResult} placeholder={t('system.speech.entry.serverRecognitionPlaceholder')} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mic className="h-5 w-5" />
                {t('system.speech.entry.browserSttTitle')}
              </CardTitle>
              <CardDescription>{t('system.speech.entry.browserSttDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              {!recognitionSupported ? (
                <StatusNote tone="warn">{t('system.speech.entry.browserSttWarning')}</StatusNote>
              ) : null}
              {browserRecognitionError ? <StatusNote tone="error">{browserRecognitionError}</StatusNote> : null}
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={startBrowserRecognition} disabled={!recognitionSupported || browserRecognitionListening}>
                  <Mic className="h-4 w-4" />
                  {browserRecognitionListening ? t('system.speech.entry.browserRecognizing') : t('system.speech.entry.startBrowserRecognition')}
                </Button>
                <Button variant="outline" onClick={stopBrowserRecognition} disabled={!browserRecognitionListening}>
                  <Square className="h-4 w-4" />
                  {t('system.speech.entry.stopBrowserRecognition')}
                </Button>
              </div>
              <div className="grid gap-2">
                <Label>{t('system.speech.entry.finalText')}</Label>
                <Textarea rows={5} readOnly value={browserRecognitionText} placeholder={t('system.speech.entry.finalTextPlaceholder')} />
              </div>
              <div className="grid gap-2">
                <Label>{t('system.speech.entry.interimText')}</Label>
                <Textarea rows={3} readOnly value={browserRecognitionInterim} placeholder={t('system.speech.entry.interimTextPlaceholder')} />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="barge-in" className="grid gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Waves className="h-5 w-5" />
                {t('system.speech.entry.bargeInDemoTitle')}
              </CardTitle>
              <CardDescription>{t('system.speech.entry.bargeInDemoDescription')}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              {currentBargeInEnabled ? null : <StatusNote tone="warn">{t('system.speech.entry.bargeInDisabledWarning')}</StatusNote>}
              {bargeInError ? <StatusNote tone="error">{bargeInError}</StatusNote> : null}
              {bargeInStatus ? <StatusNote tone={bargeInActive ? 'info' : 'success'}>{bargeInStatus}</StatusNote> : null}
              <div className="grid gap-2">
                <Label>{t('system.speech.entry.broadcastText')}</Label>
                <Textarea rows={5} value={bargeInText} onChange={(event) => setBargeInText(event.target.value)} />
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="grid gap-2">
                  <Label>{t('system.speech.entry.bargeInMode')}</Label>
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
                <div className="grid gap-2">
                  <Label>{t('system.speech.entry.recognitionLanguage')}</Label>
                  <Input value={bargeInLanguage} onChange={(event) => setBargeInLanguage(event.target.value)} />
                </div>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="grid gap-2">
                  <Label>{t('system.speech.entry.interruptWords')}</Label>
                  <Textarea rows={4} value={bargeInStopWordsText} onChange={(event) => setBargeInStopWordsText(event.target.value)} />
                </div>
                <div className="grid gap-2">
                  <Label>{t('system.speech.entry.wakeWordsDisplayOnly')}</Label>
                  <Textarea rows={4} value={bargeInWakeWordsText} onChange={(event) => setBargeInWakeWordsText(event.target.value)} />
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-[220px_minmax(0,1fr)] md:items-end">
                <div className="grid gap-2">
                  <Label>{t('system.speech.entry.vadThreshold')}</Label>
                  <Input value={bargeInVadThreshold} onChange={(event) => setBargeInVadThreshold(event.target.value)} />
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button onClick={startBargeIn} disabled={bargeInActive || !bargeInText.trim()}>
                    <Play className="h-4 w-4" />
                    {t('system.speech.entry.startBargeInDemo')}
                  </Button>
                  <Button variant="destructive" onClick={() => finishBargeIn(t('system.speech.entry.manualInterrupt'))} disabled={!bargeInActive}>
                    <Square className="h-4 w-4" />
                    {t('system.speech.entry.interruptNow')}
                  </Button>
                </div>
              </div>
              <Separator />
              <div className="grid gap-3 md:grid-cols-3">
                <Card className="border-dashed">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">ASR / Stop Words</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0 text-sm text-muted-foreground">
                    {recognitionSupported ? t('system.speech.entry.asrSupported') : t('system.speech.entry.asrUnsupported')}
                  </CardContent>
                </Card>
                <Card className="border-dashed">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">VAD Onset</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0 text-sm text-muted-foreground">
                    {vadSupported
                      ? t('system.speech.entry.currentVolume').replace('{level}', bargeInVadLevel.toFixed(3))
                      : t('system.speech.entry.vadMonitorUnsupported')}
                  </CardContent>
                </Card>
                <Card className="border-dashed">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">{t('system.speech.entry.latestTriggerText')}</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0 text-sm text-muted-foreground">
                    {bargeInTranscript || t('system.speech.entry.noTriggerText')}
                  </CardContent>
                </Card>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

function cleanupBargeInResources({
  bargeInRecognitionRef,
  bargeInMicStreamRef,
  bargeInAudioContextRef,
  bargeInAnimationRef,
}: {
  bargeInRecognitionRef: MutableRefObject<BrowserSpeechRecognition | null>
  bargeInMicStreamRef: MutableRefObject<MediaStream | null>
  bargeInAudioContextRef: MutableRefObject<AudioContext | null>
  bargeInAnimationRef: MutableRefObject<number | null>
}) {
  const recognition = bargeInRecognitionRef.current
  bargeInRecognitionRef.current = null
  if (recognition) {
    recognition.onend = null
    recognition.onerror = null
    try {
      recognition.stop()
    } catch {
      recognition.abort?.()
    }
  }

  if (bargeInAnimationRef.current !== null) {
    window.cancelAnimationFrame(bargeInAnimationRef.current)
    bargeInAnimationRef.current = null
  }

  if (bargeInMicStreamRef.current) {
    bargeInMicStreamRef.current.getTracks().forEach((track) => track.stop())
    bargeInMicStreamRef.current = null
  }

  if (bargeInAudioContextRef.current) {
    void bargeInAudioContextRef.current.close().catch(() => undefined)
    bargeInAudioContextRef.current = null
  }
}
