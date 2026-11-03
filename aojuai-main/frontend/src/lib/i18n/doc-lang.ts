'use client'

/**
 * Document <html lang> coordination.
 *
 * The admin i18n LocaleProvider normally drives `document.documentElement.lang`
 * from the UI locale. On the public CMS site the *content* locale must win
 * instead (so the live DOM lang matches the page language). The public shell
 * sets an override here; the provider respects it. When the override is cleared
 * (leaving the public site), the provider resumes the UI locale.
 */

let override: string | null = null
const listeners = new Set<() => void>()

export function getDocLangOverride(): string | null {
  return override
}

export function setDocLangOverride(lang: string | null): void {
  override = lang
  if (typeof document !== 'undefined') {
    if (lang) document.documentElement.lang = lang
  }
  listeners.forEach((fn) => fn())
}

export function subscribeDocLang(fn: () => void): () => void {
  listeners.add(fn)
  return () => {
    listeners.delete(fn)
  }
}
