'use client'

import { useEffect, useMemo, useState } from 'react'

import { apiFetch } from '@/lib/api'
import { useT } from '@/lib/i18n'
import { PUBLIC_SITE_ENABLED } from '@/lib/public-site'
import type { SiteSeoConfig } from '@/lib/seo'

type SitePublicConfig = {
  tenantName?: string | null
  seo?: SiteSeoConfig | null
  appearance?: { primaryColor?: string | null; defaultLocale?: string | null } | null
}

type SiteBranding = {
  title: string
  footerText: string
  letters: string[]
}

let cachedConfig: SitePublicConfig | null | undefined
let pendingConfigRequest: Promise<SitePublicConfig | null> | null = null

function normalizeText(value: string | null | undefined) {
  const text = String(value || '').trim()
  return text || null
}

function buildBrandTitle(config: SitePublicConfig | null | undefined, fallbackTitle: string | undefined, defaultTitle: string) {
  return (
    normalizeText(config?.seo?.title) ||
    normalizeText(config?.tenantName) ||
    normalizeText(fallbackTitle) ||
    defaultTitle
  )
}

function buildBrandLetters(title: string, defaultTitle: string) {
  const normalized = Array.from(title.replace(/\s+/g, '')).filter((char) => char.trim())
  const letters = normalized.slice(0, 4)
  if (letters.length > 0) return letters
  return Array.from(defaultTitle).slice(0, 4)
}

function buildFooterText(config: SitePublicConfig | null | undefined, title: string, platformSuffix: string) {
  const description = normalizeText(config?.seo?.description)
  if (description) return description
  return title.includes(platformSuffix) ? title : `${title} ${platformSuffix}`
}

async function loadSitePublicConfig() {
  if (!PUBLIC_SITE_ENABLED) return null
  if (cachedConfig !== undefined) return cachedConfig
  if (!pendingConfigRequest) {
    pendingConfigRequest = apiFetch<SitePublicConfig>('/api/v1/site/public-config')
      .catch(() => null)
      .then((config) => {
        cachedConfig = config
        return config
      })
      .finally(() => {
        pendingConfigRequest = null
      })
  }
  return pendingConfigRequest
}

/** 租户外观配置（主题色等）；未加载/未配置时返回 null */
export function useSiteAppearance(): { primaryColor: string | null; defaultLocale: string | null } {
  const [config, setConfig] = useState<SitePublicConfig | null>(cachedConfig ?? null)

  useEffect(() => {
    let ignore = false
    void loadSitePublicConfig().then((nextConfig) => {
      if (!ignore) setConfig(nextConfig)
    })
    return () => {
      ignore = true
    }
  }, [])

  return useMemo(
    () => ({
      primaryColor: normalizeText(config?.appearance?.primaryColor),
      defaultLocale: normalizeText(config?.appearance?.defaultLocale),
    }),
    [config],
  )
}

export function useSiteBranding(fallbackTitle?: string): SiteBranding {
  const t = useT()
  const [config, setConfig] = useState<SitePublicConfig | null>(cachedConfig ?? null)

  useEffect(() => {
    let ignore = false

    void loadSitePublicConfig().then((nextConfig) => {
      if (!ignore) {
        setConfig(nextConfig)
      }
    })

    return () => {
      ignore = true
    }
  }, [])

  return useMemo(() => {
    const defaultTitle = t('system.brand.defaultTitle')
    const platformSuffix = t('system.brand.platformSuffix')
    const title = buildBrandTitle(config, fallbackTitle, defaultTitle)
    return {
      title,
      footerText: buildFooterText(config, title, platformSuffix),
      letters: buildBrandLetters(title, defaultTitle),
    }
  }, [config, fallbackTitle, t])
}
