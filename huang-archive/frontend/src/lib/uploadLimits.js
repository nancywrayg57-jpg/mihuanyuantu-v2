/** Per-type upload caps (must match Caddy / PocketBase / hooks). */
export const UPLOAD_LIMITS = {
  image: 30 * 1024 * 1024,
  video: 600 * 1024 * 1024,
  other: 100 * 1024 * 1024,
}

export const UPLOAD_LIMIT_LABELS = {
  image: '图片单文件不超过 30MB',
  video: '视频单文件不超过 600MB',
  other: '其他文件单文件不超过 100MB',
}

export function fileKind(file, category) {
  const name = String(file?.name || '').toLowerCase()
  const type = String(file?.type || '').toLowerCase()
  if (category === 'video' || type.startsWith('video/') || /\.(mp4|mov|webm|m4v)$/.test(name)) {
    return 'video'
  }
  // Images (incl. photo scans) → 30MB; PDF/other under scan/audio/other → 100MB
  if (
    category === 'image' ||
    type.startsWith('image/') ||
    /\.(jpe?g|png|gif|webp|heic|heif|avif|bmp|tiff?)$/.test(name)
  ) {
    return 'image'
  }
  return 'other'
}

export function validateUploadFiles(files, category) {
  const list = Array.from(files || [])
  for (const f of list) {
    const kind = fileKind(f, category)
    const max = UPLOAD_LIMITS[kind]
    if (f.size > max) {
      const mb = Math.round(max / 1024 / 1024)
      const label = kind === 'image' ? '图片' : kind === 'video' ? '视频' : '文件'
      return `${label}「${f.name}」超过 ${mb}MB 上限`
    }
  }
  return ''
}

export const FILE_ACCEPT =
  'image/*,video/*,audio/*,.pdf,.heic,.heif,.mov,.mp4,.webm,.m4a,.mp3,.wav'
