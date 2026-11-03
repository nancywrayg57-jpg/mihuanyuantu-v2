'use client'

export const ASSISTANT_OPEN_EVENT = 'aoju:assistant:open'
export const ASSISTANT_ACTION_EXECUTED_EVENT = 'aoju:assistant:action-executed'

export type AssistantOpenDetail = {
  routePath?: string
  prompt?: string
  autoSend?: boolean
  forceNewSession?: boolean
}

export type AssistantActionExecutedDetail = {
  routePath?: string
  sessionId?: number | null
  actionType: string
  collectedParams?: Record<string, unknown>
  result?: Record<string, unknown> | null
  message?: string | null
  success?: boolean
}

export function emitAssistantOpen(detail: AssistantOpenDetail) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent<AssistantOpenDetail>(ASSISTANT_OPEN_EVENT, { detail }))
}

export function emitAssistantActionExecuted(detail: AssistantActionExecutedDetail) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent<AssistantActionExecutedDetail>(ASSISTANT_ACTION_EXECUTED_EVENT, { detail }))
}
