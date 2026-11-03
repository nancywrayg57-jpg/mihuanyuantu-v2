'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { Bot, RotateCcw, Send, Sparkles } from 'lucide-react'

import {
  ASSISTANT_OPEN_EVENT,
  emitAssistantActionExecuted,
  type AssistantOpenDetail,
} from '@/components/assistant/assistant-events'
import { MarkdownContent } from '@/components/markdown/markdown-content'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'
import { ApiError } from '@/lib/api'
import { useT } from '@/lib/i18n'
import {
  createAssistantSession,
  deleteAssistantSession,
  executeAssistantAction,
  getAssistantContext,
  getAssistantPresets,
  getAssistantSession,
  getAssistantSessionMessages,
  streamAssistantChat,
  type AssistantAction,
  type AssistantPreset,
  type AssistantSessionMessageResult,
} from '@/lib/api/assistant'
import {
  clearAssistantModuleSession,
  loadAssistantModuleSession,
  saveAssistantModuleSession,
} from '@/lib/assistant/session-memory'
import { describeAssistantAction } from '@/lib/assistant/action-presentation'
import {
  buildAssistantLocationSignature,
  buildAssistantNavigationHandoffPrompt,
  buildAssistantTargetLocationSignature,
  extractAssistantNavigationTargetsFromAction,
  type AssistantNavigationTarget,
} from '@/lib/assistant/navigation-targets'
import { createStreamTextBuffer } from '@/lib/assistant/stream-buffer'

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  action?: AssistantAction | null
  pending?: boolean
  streaming?: boolean
}

type PendingNavigation = {
  locationSignature: string
  prompt: string
}

const DEFAULT_PRESET_DEFS = [
  {
    id: 'summary',
    labelKey: 'system.assistant.defaultPreset.summary.label',
    promptKey: 'system.assistant.defaultPreset.summary.prompt',
  },
  {
    id: 'next-step',
    labelKey: 'system.assistant.defaultPreset.nextStep.label',
    promptKey: 'system.assistant.defaultPreset.nextStep.prompt',
  },
  {
    id: 'risk-check',
    labelKey: 'system.assistant.defaultPreset.riskCheck.label',
    promptKey: 'system.assistant.defaultPreset.riskCheck.prompt',
  },
] as const

function normalizeRoutePath(value: string | null | undefined) {
  const route = String(value || '').trim()
  if (!route) return '/'
  if (!route.startsWith('/')) return `/${route}`
  return route
}

