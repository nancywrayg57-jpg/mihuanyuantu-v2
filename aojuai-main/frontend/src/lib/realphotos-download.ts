/** FR-031 library download helpers: extension from content type + collision suffixes. */

const CONTENT_TYPE_EXT: Record<string, string> = {
  'image/jpeg': '.jpg',
  'image/jpg': '.jpg',
  'image/pjpeg': '.jpg',
  'image/png': '.png',
  'image/webp': '.webp',
  'image/gif': '.gif',
}

export function extensionForContentType(contentType: string | null | undefined): string {
  const raw = String(contentType || '')
    .split(';')[0]
    .trim()
    .toLowerCase()
  if (!raw) return '.jpg'
  if (CONTENT_TYPE_EXT[raw]) return CONTENT_TYPE_EXT[raw]
  if (raw.endsWith('+xml') && raw.includes('svg')) return '.svg'
  if (raw.startsWith('image/')) {
    const subtype = raw.slice('image/'.length)
    if (subtype === 'jpeg' || subtype === 'pjpeg') return '.jpg'
    if (/^[a-z0-9.+-]+$/i.test(subtype)) return `.${subtype.split('+')[0]}`
  }
  return '.jpg'
}

export function allocateDownloadFileName(
  basename: string,
  extension: string,
  usedNames: Map<string, number>,
): string {
  const ext = extension.startsWith('.') ? extension : `.${extension}`
  const stem = String(basename || 'asset').replace(/[\\/]+/g, '_').trim() || 'asset'
  const preferred = `${stem}${ext}`
  const seen = usedNames.get(preferred) || 0
  usedNames.set(preferred, seen + 1)
  if (seen === 0) return preferred
  // 工单 A2：冲突追加 _2 / _3（首次占用无后缀）
  return `${stem}_${seen + 1}${ext}`
}
