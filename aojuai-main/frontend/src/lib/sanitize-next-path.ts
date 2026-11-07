/**
 * Sanitize login `next` deep-link (BROWSER-E2E-FIX F1).
 * Same-origin relative paths only; reject protocol-relative and absolute URLs.
 */
export function sanitizeNextPath(raw: string | null | undefined, fallback = '/welcome'): string {
  const value = String(raw ?? '').trim()
  if (!value) return fallback
  if (!value.startsWith('/')) return fallback
  if (value.startsWith('//')) return fallback
  if (value.includes('://')) return fallback
  if (value.includes('\\')) return fallback
  // Block encoded tricks that decode to protocol-relative or scheme.
  let decoded = value
  try {
    decoded = decodeURIComponent(value)
  } catch {
    return fallback
  }
  if (!decoded.startsWith('/') || decoded.startsWith('//') || decoded.includes('://')) {
    return fallback
  }
  return value
}
