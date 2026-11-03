import type { AssistantAction } from '@/lib/api/assistant'
import { translateActive } from '@/lib/i18n/registry'

type AnyRecord = Record<string, unknown>

export type AssistantNavigationTarget = {
  key: string
  label: string
  routePath: string
  openHint: string
}

type SearchEntriesLike = Iterable<[string, string]> | null | undefined

function isRecord(value: unknown): value is AnyRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function toStringValue(value: unknown): string {
  if (typeof value === 'string') return value.trim()
  if (value == null) return ''
  return String(value).trim()
}

function normalizeRoutePath(value: string): string {
  const route = toStringValue(value)
  if (!route) return '/'
  if (!route.startsWith('/')) return `/${route}`
  return route
}

function buildSortedSearchString(entries: SearchEntriesLike): string {
  const collected = Array.from(entries || [])
    .map(([key, value]) => [String(key), String(value)] as const)
    .filter(([key]) => key.trim().length > 0)
    .sort(([leftKey, leftValue], [rightKey, rightValue]) => {
      if (leftKey === rightKey) return leftValue.localeCompare(rightValue)
      return leftKey.localeCompare(rightKey)
    })

  if (collected.length === 0) return ''
  const search = new URLSearchParams()
  for (const [key, value] of collected) {
    search.append(key, value)
  }
  return search.toString()
}

export function buildAssistantLocationSignature(routePath: string, searchEntries?: SearchEntriesLike): string {
  const normalizedPath = normalizeRoutePath(routePath)
  const search = buildSortedSearchString(searchEntries)
  return search ? `${normalizedPath}?${search}` : normalizedPath
}

export function buildAssistantTargetLocationSignature(route: string): string {
  const normalizedRoute = toStringValue(route)
  if (!normalizedRoute) return '/'
  const resolved = new URL(normalizedRoute, 'https://aoju.ai')
  return buildAssistantLocationSignature(normalizeRoutePath(resolved.pathname), resolved.searchParams.entries())
}

function pushTarget(
  targets: AssistantNavigationTarget[],
  seenRoutes: Set<string>,
  item: {
    key: string
    label: string
    routePath: string
    openHint?: string
  },
) {
  const normalizedRoutePath = toStringValue(item.routePath)
  if (!normalizedRoutePath) return
  const dedupeKey = buildAssistantTargetLocationSignature(normalizedRoutePath)
  if (seenRoutes.has(dedupeKey)) return
  seenRoutes.add(dedupeKey)
  targets.push({
    key: item.key,
    label: toStringValue(item.label) || normalizedRoutePath,
    routePath: normalizedRoutePath,
    openHint: toStringValue(item.openHint),
  })
}

export function extractAssistantNavigationTargets(result: Record<string, unknown> | null | undefined) {
  const payload = isRecord(result) ? result : {}
  const targets: AssistantNavigationTarget[] = []
  const seenRoutes = new Set<string>()
  const moduleName = toStringValue(payload.moduleName)
  const openHint = toStringValue(payload.openHint)

  for (const key of ['entryPath', 'routePath', 'detailPath']) {
    const routePath = toStringValue(payload[key])
    if (!routePath) continue
    pushTarget(targets, seenRoutes, {
      key,
      label:
        key === 'detailPath'
          ? translateActive('common.detail')
          : moduleName
            ? translateActive('system.assistant.openModulePage').replace('{name}', moduleName)
            : translateActive('system.assistant.openPage'),
      routePath,
      openHint,
    })
  }

  const items = [
    ...(Array.isArray(payload.sampleItems) ? payload.sampleItems : []),
    ...(Array.isArray(payload.items) ? payload.items : []),
  ]
  for (const item of items.slice(0, 4)) {
    if (!isRecord(item)) continue
    pushTarget(targets, seenRoutes, {
      key: `item:${toStringValue(item.id) || toStringValue(item.path) || toStringValue(item.routePath)}`,
      label: toStringValue(item.label) || toStringValue(item.title) || toStringValue(item.name) || translateActive('system.assistant.openPage'),
      routePath: toStringValue(item.routePath) || toStringValue(item.path),
      openHint: toStringValue(item.openHint) || openHint,
    })
  }

  return targets.slice(0, 6)
}

export function extractAssistantNavigationTargetsFromAction(action: AssistantAction | null | undefined) {
  const targets: AssistantNavigationTarget[] = []
  const seenRoutes = new Set<string>()
  const routePath = toStringValue(action?.targetRoutePath)
  if (!routePath) return targets
  pushTarget(targets, seenRoutes, {
    key: `action:${toStringValue(action?.toolId) || 'target'}`,
    label: toStringValue(action?.toolLabel)
      ? translateActive('system.assistant.goToNamedTarget').replace('{name}', toStringValue(action?.toolLabel))
      : translateActive('system.assistant.goToTargetPage'),
    routePath,
    openHint: toStringValue(action?.summary),
  })
  return targets
}

export function buildAssistantNavigationHandoffPrompt(
  action: AssistantAction | null | undefined,
  target: AssistantNavigationTarget,
) {
  const actionSummary = toStringValue(action?.summary)
  const actionLabel = toStringValue(action?.toolLabel) || toStringValue(action?.toolId)
  const openHint = toStringValue(target.openHint)
  const summary = actionSummary || actionLabel || translateActive('system.assistant.continuePreviousTask')
  const openHintSuffix = openHint ? ` ${openHint}` : ''
  return translateActive('system.assistant.navigationHandoffPrompt')
    .replace('{summary}', summary)
    .replace('{openHint}', openHintSuffix)
    .trim()
}
