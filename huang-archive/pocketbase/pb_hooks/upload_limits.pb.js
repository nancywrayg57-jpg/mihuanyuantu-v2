/// <reference path="../pb_data/types.d.ts" />

// Soft per-type caps (PB file maxSize is video-sized 600MB).
// Fail-open if uploadedFiles shape is unavailable.

const LIMITS = {
  image: 30 * 1024 * 1024,
  video: 600 * 1024 * 1024,
  other: 100 * 1024 * 1024,
}

function kindOf(name, contentType) {
  const n = (name || "").toLowerCase()
  const t = (contentType || "").toLowerCase()
  if (t.startsWith("image/") || /\.(jpe?g|png|gif|webp|heic|heif|avif|bmp|tiff?)$/.test(n)) return "image"
  if (t.startsWith("video/") || /\.(mp4|mov|webm|m4v)$/.test(n)) return "video"
  return "other"
}

function guardFiles(e) {
  try {
    const bag = e.uploadedFiles
    if (!bag) return
    const files = bag["media_files"] || bag.media_files
    if (!files || !files.length) return
    for (const f of files) {
      const name = f.name || f.originalName || ""
      const size = Number(f.size || 0)
      if (!size) continue
      let ctype = ""
      try {
        ctype = f.contentType || (f.header && f.header.get && f.header.get("Content-Type")) || ""
      } catch (_) {}
      const kind = kindOf(name, ctype)
      const max = LIMITS[kind]
      if (size > max) {
        const mb = Math.round(max / 1024 / 1024)
        const label = kind === "image" ? "图片" : kind === "video" ? "视频" : "文件"
        throw new BadRequestError(label + "不能超过 " + mb + "MB")
      }
    }
  } catch (err) {
    if (err instanceof BadRequestError) throw err
    console.log("upload_limits hook skipped:", err)
  }
}

onRecordBeforeCreateRequest((e) => {
  guardFiles(e)
}, "archives")

onRecordBeforeUpdateRequest((e) => {
  guardFiles(e)
}, "archives")
