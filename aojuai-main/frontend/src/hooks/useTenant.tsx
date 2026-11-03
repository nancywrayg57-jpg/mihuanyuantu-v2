'use client'

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { apiFetch } from '@/lib/api'
import { hasTenantAdminRole, type Session } from '@/lib/auth'
import {
  FALLBACK_FEATURE_CATALOG,
  isModuleEnabled as resolveIsModuleEnabled,
  normalizeFeatureSwitches,
  type FeatureCatalog,
  type FeatureSwitches,
  type VerificationConfig,
} from '@/lib/feature-switches'
import { useT } from '@/lib/i18n'
import { useAuth } from '@/hooks/useAuth'

type TenantSimpleItem = {
  id: number
  name: string
  code: string
}

type TenantResponse = {
  id: number
  name: string
  code: string
}

type TenantSettingsConfig = {
  verification?: VerificationConfig
  featureSwitches?: FeatureSwitches
  feature_switches?: FeatureSwitches
}

type TenantSettingsResponse = {
  config?: TenantSettingsConfig
}

type TenantFeatureSwitchesResponse = {
  tenantId: number
  featureSwitches?: FeatureSwitches
  feature_switches?: FeatureSwitches
}

type TenantContextValue = {
  currentTenant: TenantSimpleItem | null
  tenants: TenantSimpleItem[]
  targetTenantId: number | null
  setTargetTenantId: (id: number | null) => void
  targetTenant: TenantSimpleItem | null
  loading: boolean
  error: string | null
  featureCatalog: FeatureCatalog
  featureSwitches: FeatureSwitches | null
  featureSwitchesLoading: boolean
  featureSwitchesError: string | null
  isModuleEnabled: (moduleId: string) => boolean
}

const TenantContext = createContext<TenantContextValue | null>(null)

const STORAGE_KEY = 'aojuai.targetTenantId'

function loadStoredTargetTenantId() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = Number(raw)
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null
  } catch {
    return null
  }
}

