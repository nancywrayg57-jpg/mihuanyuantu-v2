'use client'

import type { ReactNode } from 'react'
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import {
  DEFAULT_LOCALE,
  SUPPORTED_LOCALES,
  setActiveLocale,
  translate,
  translateMenuTitle,
  type Locale,
  type MessageKey,
} from './registry'
// 模块语言包：放进 locales/ 目录即自动注册，**不要再往这里加 import**。
// 索引由 `python -m scripts.export_locale_index` 生成，漂移由 GOV-17 守卫。
import './locales/index.generated'
import { getDocLangOverride, subscribeDocLang } from './doc-lang'

const STORAGE_KEY = 'aoju.locale'



type LocaleContextValue = {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: MessageKey) => string
  /** 翻译后端菜单标题（DB 中文原文 → 当前语言） */
  tMenu: (title: string) => string
  applyTenantDefault: (locale: Locale) => void
}

const LocaleContext = createContext<LocaleContextValue>({
  locale: DEFAULT_LOCALE,
  setLocale: () => undefined,
  t: (key) => translate(DEFAULT_LOCALE, key),
  tMenu: (title) => title,
  applyTenantDefault: () => undefined,
})

function normalizeLocale(value: string | null | undefined): Locale | null {
  const raw = String(value || '').trim()
  return (SUPPORTED_LOCALES as readonly string[]).includes(raw) ? (raw as Locale) : null
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  // lazy init：SSR 渲染默认语言，客户端首渲即读取本地偏好
  const [locale, setLocaleState] = useState<Locale>(() => {
    if (typeof window === 'undefined') return DEFAULT_LOCALE
    return normalizeLocale(window.localStorage.getItem(STORAGE_KEY)) ?? DEFAULT_LOCALE
  })

  useEffect(() => {
    // The public CMS site can pin the document lang to its content locale; respect it.
    document.documentElement.lang = getDocLangOverride() || locale
    setActiveLocale(locale)
  }, [locale])

  // Re-apply when the public site sets/clears its content-locale override.
  useEffect(
    () =>
      subscribeDocLang(() => {
        document.documentElement.lang = getDocLangOverride() || locale
      }),
    [locale],
  )

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next)
    try {
      window.localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // ignore
    }
  }, [])

  // 租户默认语言：仅当用户从未手动选择过语言时应用（不写入 localStorage）
  const applyTenantDefault = useCallback((next: Locale) => {
    try {
      if (window.localStorage.getItem(STORAGE_KEY)) return
    } catch {
      return
    }
    setLocaleState(next)
  }, [])

  const t = useCallback((key: MessageKey) => translate(locale, key), [locale])
  const tMenu = useCallback((title: string) => translateMenuTitle(title, locale), [locale])

  const value = useMemo(
    () => ({ locale, setLocale, t, tMenu, applyTenantDefault }),
    [applyTenantDefault, locale, setLocale, t, tMenu],
  )

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
}

export function useLocale() {
  return useContext(LocaleContext)
}

/** 取翻译函数：const t = useT(); t('nav.searchMenus') */
export function useT() {
  return useContext(LocaleContext).t
}

export {
  DEFAULT_LOCALE,
  LOCALE_LABELS,
  SUPPORTED_LOCALES,
  registerLocaleMessages,
  setActiveLocale,
  translate,
  translateMenuTitle,
  type Locale,
  type MessageKey,
} from './registry'
