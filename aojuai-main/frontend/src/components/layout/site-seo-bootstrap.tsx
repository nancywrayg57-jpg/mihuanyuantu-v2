'use client'

import { useEffect } from 'react'

import { apiFetch } from '@/lib/api'
import { PUBLIC_SITE_ENABLED } from '@/lib/public-site'
import { applySiteSeo, type SiteSeoConfig } from '@/lib/seo'

type SitePublicConfig = {
  tenantId?: number | null
  tenantCode?: string | null
  tenantName?: string | null
  seo?: SiteSeoConfig | null
}

export function SiteSeoBootstrap() {
  useEffect(() => {
    if (!PUBLIC_SITE_ENABLED) return
    let ignore = false

    async function run() {
      try {
        const cfg = await apiFetch<SitePublicConfig>('/api/v1/site/public-config')
        if (ignore) return
        applySiteSeo(cfg?.seo || null)
      } catch {
        // ignore (best-effort)
      }
    }

    void run()
    return () => {
      ignore = true
    }
  }, [])

  return null
}