function buildWelcomeMessage(moduleName: string, t: (key: string) => string) {
  return t('system.assistant.welcome').replace('{name}', moduleName || t('system.assistant.unifiedAssistant'))
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function shouldAutoExecuteAction(action: AssistantAction | null | undefined): action is AssistantAction {
  if (!action) return false
  if (action.toolId === 'page.router.navigate') return false
  if (!action.canExecute) return false
  if (action.autoExecute === true) return true
  if (action.confirmationRequired) return false
  return action.mode === 'ready'
}

function isRouteNavigationAction(action: AssistantAction | null | undefined): boolean {
  return Boolean(action && action.toolId === 'page.router.navigate' && action.targetRoutePath)
}

function extractRoutePathname(value: string) {
  try {
    const resolved = new URL(value, 'https://aoju.ai')
    return normalizeRoutePath(resolved.pathname)
  } catch {
    return normalizeRoutePath(value)
  }
}

const ASSISTANT_INTERNAL_PROTOCOL_BLOCK_RE = /(?:\n\s*\n|\n)\s*\{[\s\S]*?"assistantAction"[\s\S]*?\}\s*$/
const ASSISTANT_INTERNAL_PROTOCOL_CODE_BLOCK_RE = /```(?:aoju_action|json)?\s*[\r\n]+([\s\S]*?)```/gi
const ASSISTANT_INTERNAL_PROTOCOL_HINT_RE = /"(?:assistantAction|assistant_action|toolId|tool_id|targetRoutePath|targetModuleCode)"/

function sanitizeAssistantVisibleContent(content: string | null | undefined) {
  let nextContent = String(content || '')
  if (!nextContent) return ''
  nextContent = nextContent.replace(ASSISTANT_INTERNAL_PROTOCOL_CODE_BLOCK_RE, (block, inner) => {
    const source = typeof inner === 'string' ? inner : block
    return ASSISTANT_INTERNAL_PROTOCOL_HINT_RE.test(source) ? '' : block
  })
  nextContent = nextContent.replace(ASSISTANT_INTERNAL_PROTOCOL_BLOCK_RE, '')
  return nextContent.trim()
}

function extractAssistantRoleProfile(contextData: Record<string, unknown>) {
  const raw = contextData.currentRoleProfile
  if (!isRecord(raw)) return null
  const id = String(raw.id || '').trim()
  const label = String(raw.label || raw.id || '').trim()
  const actorKind = String(raw.actorKind || '').trim()
  if (!id && !label) return null
  return {
    id,
    label: label || id,
    actorKind,
  }
}

function extractAssistantSkillPacks(contextData: Record<string, unknown>) {
  const raw = contextData.skillPacks
  if (!Array.isArray(raw)) return []
  return raw
    .filter((item): item is Record<string, unknown> => isRecord(item))
    .map((item) => ({
      id: String(item.id || '').trim(),
      label: String(item.label || item.id || '').trim(),
      available: item.available !== false,
    }))
    .filter((item) => item.id || item.label)
}

function buildWelcomeChatMessage(sessionId: number, moduleName: string, t: (key: string) => string): ChatMessage {
  return {
    id: `welcome:${sessionId}`,
    role: 'assistant',
    content: buildWelcomeMessage(moduleName, t),
  }
}

function restoreChatMessages(
  items: AssistantSessionMessageResult[],
  fallbackSessionId: number,
  fallbackModuleName: string,
  t: (key: string) => string,
): ChatMessage[] {
  const restored = items
    .filter((item) => item.role === 'user' || item.role === 'assistant')
    .map((item) => ({
      id: `history:${item.id}`,
      role: item.role as 'user' | 'assistant',
      content: item.content,
      action: item.role === 'assistant' ? item.action : null,
      pending: false,
      streaming: false,
    }))

  return restored.length > 0 ? restored : [buildWelcomeChatMessage(fallbackSessionId, fallbackModuleName, t)]
}

export function AssistantDock() {
  const t = useT()
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { session } = useAuth()
  const { targetTenantId, isModuleEnabled } = useTenant()
  const assistantModuleEnabled = isModuleEnabled('assistant')

  const currentRoutePath = useMemo(() => normalizeRoutePath(pathname), [pathname])
  const sessionMemoryScope = useMemo(
    () => `${targetTenantId ?? 0}:${session?.username || 'anonymous'}`,
    [session?.username, targetTenantId],
  )
  const currentContextParams = useMemo(() => {
    const entries = Array.from(searchParams.entries())
    if (entries.length === 0) return {}
    return {
      query: Object.fromEntries(entries),
    }
  }, [searchParams])
  const currentContextKey = useMemo(() => JSON.stringify(currentContextParams), [currentContextParams])
  const currentLocationSignature = useMemo(
    () => buildAssistantLocationSignature(currentRoutePath, searchParams.entries()),
    [currentRoutePath, searchParams],
  )

  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [chatLoading, setChatLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [pendingRoutePath, setPendingRoutePath] = useState<string | null>(null)
  const [sessionRoutePath, setSessionRoutePath] = useState('')
  const [sessionContextKey, setSessionContextKey] = useState('')
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [moduleCode, setModuleCode] = useState('')
  const [moduleName, setModuleName] = useState(() => t('system.assistant.unifiedAssistant'))
  const [contextData, setContextData] = useState<Record<string, unknown>>({})
  const [presets, setPresets] = useState<AssistantPreset[]>([])
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [pendingAutoSend, setPendingAutoSend] = useState<string | null>(null)
  const [pendingNavigation, setPendingNavigation] = useState<PendingNavigation | null>(null)
  const [executingActionId, setExecutingActionId] = useState<string | null>(null)
  const streamAbortRef = useRef<AbortController | null>(null)
  const bypassStoredSessionRestoreRef = useRef(false)

  const activeRoutePath = useMemo(
    () => normalizeRoutePath(pendingRoutePath || currentRoutePath),
    [currentRoutePath, pendingRoutePath],
  )
  const roleProfile = useMemo(() => extractAssistantRoleProfile(contextData), [contextData])
  const visibleSkillPacks = useMemo(
    () => extractAssistantSkillPacks(contextData).filter((item) => item.available).slice(0, 4),
    [contextData],
  )
  const defaultPresets = useMemo<AssistantPreset[]>(
    () => DEFAULT_PRESET_DEFS.map((item) => ({
      id: item.id,
      label: t(item.labelKey),
      prompt: t(item.promptKey),
    })),
    [t],
  )
  const visiblePresets = presets.length > 0 ? presets : defaultPresets

  const stopStreaming = useCallback(() => {
    if (!streamAbortRef.current) return
    streamAbortRef.current.abort()
    streamAbortRef.current = null
  }, [])

  const resetConversation = useCallback(() => {
    stopStreaming()
    setSessionId(null)
    setSessionRoutePath('')
    setSessionContextKey('')
    setModuleCode('')
    setModuleName(t('system.assistant.unifiedAssistant'))
    setContextData({})
    setPresets([])
    setSuggestions([])
    setMessages([])
    setInput('')
    setPendingAutoSend(null)
    setPendingNavigation(null)
    setExecutingActionId(null)
    setChatLoading(false)
    setError(null)
  }, [stopStreaming, t])

  useEffect(() => () => {
    stopStreaming()
  }, [stopStreaming])

  useEffect(() => {
    if (!session) return

    const handler = (event: Event) => {
      const detail = (event as CustomEvent<AssistantOpenDetail>).detail || {}
      if (detail.forceNewSession) {
        bypassStoredSessionRestoreRef.current = true
        if (moduleCode) {
          clearAssistantModuleSession(sessionMemoryScope, moduleCode)
        }
        resetConversation()
      }
      if (detail.routePath) {
        setPendingRoutePath(normalizeRoutePath(detail.routePath))
      }
      if (detail.prompt) {
        setInput(detail.prompt)
      }
      if (detail.autoSend && detail.prompt?.trim()) {
        setPendingAutoSend(detail.prompt.trim())
      }
      setOpen(true)
    }

    window.addEventListener(ASSISTANT_OPEN_EVENT, handler as EventListener)
    return () => {
      window.removeEventListener(ASSISTANT_OPEN_EVENT, handler as EventListener)
    }
  }, [moduleCode, resetConversation, session, sessionMemoryScope])

  useEffect(() => {
    if (!sessionId || !moduleCode) return
    saveAssistantModuleSession(sessionMemoryScope, {
      sessionId,
      moduleCode,
      moduleName,
      updatedAt: new Date().toISOString(),
    })
  }, [moduleCode, moduleName, sessionId, sessionMemoryScope])

  useEffect(() => {
    if (!open || !session) return
    if (sessionId && sessionRoutePath === activeRoutePath && sessionContextKey === currentContextKey) return

    let ignore = false

    async function ensureSession() {
      setLoading(true)
      setError(null)

      try {
        const [contextRes, presetRes] = await Promise.all([
          getAssistantContext(activeRoutePath, currentContextParams, { session, tenantId: targetTenantId }),
          getAssistantPresets(activeRoutePath, currentContextParams, { session, tenantId: targetTenantId }),
        ])

        if (ignore) return

        const resolvedModuleCode = contextRes.moduleCode || presetRes.moduleCode || moduleCode || ''
        const resolvedModuleName = contextRes.moduleName || presetRes.moduleName || moduleName || t('system.assistant.unifiedAssistant')
        const sameModuleSession = Boolean(sessionId && moduleCode && moduleCode === resolvedModuleCode)

        if (sameModuleSession) {
          setSessionRoutePath(activeRoutePath)
          setSessionContextKey(currentContextKey)
          setModuleCode(resolvedModuleCode)
          setModuleName(resolvedModuleName)
          setContextData(contextRes.data || {})
          setPresets(presetRes.presets || [])
          setPendingRoutePath(null)
          return
        }

        if (sessionId && moduleCode && moduleCode !== resolvedModuleCode) {
          stopStreaming()
          setChatLoading(false)
          setMessages([])
        }

        const shouldBypassStoredRestore = bypassStoredSessionRestoreRef.current
        bypassStoredSessionRestoreRef.current = false

        if (!shouldBypassStoredRestore && resolvedModuleCode) {
          const storedSession = loadAssistantModuleSession(sessionMemoryScope, resolvedModuleCode)
          if (storedSession?.sessionId) {
            try {
              const [storedSessionRes, historyRes] = await Promise.all([
                getAssistantSession(storedSession.sessionId, { session, tenantId: targetTenantId }),
                getAssistantSessionMessages(storedSession.sessionId, { session, tenantId: targetTenantId, limit: 100 }),
              ])

              if (ignore) return

              if (storedSessionRes.moduleCode === resolvedModuleCode) {
                setSessionId(storedSessionRes.id)
                setSessionRoutePath(activeRoutePath)
                setSessionContextKey(currentContextKey)
                setModuleCode(resolvedModuleCode)
                setModuleName(resolvedModuleName)
                setContextData(contextRes.data || {})
                setPresets(presetRes.presets || [])
                setSuggestions([])
                setMessages(restoreChatMessages(historyRes, storedSessionRes.id, resolvedModuleName, t))
                setPendingRoutePath(null)
                return
              }

              clearAssistantModuleSession(sessionMemoryScope, resolvedModuleCode)
            } catch {
              clearAssistantModuleSession(sessionMemoryScope, resolvedModuleCode)
            }
          }
        }

        const sessionRes = await createAssistantSession(
          {
            routePath: activeRoutePath,
            contextParams: currentContextParams,
          },
          { session, tenantId: targetTenantId },
        )
        if (ignore) return

        const nextModuleCode = resolvedModuleCode || sessionRes.moduleCode || ''
        const nextModuleName = resolvedModuleName || sessionRes.moduleName || t('system.assistant.unifiedAssistant')
        setSessionId(sessionRes.id)
        setSessionRoutePath(activeRoutePath)
        setSessionContextKey(currentContextKey)
        setModuleCode(nextModuleCode)
        setModuleName(nextModuleName)
        setContextData(contextRes.data || {})
        setPresets(presetRes.presets || [])
        setSuggestions([])
        setMessages([buildWelcomeChatMessage(sessionRes.id, nextModuleName, t)])
        setPendingRoutePath(null)
      } catch (err) {
        if (ignore) return
        setError(err instanceof ApiError ? err.message : t('system.assistant.initFailed'))
      } finally {
        if (!ignore) {
          setLoading(false)
        }
      }
    }

    void ensureSession()
    return () => {
      ignore = true
    }
  }, [
    activeRoutePath,
    currentContextKey,
    currentContextParams,
    moduleCode,
    moduleName,
    open,
    session,
    sessionId,
    sessionContextKey,
    sessionMemoryScope,
    sessionRoutePath,
    stopStreaming,
    targetTenantId,
    t,
  ])

  const handleNavigateFromAssistant = useCallback(
    (target: AssistantNavigationTarget, action: AssistantAction | null | undefined) => {
      const targetRoutePath = extractRoutePathname(target.routePath)
      setPendingRoutePath(targetRoutePath)
      setPendingNavigation({
        locationSignature: buildAssistantTargetLocationSignature(target.routePath),
        prompt: buildAssistantNavigationHandoffPrompt(action, target),
      })
      setOpen(true)
      router.push(target.routePath)
    },
    [router],
  )

  const handleStartNewConversation = useCallback(async () => {
    if (!session) return
    const previousSessionId = sessionId
    const previousModuleCode = moduleCode
    stopStreaming()
    setError(null)
    if (previousModuleCode) {
      clearAssistantModuleSession(sessionMemoryScope, previousModuleCode)
    }
    bypassStoredSessionRestoreRef.current = true
    resetConversation()
    setOpen(true)
    if (!previousSessionId) return
    try {
      await deleteAssistantSession(previousSessionId, { session, tenantId: targetTenantId })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('system.assistant.clearContextFailed'))
    }
  }, [moduleCode, resetConversation, session, sessionId, sessionMemoryScope, stopStreaming, targetTenantId, t])

  const handleExecuteAction = useCallback(
    async (messageId: string, action: AssistantAction) => {
      if (!session || !sessionId) return
      if (!action.canExecute) return
      if (isRouteNavigationAction(action)) {
        const [target] = extractAssistantNavigationTargetsFromAction(action)
        if (target) {
          handleNavigateFromAssistant(target, action)
        }
        return
      }

      setError(null)
      setExecutingActionId(messageId)

      try {
        const result = await executeAssistantAction(
          {
            sessionId,
            actionType: action.toolId,
            params: {
              routePath: activeRoutePath,
              collectedParams: action.collectedParams,
            },
          },
          { session, tenantId: targetTenantId },
        )

        setMessages((prev) => prev.map((item) => {
          if (item.id !== messageId || !item.action) return item
          return {
            ...item,
            action: {
              ...item.action,
              mode: result.success ? 'result' : item.action.mode,
              canExecute: false,
            },
          }
        }))
        setMessages((prev) => [
          ...prev,
          {
            id: `assistant-action:${Date.now()}`,
            role: 'assistant',
            content: result.message || (result.success ? t('system.assistant.actionSuccess') : t('system.assistant.actionFailed')),
          },
        ])
        emitAssistantActionExecuted({
          routePath: activeRoutePath,
          sessionId,
          actionType: action.toolId,
          collectedParams: action.collectedParams,
          result: result.result,
          message: result.message,
          success: result.success,
        })
      } catch (err) {
        const errorMessage = err instanceof ApiError ? err.message : t('system.assistant.executeActionFailed')
        setError(errorMessage)
        setMessages((prev) => [
          ...prev,
          {
            id: `assistant-action-error:${Date.now()}`,
            role: 'assistant',
            content: errorMessage,
          },
        ])
      } finally {
        setExecutingActionId(null)
      }
    },
    [activeRoutePath, handleNavigateFromAssistant, session, sessionId, targetTenantId, t],
  )

  const sendMessage = useCallback(
    async (overrideMessage?: string) => {
      if (!session || !sessionId) return
      const userMessage = String(overrideMessage ?? input).trim()
      if (!userMessage) return

      stopStreaming()
      setError(null)
      setChatLoading(true)
      setInput('')

      const assistantMessageId = `assistant:${Date.now()}`
      setMessages((prev) => [
        ...prev,
        { id: `user:${Date.now()}`, role: 'user', content: userMessage },
        {
          id: assistantMessageId,
          role: 'assistant',
          content: '',
          action: null,
          pending: true,
          streaming: true,
        },
      ])

      try {
        const controller = new AbortController()
        streamAbortRef.current = controller

        const streamBuffer = createStreamTextBuffer({
          flushDelayMs: 120,
          onFirstChunk: () => {
            setMessages((prev) => prev.map((item) => {
              if (item.id !== assistantMessageId) return item
              return {
                ...item,
                pending: false,
                streaming: true,
              }
            }))
          },
          onText: (nextText) => {
            setMessages((prev) => prev.map((item) => {
              if (item.id !== assistantMessageId) return item
              return {
                ...item,
                content: nextText,
                pending: false,
                streaming: true,
              }
            }))
          },
        })

        let latestReply = ''
        let finalAction: AssistantAction | null = null

        const appendStreamDelta = (delta: string) => {
          const nextDelta = String(delta || '')
          if (!nextDelta) return
          latestReply += nextDelta
          streamBuffer.push(nextDelta)
        }

        const syncStreamReply = (fullText: string) => {
          const nextText = String(fullText || '')
          if (!nextText) return
          latestReply = nextText
          streamBuffer.replace(nextText)
        }

        await streamAssistantChat(
          {
            sessionId,
            message: userMessage,
            routePath: activeRoutePath,
            contextParams: currentContextParams,
          },
          (chunk) => {
            if (chunk.type === 'content') {
              appendStreamDelta(chunk.content || '')
              return
            }

            if (chunk.type === 'error') {
              const errorMessage = String(chunk.content || t('system.assistant.replyFailed'))
              setError(errorMessage)
              streamBuffer.flush()
              setMessages((prev) => prev.map((item) => {
                if (item.id !== assistantMessageId) return item
                const nextContent = item.content
                  ? `${item.content}\n\nError: ${errorMessage}`
                  : `Error: ${errorMessage}`
                return {
                  ...item,
                  content: nextContent,
                  pending: false,
                  streaming: false,
                }
              }))
              return
            }

            if (chunk.type === 'done') {
              if (chunk.moduleName) {
                setModuleName(chunk.moduleName)
              }
              if (chunk.moduleCode) {
                setModuleCode(chunk.moduleCode)
              }
              if (chunk.context && Object.keys(chunk.context).length > 0) {
                setContextData(chunk.context)
              }
              setSuggestions(chunk.suggestions || [])
              finalAction = chunk.action || null
              syncStreamReply(sanitizeAssistantVisibleContent(chunk.reply || latestReply) || t('system.assistant.emptyReply'))
              streamBuffer.finish()
              setMessages((prev) => prev.map((item) => {
                if (item.id !== assistantMessageId) return item
                return {
                  ...item,
                  action: chunk.action || null,
                  pending: false,
                  streaming: false,
                }
              }))
            }
          },
          { session, tenantId: targetTenantId, signal: controller.signal },
        )

        await streamBuffer.waitForIdle()
        streamBuffer.stop()
        streamAbortRef.current = null
        setMessages((prev) => prev.map((item) => {
          if (item.id !== assistantMessageId) return item
          return {
            ...item,
            content: sanitizeAssistantVisibleContent(latestReply || item.content) || t('system.assistant.emptyReply'),
            action: finalAction,
            pending: false,
            streaming: false,
          }
        }))

        if (shouldAutoExecuteAction(finalAction)) {
          await handleExecuteAction(assistantMessageId, finalAction)
        }
      } catch (err) {
        const aborted =
          (err instanceof DOMException && err.name === 'AbortError') ||
          (err instanceof Error && err.name === 'AbortError')
        if (!aborted) {
          const errorMessage = err instanceof ApiError ? err.message : t('system.assistant.replyFailed')
          setError(errorMessage)
          setMessages((prev) => prev.map((item) => {
            if (item.id !== assistantMessageId) return item
            return {
              ...item,
              content: item.content ? `${item.content}\n\nError: ${errorMessage}` : `Error: ${errorMessage}`,
              pending: false,
              streaming: false,
            }
          }))
        }
      } finally {
        streamAbortRef.current = null
        setChatLoading(false)
      }
    },
    [activeRoutePath, currentContextParams, handleExecuteAction, input, session, sessionId, stopStreaming, targetTenantId, t],
  )

  useEffect(() => {
    if (!pendingAutoSend || !sessionId || loading || chatLoading) return
    const message = pendingAutoSend
    setPendingAutoSend(null)
    void sendMessage(message)
  }, [chatLoading, loading, pendingAutoSend, sendMessage, sessionId])

  useEffect(() => {
    if (!pendingNavigation) return
    if (currentLocationSignature !== pendingNavigation.locationSignature) return
    setOpen(true)
    setPendingAutoSend(pendingNavigation.prompt)
    setPendingNavigation(null)
  }, [currentLocationSignature, pendingNavigation])

  if (!session || !assistantModuleEnabled) return null

  return (
    <div className="fixed bottom-4 right-4 z-30">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button className="rounded-full shadow-lg">
            <Bot className="mr-1 h-4 w-4" />
            {t('system.assistant.title')}
          </Button>
        </SheetTrigger>
        <SheetContent side="right" className="w-full p-0 sm:max-w-xl">
          <div className="flex h-full flex-col">
            <SheetHeader className="border-b px-5 py-4 text-left">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <SheetTitle className="truncate">{moduleName}</SheetTitle>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 shrink-0"
                      disabled={loading || chatLoading}
                      onClick={() => void handleStartNewConversation()}
                    >
                      <RotateCcw className="mr-1 h-3.5 w-3.5" />
                      {t('system.assistant.newConversation')}
                    </Button>
                  </div>
                  <SheetDescription className="sr-only">
                    {t('system.assistant.sheetDescription')}
                  </SheetDescription>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">{t('system.assistant.unifiedEntry')}</Badge>
                    <Badge variant="outline" className="max-w-full truncate">
                      {activeRoutePath}
                    </Badge>
                  </div>
                  {roleProfile || visibleSkillPacks.length > 0 ? (
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {roleProfile ? (
                        <Badge variant="outline" className="max-w-full truncate text-xs font-normal">
                          {t('system.assistant.rolePrefix').replace('{name}', roleProfile.label)}
                        </Badge>
                      ) : null}
                      {visibleSkillPacks.map((item) => (
                        <Badge
                          key={item.id || item.label}
                          variant="secondary"
                          className="max-w-full truncate text-xs font-normal"
                        >
                          {item.label}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            </SheetHeader>

            <div className="flex min-h-0 flex-1 flex-col gap-3 px-4 py-3">
              <ScrollArea className="min-h-0 flex-1 rounded-xl border bg-muted/20 px-3 py-3">
                <div className="space-y-3 pr-2">
                  {messages.length === 0 ? (
                    <div className="text-xs text-muted-foreground">
                      {loading ? t('system.assistant.loadingContext') : t('system.assistant.startPrompt')}
                    </div>
                  ) : null}

                  {messages.map((item) => (
                    <div
                      key={item.id}
                      className={item.role === 'assistant' ? 'flex justify-start' : 'flex justify-end'}
                    >
                      <div
                        className={
                          item.role === 'assistant'
                            ? 'max-w-[92%] rounded-2xl rounded-bl-md border bg-background px-3 py-2 text-sm shadow-sm'
                            : 'max-w-[92%] rounded-2xl rounded-br-md bg-primary px-3 py-2 text-sm text-primary-foreground'
                        }
                      >
                        <div className="mb-1 text-xs text-muted-foreground">
                          {item.role === 'assistant' ? t('system.assistant.roleAssistant') : t('system.assistant.roleUser')}
                        </div>
                        {item.role === 'assistant' ? (
                          <MarkdownContent
                            content={sanitizeAssistantVisibleContent(item.content) || (item.pending ? '...' : '')}
                            className="space-y-2 leading-6 [&_p]:my-1 [&_p]:leading-6 [&_li]:leading-6 [&_ul]:my-1 [&_ol]:my-1"
                          />
                        ) : (
                          <div className="whitespace-pre-wrap break-words leading-5">{item.content}</div>
                        )}

                        {item.role === 'assistant' && item.action ? (
                          (() => {
                            const actionPresentation = describeAssistantAction(item.action)
                            const directNavigationTarget = isRouteNavigationAction(item.action)
                              ? extractAssistantNavigationTargetsFromAction(item.action)[0] || null
                              : null
                            return (
                              <div className="mt-3 rounded-xl border bg-muted/30 px-3 py-2">
                            <div className="flex items-start justify-between gap-2">
                              <div className="min-w-0">
                                <div className="truncate text-[12px] font-medium text-foreground">
                                  {actionPresentation.title}
                                </div>
                                {actionPresentation.skillLabel ? (
                                  <div className="mt-1">
                                    <Badge variant="secondary" className="max-w-full truncate text-xs font-normal">
                                      {actionPresentation.skillLabel}
                                    </Badge>
                                  </div>
                                ) : null}
                                {actionPresentation.summary ? (
                                  <div className="mt-1 text-[12px] leading-5 text-muted-foreground">
                                    {actionPresentation.summary}
                                  </div>
                                ) : null}
                              </div>
                              <Badge variant="outline" className="shrink-0 px-2 py-0 text-xs">
                                {actionPresentation.statusLabel}
                              </Badge>
                            </div>

                            {actionPresentation.paramChips.length > 0 ? (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {actionPresentation.paramChips.map((line) => (
                                  <Badge key={line} variant="secondary" className="max-w-full truncate text-xs font-normal">
                                    {line}
                                  </Badge>
                                ))}
                              </div>
                            ) : null}

                            {item.action.missingFields.length > 0 ? (
                              <div className="mt-2 text-[12px] leading-5 text-muted-foreground">
                                {t('system.assistant.missingFields').replace(
                                  '{fields}',
                                  item.action.missingFields.map((field) => field.label).join('、'),
                                )}
                              </div>
                            ) : null}

                            {item.action.nextQuestion ? (
                              <div className="mt-2 text-[12px] leading-5 text-foreground/80">
                                {t('system.assistant.nextQuestion').replace('{question}', item.action.nextQuestion)}
                              </div>
                            ) : null}

                            {item.action.suggestedReplies.length > 0 ? (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {item.action.suggestedReplies.map((suggestion) => (
                                  <Button
                                    key={`${item.id}:${suggestion}`}
                                    size="sm"
                                    variant="outline"
                                    className="h-auto min-h-7 rounded-full px-2.5 py-1 text-xs"
                                    onClick={() => setInput(suggestion)}
                                  >
                                    {suggestion}
                                  </Button>
                                ))}
                              </div>
                            ) : null}

                            {item.action.reason ? (
                              <div className="mt-2 text-[12px] leading-5 text-muted-foreground">
                                {item.action.reason}
                              </div>
                            ) : null}

                            {directNavigationTarget ? (
                              <div className="mt-3">
                                <Button
                                  size="sm"
                                  onClick={() => handleNavigateFromAssistant(directNavigationTarget, item.action)}
                                >
                                  {item.action.confirmText?.trim() || t('system.assistant.goToPage')}
                                </Button>
                              </div>
                            ) : null}

                            {item.action.canExecute && !directNavigationTarget ? (
                              <div className="mt-3">
                                <Button
                                  size="sm"
                                  disabled={executingActionId === item.id}
                                  onClick={() => void handleExecuteAction(item.id, item.action!)}
                                >
                                  {executingActionId === item.id ? t('system.common.executing') : actionPresentation.executeLabel}
                                </Button>
                              </div>
                            ) : null}
                          </div>
                            )
                          })()
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>

              {visiblePresets.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {visiblePresets.map((preset) => (
                    <Button
                      key={preset.id}
                      size="sm"
                      variant="outline"
                      className="h-auto min-h-8 rounded-full px-3 py-1 text-xs"
                      onClick={() => setInput(preset.prompt)}
                    >
                      <Sparkles className="mr-1 h-3.5 w-3.5" />
                      {preset.label}
                    </Button>
                  ))}
                </div>
              ) : null}

              {suggestions.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {suggestions.map((item) => (
                    <Button
                      key={item}
                      size="sm"
                      variant="secondary"
                      className="h-auto min-h-8 rounded-full px-3 py-1 text-xs"
                      onClick={() => setInput(item)}
                    >
                      {item}
                    </Button>
                  ))}
                </div>
              ) : null}

              <div className="grid gap-2">
                <Textarea
                  rows={4}
                  value={input}
                  disabled={loading || chatLoading || !sessionId}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder={t('system.assistant.placeholder')}
                  onKeyDown={(event) => {
                    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                      event.preventDefault()
                      void sendMessage()
                    }
                  }}
                />
                <div className="flex items-center justify-between gap-2">
                  <div className="min-h-5 text-xs text-muted-foreground">
                    {error
                      ? <span className="text-destructive">{error}</span>
                      : t('system.assistant.inputHint')}
                  </div>
                  <Button
                    disabled={!input.trim() || chatLoading || loading || !sessionId}
                    onClick={() => void sendMessage()}
                  >
                    <Send className="mr-1 h-4 w-4" />
                    {t('system.assistant.send')}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
