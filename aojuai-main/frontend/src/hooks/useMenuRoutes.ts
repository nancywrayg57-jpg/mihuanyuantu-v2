'use client'

import { useEffect, useState } from 'react'

import { apiFetch } from '@/lib/api'
import { filterMenuRoutesByFeatureSwitches } from '@/lib/feature-switches'
import { useT } from '@/lib/i18n'
import { useAuth } from '@/hooks/useAuth'
import { useTenant } from '@/hooks/useTenant'

export type MenuRouteMeta = {
  title?: string
  icon?: string | null
  showLink?: boolean
  hidden?: boolean
  requireSuperuser?: boolean
  [k: string]: unknown
}

export type MenuRoute = {
  path: string
  name: string
  component?: string | null
  redirect?: string | null
  meta?: MenuRouteMeta
  children?: MenuRoute[]
}

export function useMenuRoutes() {
  const t = useT()
  const { session } = useAuth()
  const { targetTenantId, featureCatalog, featureSwitches } = useTenant()

  const [routes, setRoutes] = useState<MenuRoute[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false

    async function load() {
      if (!session) {
        setRoutes([])
        setLoading(false)
        setError(null)
        return
      }

      setLoading(true)
      setError(null)
      try {
        const data = await apiFetch<MenuRoute[]>('/api/v1/menus/routes', {
          session,
          tenantId: targetTenantId,
        })
        if (ignore) return
        const nextRoutes = Array.isArray(data) ? data : []
        setRoutes(filterMenuRoutesByFeatureSwitches(nextRoutes, featureCatalog, featureSwitches))
      } catch (err) {
        if (ignore) return
        setRoutes([])
        setError(err instanceof Error ? err.message : t('system.menu.loadFailed'))
      } finally {
        if (!ignore) setLoading(false)
      }
    }

    void load()
    return () => {
      ignore = true
    }
  }, [featureCatalog, featureSwitches, session, targetTenantId, t])

  return { routes, loading, error }
}