function storeTargetTenantId(id: number | null) {
  try {
    if (id) {
      localStorage.setItem(STORAGE_KEY, String(id))
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    // ignore
  }
}

async function fetchCurrentTenant(session: Session) {
  if (session.isSuperuser) {
    return apiFetch<TenantResponse>('/api/v1/tenants/current', { session })
  }
  if (hasTenantAdminRole(session)) {
    return apiFetch<TenantResponse>('/api/v1/tenant/profile', { session })
  }
  return null
}

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const t = useT()
  const { session } = useAuth()
  const [currentTenant, setCurrentTenant] = useState<TenantSimpleItem | null>(null)
  const [tenants, setTenants] = useState<TenantSimpleItem[]>([])
  const [targetTenantId, setTargetTenantIdState] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [featureCatalog, setFeatureCatalog] = useState<FeatureCatalog>(FALLBACK_FEATURE_CATALOG)
  const [featureSwitches, setFeatureSwitches] = useState<FeatureSwitches | null>(null)
  const [featureSwitchesLoading, setFeatureSwitchesLoading] = useState(false)
  const [featureSwitchesError, setFeatureSwitchesError] = useState<string | null>(null)

  const setTargetTenantId = useCallback((id: number | null) => {
    setTargetTenantIdState(id)
    storeTargetTenantId(id)
  }, [])

  useEffect(() => {
    let ignore = false

    async function load(sessionValue: Session) {
      setLoading(true)
      setError(null)

      try {
        const current = await fetchCurrentTenant(sessionValue)
        if (ignore) return
        if (current) {
          setCurrentTenant({ id: current.id, name: current.name, code: current.code })
        } else {
          setCurrentTenant(null)
        }

        if (!sessionValue.isSuperuser) {
          setTenants([])
          setTargetTenantId(null)
          return
        }

        if (!current) {
          setTenants([])
          setTargetTenantId(null)
          setError(t('system.tenant.loadFailed'))
          return
        }

        const allTenants = await apiFetch<TenantSimpleItem[]>('/api/v1/tenants/all', {
          session: sessionValue,
        })
        if (ignore) return

        setTenants(allTenants)
        const stored = loadStoredTargetTenantId()
        const fallback = current.id
        const initial =
          stored && allTenants.some((t) => t.id === stored) ? stored : fallback
        setTargetTenantId(initial)
      } catch (err) {
        if (ignore) return
        setError(err instanceof Error ? err.message : t('system.tenant.loadFailed'))
      } finally {
        if (!ignore) setLoading(false)
      }
    }

    if (!session) {
      setCurrentTenant(null)
      setTenants([])
      setTargetTenantIdState(null)
      setError(null)
      setLoading(false)
      return () => {}
    }

    void load(session)
    return () => {
      ignore = true
    }
  }, [session, setTargetTenantId, t])

  const targetTenant = useMemo(() => {
    if (!session?.isSuperuser) {
      return currentTenant
    }
    if (!targetTenantId) return null
    return tenants.find((t) => t.id === targetTenantId) || null
  }, [currentTenant, session?.isSuperuser, targetTenantId, tenants])

  useEffect(() => {
    let ignore = false

    async function loadTenantFeatureSwitches(sessionValue: Session, tenantId: number | null) {
      setFeatureSwitchesLoading(true)
      setFeatureSwitchesError(null)

      try {
        if (!hasTenantAdminRole(sessionValue)) {
          const runtimeSwitches = await apiFetch<TenantFeatureSwitchesResponse>(
            '/api/v1/tenant/profile/feature-switches',
            { session: sessionValue },
          )
          if (ignore) return
          setFeatureCatalog(FALLBACK_FEATURE_CATALOG)
          setFeatureSwitches(
            normalizeFeatureSwitches(
              FALLBACK_FEATURE_CATALOG,
              runtimeSwitches.featureSwitches || runtimeSwitches.feature_switches,
            ),
          )
          return
        }

        const requestTenantId = sessionValue.isSuperuser ? tenantId : null
        const [settingsRes, featureCatalogRes] = await Promise.all([
          apiFetch<TenantSettingsResponse>('/api/v1/tenant/profile/settings', {
            session: sessionValue,
            tenantId: requestTenantId,
          }),
          apiFetch<FeatureCatalog>('/api/v1/tenant/profile/settings/feature-catalog', {
            session: sessionValue,
            tenantId: requestTenantId,
          }).catch(() => FALLBACK_FEATURE_CATALOG),
        ])
        if (ignore) return

        const resolvedCatalog = featureCatalogRes || FALLBACK_FEATURE_CATALOG
        const config = settingsRes?.config
        setFeatureCatalog(resolvedCatalog)
        setFeatureSwitches(
          normalizeFeatureSwitches(
            resolvedCatalog,
            config?.featureSwitches || config?.feature_switches,
            config?.verification,
          ),
        )
      } catch (err) {
        if (ignore) return
        setFeatureCatalog(FALLBACK_FEATURE_CATALOG)
        setFeatureSwitches(normalizeFeatureSwitches(FALLBACK_FEATURE_CATALOG, null))
        setFeatureSwitchesError(err instanceof Error ? err.message : t('system.tenant.featureSwitchesLoadFailed'))
      } finally {
        if (!ignore) setFeatureSwitchesLoading(false)
      }
    }

    if (!session) {
      setFeatureCatalog(FALLBACK_FEATURE_CATALOG)
      setFeatureSwitches(null)
      setFeatureSwitchesLoading(false)
      setFeatureSwitchesError(null)
      return () => {}
    }

    if (session.isSuperuser && !targetTenantId) {
      setFeatureCatalog(FALLBACK_FEATURE_CATALOG)
      setFeatureSwitches(null)
      setFeatureSwitchesLoading(false)
      setFeatureSwitchesError(null)
      return () => {
        ignore = true
      }
    }

    void loadTenantFeatureSwitches(session, targetTenantId)
    return () => {
      ignore = true
    }
  }, [session, targetTenantId, t])

  const isModuleEnabled = useCallback(
    (moduleId: string) => resolveIsModuleEnabled(featureCatalog, featureSwitches, moduleId),
    [featureCatalog, featureSwitches],
  )

  const value = useMemo<TenantContextValue>(
    () => ({
      currentTenant,
      tenants,
      targetTenantId,
      setTargetTenantId,
      targetTenant,
      loading,
      error,
      featureCatalog,
      featureSwitches,
      featureSwitchesLoading,
      featureSwitchesError,
      isModuleEnabled,
    }),
    [
      currentTenant,
      tenants,
      targetTenantId,
      setTargetTenantId,
      targetTenant,
      loading,
      error,
      featureCatalog,
      featureSwitches,
      featureSwitchesLoading,
      featureSwitchesError,
      isModuleEnabled,
    ],
  )

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>
}

export function useTenant() {
  const ctx = useContext(TenantContext)
  if (!ctx) {
    throw new Error('useTenant must be used within <TenantProvider>')
  }
  return ctx
}
