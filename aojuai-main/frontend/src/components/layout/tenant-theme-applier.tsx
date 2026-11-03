'use client'

import { useEffect } from 'react'

import { useSiteAppearance } from '@/hooks/useSiteBranding'
import { SUPPORTED_LOCALES, useLocale, type Locale } from '@/lib/i18n'
import { applyThemePreset, resolveThemePreset } from '@/lib/theme-presets'

/**
 * 租户主题色应用器：读取 /site/public-config 的 appearance.primaryColor，
 * 把预设写入 --primary / --ring CSS 变量；监听明暗切换以应用对应档位。
 * 挂载在 Providers 中，全站生效（含登录页）。
 */
export function TenantThemeApplier() {
  const { primaryColor, defaultLocale } = useSiteAppearance()
  const { applyTenantDefault } = useLocale()

  useEffect(() => {
    if (defaultLocale && (SUPPORTED_LOCALES as readonly string[]).includes(defaultLocale)) {
      applyTenantDefault(defaultLocale as Locale)
    }
  }, [applyTenantDefault, defaultLocale])

  useEffect(() => {
    const preset = resolveThemePreset(primaryColor)
    applyThemePreset(preset)
    if (!preset) return
    const root = document.documentElement
    const observer = new MutationObserver(() => applyThemePreset(preset))
    observer.observe(root, { attributes: true, attributeFilter: ['class'] })
    return () => {
      observer.disconnect()
    }
  }, [primaryColor])

  return null
}
