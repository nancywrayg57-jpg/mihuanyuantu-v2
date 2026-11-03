/**
 * 语言包注册表：核心包先注册，分支/模块包通过 registerLocaleMessages 追加。
 * 查找顺序：当前语言 → zh-CN（基准）→ 键本身。
 */
import { enUS } from './locales/en-US'
import { esES } from './locales/es-ES'
import { zhCN } from './locales/zh-CN'

export const SUPPORTED_LOCALES = ['zh-CN', 'en-US', 'es-ES'] as const
export type Locale = (typeof SUPPORTED_LOCALES)[number]
export const DEFAULT_LOCALE: Locale = 'zh-CN'

/** 已知核心键的联合类型 + 开放的分支扩展键（保留核心键的补全提示） */
export type MessageKey = keyof typeof zhCN | (string & {})

export const LOCALE_LABELS: Record<Locale, MessageKey> = {
  'zh-CN': 'topbar.localeZhCN',
  'en-US': 'topbar.localeEnUS',
  'es-ES': 'topbar.localeEsES',
}

const MESSAGES: Record<Locale, Record<string, string>> = {
  'zh-CN': { ...zhCN },
  'en-US': { ...enUS },
  'es-ES': { ...esES },
}

/** 分支/模块语言包注册入口（重复键后注册者覆盖，便于分支覆写核心文案） */
export function registerLocaleMessages(locale: Locale, messages: Record<string, string>) {
  Object.assign(MESSAGES[locale], messages)
}

export function translate(locale: Locale, key: MessageKey): string {
  const k = key as string
  return MESSAGES[locale]?.[k] ?? MESSAGES['zh-CN'][k] ?? k
}

/**
 * 后端菜单标题翻译：DB 存中文标题，语言包用 `menu.<中文原文>` 登记译文。
 * 未登记的标题原样返回（永不出现裸键）。
 */
export function translateMenuTitle(title: string, locale: Locale): string {
  if (!title || locale === 'zh-CN') return title
  const hit = MESSAGES[locale]?.[`menu.${title}`]
  return hit || title
}

// 模块级当前语言（服务端渲染时为 DEFAULT_LOCALE；客户端由 LocaleProvider 同步）
let activeLocale: Locale = DEFAULT_LOCALE
export function getActiveLocale(): Locale {
  return activeLocale
}
export function setActiveLocale(locale: Locale) {
  activeLocale = locale
}
export function translateActive(key: MessageKey): string {
  return translate(activeLocale, key)
}
