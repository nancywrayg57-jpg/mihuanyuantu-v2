'use client'

type StoredAssistantModuleSession = {
  sessionId: number
  moduleCode: string
  moduleName: string
  updatedAt: string
}

const STORAGE_PREFIX = 'aoju:assistant:module-sessions:v1'

function buildStorageKey(scopeId?: string | number | null) {
  return `${STORAGE_PREFIX}:${String(scopeId ?? 'default')}`
}

function readRegistry(scopeId?: string | number | null): Record<string, StoredAssistantModuleSession> {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.sessionStorage.getItem(buildStorageKey(scopeId))
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    return parsed as Record<string, StoredAssistantModuleSession>
  } catch {
    return {}
  }
}

function writeRegistry(scopeId: string | number | null | undefined, registry: Record<string, StoredAssistantModuleSession>) {
  if (typeof window === 'undefined') return
  try {
    const hasEntries = Object.keys(registry).length > 0
    const key = buildStorageKey(scopeId)
    if (!hasEntries) {
      window.sessionStorage.removeItem(key)
      return
    }
    window.sessionStorage.setItem(key, JSON.stringify(registry))
  } catch {
    return
  }
}

export function loadAssistantModuleSession(
  scopeId: string | number | null | undefined,
  moduleCode: string | null | undefined,
): StoredAssistantModuleSession | null {
  const normalizedModuleCode = String(moduleCode || '').trim()
  if (!normalizedModuleCode) return null
  const registry = readRegistry(scopeId)
  const stored = registry[normalizedModuleCode]
  if (!stored || typeof stored.sessionId !== 'number' || stored.sessionId <= 0) return null
  return stored
}

export function saveAssistantModuleSession(
  scopeId: string | number | null | undefined,
  payload: StoredAssistantModuleSession,
) {
  const normalizedModuleCode = String(payload.moduleCode || '').trim()
  if (!normalizedModuleCode) return
  const registry = readRegistry(scopeId)
  registry[normalizedModuleCode] = {
    sessionId: payload.sessionId,
    moduleCode: normalizedModuleCode,
    moduleName: String(payload.moduleName || '').trim(),
    updatedAt: payload.updatedAt || new Date().toISOString(),
  }
  writeRegistry(scopeId, registry)
}

export function clearAssistantModuleSession(
  scopeId: string | number | null | undefined,
  moduleCode: string | null | undefined,
) {
  const normalizedModuleCode = String(moduleCode || '').trim()
  if (!normalizedModuleCode) return
  const registry = readRegistry(scopeId)
  if (!(normalizedModuleCode in registry)) return
  delete registry[normalizedModuleCode]
  writeRegistry(scopeId, registry)
}
