/** Client-side image compress + video cover/duration for upload preview. */

const IMAGE_MAX_EDGE = 1920
const IMAGE_QUALITY = 0.82
const COVER_MAX_EDGE = 960
const COVER_QUALITY = 0.8

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      resolve(img)
    }
    img.onerror = (e) => {
      URL.revokeObjectURL(url)
      reject(e)
    }
    img.src = url
  })
}

function canvasToJpegFile(canvas, name, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) return reject(new Error('压缩失败'))
        const base = String(name || 'image').replace(/\.[^.]+$/, '')
        resolve(new File([blob], `${base}.jpg`, { type: 'image/jpeg', lastModified: Date.now() }))
      },
      'image/jpeg',
      quality,
    )
  })
}

/** Compress raster image; skip GIF/SVG; keep HEIC as-is (browser often can't decode). */
export async function compressImageFile(file, { maxEdge = IMAGE_MAX_EDGE, quality = IMAGE_QUALITY } = {}) {
  const type = String(file.type || '').toLowerCase()
  const name = String(file.name || '').toLowerCase()
  if (type.includes('gif') || name.endsWith('.gif')) return { file, compressed: false, skipped: 'gif' }
  if (type.includes('heic') || type.includes('heif') || /\.(heic|heif)$/.test(name)) {
    return { file, compressed: false, skipped: 'heic' }
  }
  if (!type.startsWith('image/') && !/\.(jpe?g|png|webp|bmp|tiff?)$/.test(name)) {
    return { file, compressed: false, skipped: 'not-image' }
  }

  try {
    const img = await loadImage(file)
    const scale = Math.min(1, maxEdge / Math.max(img.width, img.height))
    const w = Math.max(1, Math.round(img.width * scale))
    const h = Math.max(1, Math.round(img.height * scale))
    if (scale >= 0.98 && file.size <= 400 * 1024 && type === 'image/jpeg') {
      return { file, compressed: false, skipped: 'already-small', width: img.width, height: img.height }
    }
    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d')
    ctx.drawImage(img, 0, 0, w, h)
    const out = await canvasToJpegFile(canvas, file.name, quality)
    if (out.size >= file.size * 0.95 && type === 'image/jpeg') {
      return { file, compressed: false, skipped: 'no-gain', width: img.width, height: img.height }
    }
    return { file: out, compressed: true, width: w, height: h, originalSize: file.size, size: out.size }
  } catch {
    return { file, compressed: false, skipped: 'decode-failed' }
  }
}

export async function extractVideoMeta(file) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const video = document.createElement('video')
    video.preload = 'metadata'
    video.muted = true
    video.playsInline = true
    video.src = url

    const fail = () => {
      URL.revokeObjectURL(url)
      resolve({ duration: 0, coverFile: null })
    }

    video.onerror = fail
    video.onloadedmetadata = () => {
      const duration = Number.isFinite(video.duration) ? Math.round(video.duration) : 0
      const seekTo = Math.min(0.2, Math.max(0, (duration || 1) * 0.05))
      const capture = () => {
        try {
          const w0 = video.videoWidth || 640
          const h0 = video.videoHeight || 360
          const scale = Math.min(1, COVER_MAX_EDGE / Math.max(w0, h0))
          const canvas = document.createElement('canvas')
          canvas.width = Math.max(1, Math.round(w0 * scale))
          canvas.height = Math.max(1, Math.round(h0 * scale))
          canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
          canvas.toBlob(
            (blob) => {
              URL.revokeObjectURL(url)
              if (!blob) return resolve({ duration, coverFile: null })
              const coverFile = new File([blob], 'cover.jpg', { type: 'image/jpeg', lastModified: Date.now() })
              resolve({ duration, coverFile, width: canvas.width, height: canvas.height })
            },
            'image/jpeg',
            COVER_QUALITY,
          )
        } catch {
          fail()
        }
      }
      if (seekTo > 0) {
        video.currentTime = seekTo
        video.onseeked = capture
      } else {
        capture()
      }
    }
  })
}

export function formatDuration(sec) {
  const n = Math.max(0, Math.round(Number(sec) || 0))
  const m = Math.floor(n / 60)
  const s = n % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function thumbUrl(pb, record, filename, size = '600x0') {
  if (!record || !filename) return ''
  try {
    return pb.files.getURL(record, filename, { thumb: size })
  } catch {
    return pb.files.getURL(record, filename)
  }
}

export function coverOrThumbUrl(pb, archive) {
  const cover = archive?.cover_file
  const coverName = Array.isArray(cover) ? cover[0] : cover
  if (coverName) return thumbUrl(pb, archive, coverName, '600x0') || pb.files.getURL(archive, coverName)
  const files = archive?.media_files || []
  const first = files[0]
  if (!first) return ''
  if (['image', 'scan'].includes(archive.category)) {
    return thumbUrl(pb, archive, first, '600x0') || pb.files.getURL(archive, first)
  }
  return ''
}

/** Prepare files for upload: compress images; for video attach cover+duration. */
export async function prepareUploadFiles(files, category) {
  const list = Array.from(files || [])
  const prepared = []
  let coverFile = null
  let durationSec = 0
  const notes = []

  for (const f of list) {
    if (category === 'image' || category === 'scan' || String(f.type).startsWith('image/')) {
      const r = await compressImageFile(f)
      prepared.push(r.file)
      if (r.compressed) {
        const saved = Math.max(0, (r.originalSize || f.size) - r.size)
        notes.push(`${f.name} 已压缩（约省 ${Math.round(saved / 1024)}KB）`)
      }
    } else {
      prepared.push(f)
    }
  }

  if (category === 'video' && prepared[0]) {
    const meta = await extractVideoMeta(prepared[0])
    durationSec = meta.duration || 0
    coverFile = meta.coverFile
    if (durationSec) notes.push(`视频时长 ${formatDuration(durationSec)}`)
    if (coverFile) notes.push('已提取视频封面')
  }

  return { files: prepared, coverFile, durationSec, notes }
}
