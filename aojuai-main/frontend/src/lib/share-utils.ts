import { toast } from 'sonner'

import { translateActive } from '@/lib/i18n/registry'

type CopyTextOptions = {
  successMessage?: string
  errorMessage?: string
}

export function resolveAbsoluteUrl(pathOrUrl: string) {
  const raw = String(pathOrUrl || '').trim()
  if (!raw) return ''
  if (/^https?:\/\//i.test(raw)) return raw
  const path = raw.startsWith('/') ? raw : `/${raw}`
  if (typeof window === 'undefined') return path
  return `${window.location.origin}${path}`
}

export function buildTokenSharePath(routePrefix: string, token?: string | null) {
  const normalizedPrefix = String(routePrefix || '').trim()
  const normalizedToken = String(token || '').trim()
  if (!normalizedPrefix || !normalizedToken) return ''
  const prefix = normalizedPrefix.startsWith('/') ? normalizedPrefix : `/${normalizedPrefix}`
  return `${prefix.replace(/\/+$/u, '')}/${encodeURIComponent(normalizedToken)}`
}

export function buildTokenShareUrl(routePrefix: string, token?: string | null) {
  return resolveAbsoluteUrl(buildTokenSharePath(routePrefix, token))
}

export async function copyTextToClipboard(text: string, options: CopyTextOptions = {}) {
  const value = String(text || '').trim()
  if (!value) return false

  const successMessage = options.successMessage || translateActive('system.common.copiedToClipboard')
  const errorMessage = options.errorMessage || translateActive('system.common.copyFailed')

  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
      toast.success(successMessage)
      return true
    }
  } catch {
    // fall through to legacy copy fallback
  }

  try {
    const textarea = document.createElement('textarea')
    textarea.value = value
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    textarea.style.top = '-9999px'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    toast.success(successMessage)
    return true
  } catch {
    toast.error(errorMessage)
    return false
  }
}
