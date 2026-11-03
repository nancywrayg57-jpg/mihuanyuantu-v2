import { type AssistantAction } from '@/lib/api/assistant'
import { translateActive } from '@/lib/i18n/registry'

const SENSITIVE_PARAM_KEYS = new Set([
  'password',
  'token',
  'access_token',
  'refresh_token',
  'secret',
  'api_key',
  'apikey',
])

const INTERNAL_PARAM_KEYS = new Set([
  'assistantaction',
  'assistant_action',
  'toolid',
  'tool_id',
  'targetroutepath',
  'target_route_path',
  'targetmodulecode',
  'target_module_code',
  'targetcontextparams',
  'target_context_params',
])

export type AssistantActionPresentation = {
  title: string
  summary: string
  skillLabel: string
  statusLabel: string
  executeLabel: string
  paramChips: string[]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function hasDisplayableValue(value: unknown) {
  if (value == null) return false
  if (typeof value === 'string') return value.trim().length > 0
  if (Array.isArray(value)) return value.length > 0
  if (isRecord(value)) return Object.keys(value).length > 0
  return true
}

function isSensitiveParamKey(key: string) {
  return SENSITIVE_PARAM_KEYS.has(key.trim().toLowerCase())
}

function isInternalParamKey(key: string) {
  return INTERNAL_PARAM_KEYS.has(key.trim().toLowerCase())
}

function summarizeCollectedParams(action: AssistantAction) {
  const collectedParams = action.collectedParams || {}
  const lines: string[] = []

  for (const [key, value] of Object.entries(collectedParams)) {
    if (!hasDisplayableValue(value)) continue
    if (isSensitiveParamKey(key)) continue
    if (isInternalParamKey(key)) continue

    if (Array.isArray(value)) {
      lines.push(`${key}: ${value.slice(0, 3).join(', ')}${value.length > 3 ? '…' : ''}`)
    } else if (isRecord(value)) {
      lines.push(
        translateActive('system.assistant.paramObjectSummary')
          .replace('{key}', key)
          .replace('{n}', String(Object.keys(value).length)),
      )
    } else if (typeof value === 'boolean') {
      lines.push(
        translateActive('system.assistant.paramBooleanSummary')
          .replace('{key}', key)
          .replace('{value}', translateActive(value ? 'system.common.yes' : 'system.common.no')),
      )
    } else {
      lines.push(`${key}: ${String(value)}`)
    }

    if (lines.length >= 4) break
  }

  return lines
}

function buildActionStatusLabel(action: AssistantAction) {
  if (action.toolId === 'page.router.navigate') return translateActive('system.assistant.statusCanNavigate')
  if (action.mode === 'confirm' && action.canExecute) return translateActive('system.assistant.statusPendingConfirm')
  if (action.mode === 'blocked') return translateActive('system.assistant.statusBlocked')
  if (action.mode === 'result') return translateActive('system.assistant.statusCompleted')
  if (action.missingFields.length > 0) {
    return translateActive('system.assistant.statusMissingFields').replace('{n}', String(action.missingFields.length))
  }
  if (action.canExecute) return translateActive('system.assistant.statusExecutable')
  return translateActive('system.assistant.statusProcessing')
}

function buildExecuteButtonLabel(action: AssistantAction) {
  if (action.confirmText?.trim()) return action.confirmText.trim()
  return action.confirmationRequired
    ? translateActive('system.assistant.confirmExecute')
    : translateActive('system.assistant.executeNow')
}

export function describeAssistantAction(action: AssistantAction): AssistantActionPresentation {
  const title =
    action.toolLabel?.trim() ||
    (action.toolId === 'page.router.navigate' ? translateActive('system.assistant.goToTargetPage') : action.toolId)
  return {
    title,
    summary: action.summary?.trim() || '',
    skillLabel: action.skillLabel?.trim() || action.skillId?.trim() || '',
    statusLabel: buildActionStatusLabel(action),
    executeLabel: buildExecuteButtonLabel(action),
    paramChips: summarizeCollectedParams(action),
  }
}
