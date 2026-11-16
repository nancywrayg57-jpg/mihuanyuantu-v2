/**
 * Shared GPS submit guard for batch / single-entry (library→batch) paths (R4).
 * Skip semantics stay honest: incomplete fixed/random may submit with a soft warning.
 */

export type GpsAwarePreset = {
  code: string
  gpsMode?: string
  gpsWritable?: boolean
  gpsWillSkip?: boolean
  gpsWritableReason?: string
}

export type GpsSubmitGuard = {
  blocked: boolean
  skipHint: string
  blockReason: string
}

/** Map legacy operator-facing GPS copy to short Chinese (no English mode tokens). */
export function cleanGpsHint(raw: string | null | undefined): string {
  const text = String(raw || '').trim()
  if (!text) return ''
  if (
    text.includes('fixed 无坐标') ||
    text.includes('已按旧版') ||
    text.includes('不伪造、不失败')
  ) {
    return '固定坐标未填写，已跳过 GPS 写入'
  }
  return text
    .replace(/（不伪造）/g, '')
    .replace(/不伪造、?/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

export function gpsSubmitGuard(preset: GpsAwarePreset | null | undefined): GpsSubmitGuard {
  if (!preset) {
    return { blocked: false, skipHint: '', blockReason: '' }
  }
  const blocked = preset.gpsWritable === false
  const rawHint =
    !blocked &&
    Boolean(preset.gpsWillSkip) &&
    Boolean(preset.gpsMode) &&
    preset.gpsMode !== 'none'
      ? preset.gpsWritableReason || '本预设 GPS 配置不完整，处理时不写入坐标'
      : ''
  const skipHint = cleanGpsHint(rawHint)
  const blockReason = blocked
    ? cleanGpsHint(preset.gpsWritableReason) || '请先在预设台账补全 GPS'
    : ''
  return { blocked, skipHint, blockReason }
}
