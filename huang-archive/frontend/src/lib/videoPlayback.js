/** Video playback helpers — WeChat / mobile friendly. */

export function isWeChat() {
  if (typeof navigator === 'undefined') return false
  return /MicroMessenger/i.test(navigator.userAgent || '')
}

export function isNativeVideoName(name) {
  return /\.(mp4|m4v|webm)$/i.test(String(name || ''))
}

/** Prefer transcoded playback_file when ready; else original when native. */
export function resolvePlayUrl(pb, archive) {
  if (!archive) return { url: '', mode: 'none', note: '' }
  const status = archive.playback_status || 'none'
  const note = archive.playback_note || ''
  const files = archive.media_files || []
  const first = files[0] || ''
  const original = first ? pb.files.getURL(archive, first) : ''
  const playFile = archive.playback_file
  const playName = Array.isArray(playFile) ? playFile[0] : playFile

  if (status === 'ready' && playName) {
    return { url: pb.files.getURL(archive, playName), mode: 'ready', note, original }
  }
  if ((status === 'native' || !status || status === 'none') && first && isNativeVideoName(first)) {
    return { url: original, mode: 'native', note: note || '浏览器可直接播放原文件', original }
  }
  if (status === 'pending') {
    return { url: original && isNativeVideoName(first) ? original : '', mode: 'pending', note, original }
  }
  if (status === 'failed') {
    return { url: '', mode: 'failed', note: note || '当前环境无法播放，请下载后用系统播放器打开', original }
  }
  // Unknown format without status yet — try original, show fallback on error
  return { url: original, mode: 'try', note, original }
}
