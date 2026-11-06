/** S1 上传硬校验。与后端 inspect_upload 同一组上限。 */

export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024
export const MAX_PIXELS = 40_000_000
export const RECHARGE_CREDITS_BY_YUAN: Record<number, number> = {
  100: 1000,
  300: 3150,
  500: 5500,
  1000: 11500,
  3000: 36000,
}
export const RECHARGE_TIERS_YUAN = [100, 300, 500, 1000, 3000] as const

export type LocalInspect =
  | { ok: true; width: number; height: number; bytes: number; kind: 'jpeg' | 'png' }
  | { ok: false; message: string }

/** 管理员 2026-11-06 确认：宽等于高时按横图下限（宽>=1024 且高>=768）。 */
export const SQUARE_USES_LANDSCAPE_FLOOR = true

function magic(bytes: Uint8Array): 'jpeg' | 'png' | null {
  if (bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return 'jpeg'
  if (
    bytes.length >= 8 &&
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47 &&
    bytes[4] === 0x0d &&
    bytes[5] === 0x0a &&
    bytes[6] === 0x1a &&
    bytes[7] === 0x0a
  ) {
    return 'png'
  }
  return null
}

function orientation(width: number, height: number): string | null {
  if (width > height || (width === height && SQUARE_USES_LANDSCAPE_FLOOR)) {
    if (width < 1024 || height < 768) return '横图至少 1024×768'
    return null
  }
  if (height > width) {
    if (height < 1024 || width < 768) return '竖图至少 768×1024'
    return null
  }
  return '分辨率不符合方向规则'
}

export async function inspectLocalFile(file: File): Promise<LocalInspect> {
  if (!file || file.size <= 0) return { ok: false, message: '空文件' }
  if (file.size > MAX_UPLOAD_BYTES) return { ok: false, message: '超过 20 MiB' }
  const bytes = new Uint8Array(await file.arrayBuffer())
  const kind = magic(bytes)
  if (!kind) return { ok: false, message: '仅支持 JPG、JPEG、PNG' }
  const bitmap = await createImageBitmap(file).catch(() => null)
  if (!bitmap) return { ok: false, message: '图片无法解码' }
  const width = bitmap.width
  const height = bitmap.height
  bitmap.close()
  if (width <= 0 || height <= 0 || width * height > MAX_PIXELS) {
    return { ok: false, message: '超过 40MP 或尺寸非法' }
  }
  const orientationError = orientation(width, height)
  if (orientationError) return { ok: false, message: orientationError }
  return { ok: true, width, height, bytes: file.size, kind }
}
