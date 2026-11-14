import pb from './pb'
import { zhError } from './errors'

const CHUNK_THRESHOLD = 1 * 1024 * 1024 // use chunked path above 1MB
const DEFAULT_CHUNK = 2 * 1024 * 1024
const RESUME_KEY = 'hz_upload_sessions_v1'

const EXT_MIME = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  gif: 'image/gif',
  webp: 'image/webp',
  bmp: 'image/bmp',
  tif: 'image/tiff',
  tiff: 'image/tiff',
  heic: 'image/heic',
  heif: 'image/heif',
  avif: 'image/avif',
  mp4: 'video/mp4',
  m4v: 'video/x-m4v',
  mov: 'video/quicktime',
  webm: 'video/webm',
  avi: 'video/x-msvideo',
  mkv: 'video/x-matroska',
  '3gp': 'video/3gpp',
  mpeg: 'video/mpeg',
  mpg: 'video/mpeg',
  pdf: 'application/pdf',
  mp3: 'audio/mpeg',
  m4a: 'audio/mp4',
  aac: 'audio/aac',
  wav: 'audio/wav',
  ogg: 'audio/ogg',
}

function loadResumeMap() {
  try {
    return JSON.parse(localStorage.getItem(RESUME_KEY) || '{}')
  } catch {
    return {}
  }
}

function saveResumeMap(map) {
  localStorage.setItem(RESUME_KEY, JSON.stringify(map))
}

function fileKey(file) {
  return `${file.name}::${file.size}::${file.lastModified}`
}

export function shouldUseChunked(file) {
  return file && file.size > CHUNK_THRESHOLD
}

function guessMime(file) {
  const typed = String(file?.type || '').trim().toLowerCase()
  if (typed && typed !== 'application/octet-stream') {
    if (typed === 'image/jpg' || typed === 'image/pjpeg') return 'image/jpeg'
    if (typed === 'image/x-png') return 'image/png'
    if (typed === 'image/x-ms-bmp') return 'image/bmp'
    if (typed === 'audio/mp3') return 'audio/mpeg'
    return typed
  }
  const name = String(file?.name || '')
  const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : ''
  return EXT_MIME[ext] || 'application/octet-stream'
}

/** Ensure File has a PocketBase-accepted MIME (extension fallback). */
export function normalizeUploadFile(file) {
  if (!file) return file
  const mime = guessMime(file)
  if (file.type === mime && file.name) return file
  try {
    return new File([file], file.name || `upload-${Date.now()}`, {
      type: mime,
      lastModified: file.lastModified || Date.now(),
    })
  } catch {
    return file
  }
}

async function authHeaders() {
  const token = pb.authStore.token
  return {
    Authorization: token,
  }
}

function throwApiError(data, fallback) {
  const err = new Error(data?.message || fallback)
  err.data = data
  err.response = { data }
  throw err
}

export async function initSession(meta) {
  const res = await fetch('/api/hz/upload/init', {
    method: 'POST',
    headers: {
      ...(await authHeaders()),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      filename: meta.filename,
      size: meta.size,
      mime: meta.mime,
      category: meta.category,
      chunkSize: meta.chunkSize || DEFAULT_CHUNK,
      title: meta.title,
      occurred_time: meta.occurred_time,
      related_persons: meta.related_persons,
      description: meta.description || '',
      external_link: meta.external_link || '',
    }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throwApiError(data, '初始化分片上传失败')
  return data
}

export async function getStatus(sessionId) {
  const res = await fetch(`/api/hz/upload/status/${sessionId}`, {
    headers: await authHeaders(),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throwApiError(data, '查询上传状态失败')
  return data
}

export async function uploadChunk(sessionId, index, blob, onRetry) {
  const maxAttempts = 4
  let lastErr
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const form = new FormData()
      form.append('chunk', blob, `chunk-${index}`)
      const res = await fetch(`/api/hz/upload/chunk/${sessionId}/${index}`, {
        method: 'POST',
        headers: await authHeaders(),
        body: form,
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throwApiError(data, `分片 ${index} 上传失败`)
      return data
    } catch (e) {
      lastErr = e
      onRetry?.(attempt, e)
      await new Promise((r) => setTimeout(r, 400 * attempt))
    }
  }
  throw lastErr || new Error('分片上传失败')
}

export async function completeSession(sessionId, fields = {}) {
  const res = await fetch(`/api/hz/upload/complete/${sessionId}`, {
    method: 'POST',
    headers: {
      ...(await authHeaders()),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(fields),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throwApiError(data, '合并上传失败')
  return data
}

export async function abortSession(sessionId) {
  try {
    await fetch(`/api/hz/upload/session/${sessionId}`, {
      method: 'DELETE',
      headers: await authHeaders(),
    })
  } catch (_) {}
}

/**
 * Upload one file with chunking + resume.
 * @returns {Promise<object>} archive record
 */
export async function uploadFileChunked(file, fields, { onProgress, signal } = {}) {
  const normalized = normalizeUploadFile(file)
  const key = fileKey(normalized)
  const resumeMap = loadResumeMap()
  let sessionId = resumeMap[key]?.sessionId || ''
  let chunkSize = resumeMap[key]?.chunkSize || DEFAULT_CHUNK
  let totalChunks = resumeMap[key]?.totalChunks || 0
  let received = new Set(resumeMap[key]?.received || [])

  if (sessionId) {
    try {
      const st = await getStatus(sessionId)
      received = new Set(st.received || [])
      totalChunks = st.totalChunks
    } catch {
      sessionId = ''
      received = new Set()
    }
  }

  if (!sessionId) {
    const init = await initSession({
      filename: normalized.name,
      size: normalized.size,
      mime: guessMime(normalized),
      category: fields.category,
      chunkSize: DEFAULT_CHUNK,
      ...fields,
    })
    sessionId = init.sessionId
    chunkSize = init.chunkSize
    totalChunks = init.totalChunks
    received = new Set()
  }

  onProgress?.({ received: received.size, totalChunks, percent: 1, sessionId })

  resumeMap[key] = {
    sessionId,
    chunkSize,
    totalChunks,
    received: [...received],
    updatedAt: Date.now(),
  }
  saveResumeMap(resumeMap)

  for (let i = 0; i < totalChunks; i++) {
    if (signal?.aborted) throw new Error('已取消上传')
    if (received.has(i)) {
      onProgress?.({
        received: received.size,
        totalChunks,
        percent: Math.round((received.size / totalChunks) * 100),
        sessionId,
      })
      continue
    }
    const start = i * chunkSize
    const end = Math.min(normalized.size, start + chunkSize)
    const blob = normalized.slice(start, end)
    await uploadChunk(sessionId, i, blob)
    received.add(i)
    resumeMap[key] = {
      sessionId,
      chunkSize,
      totalChunks,
      received: [...received],
      updatedAt: Date.now(),
    }
    saveResumeMap(resumeMap)
    onProgress?.({
      received: received.size,
      totalChunks,
      percent: Math.round((received.size / totalChunks) * 100),
      sessionId,
    })
  }

  const record = await completeSession(sessionId, fields)
  delete resumeMap[key]
  saveResumeMap(resumeMap)
  return record
}

function playbackFieldsFor(category, files) {
  if (category !== 'video') return { playback_status: 'none', playback_note: '' }
  const name = files?.[0]?.name || ''
  if (/\.(mp4|m4v|webm)$/i.test(name)) {
    return { playback_status: 'native', playback_note: '浏览器可直接播放原文件' }
  }
  return { playback_status: 'pending', playback_note: '正在转码为微信友好 MP4，请稍候…' }
}

const ALLOWED_FIELD_KEYS = new Set([
  'title',
  'category',
  'occurred_time',
  'related_persons',
  'description',
  'external_link',
  // uploader is set by archives_uploader.pb.js from auth — never send from client
  // (String(user) → "[object Object]" caused mobile「上传者：内容不符合要求」).
  'uploader_name',
  'likes_count',
  'playback_status',
  'playback_note',
  'duration_sec',
])

/** PocketBase record id → safe string; never String(object) → "[object Object]". */
export function resolveRecordId(value) {
  if (value == null || value === '') return ''
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number') return String(value)
  if (typeof value === 'object') {
    const id = value.id ?? value.record?.id
    if (typeof id === 'string' && id.trim()) return id.trim()
  }
  return ''
}

function formFieldValue(key, value) {
  if (value == null || value === '') return null
  if (typeof value === 'object') {
    // Never append "[object Object]" into multipart (breaks relation fields).
    const id = resolveRecordId(value)
    return id || null
  }
  const s = String(value)
  if (!s || s === '[object Object]') return null
  return s
}

/** Sanitize filename for WeChat/iOS path-like or empty names. */
export function safeUploadFilename(file, fallbackExt = 'bin') {
  let name = String(file?.name || '').trim()
  // Strip fake path prefixes from some WebViews
  name = name.replace(/^.*[/\\]/, '')
  name = name.replace(/[^\w.\u4e00-\u9fff()\-+]+/g, '_')
  name = name.replace(/_+/g, '_').replace(/^_|_$/g, '')
  if (!name || name === '.' || name === '..') {
    const mime = guessMime(file)
    const ext =
      Object.entries(EXT_MIME).find(([, m]) => m === mime)?.[0] ||
      fallbackExt
    name = `upload-${Date.now()}.${ext}`
  }
  if (name.length > 120) {
    const dot = name.lastIndexOf('.')
    const ext = dot > 0 ? name.slice(dot) : ''
    name = name.slice(0, 120 - ext.length) + ext
  }
  return name
}

/** Ensure multi-select files keep distinct names (WeChat often reuses image.jpg). */
export function uniqueUploadNames(files) {
  const seen = new Map()
  return (files || []).map((file, index) => {
    const nf = normalizeUploadFile(file)
    let name = safeUploadFilename(nf, 'jpg')
    const key = name.toLowerCase()
    const n = (seen.get(key) || 0) + 1
    seen.set(key, n)
    if (n > 1) {
      const dot = name.lastIndexOf('.')
      const base = dot > 0 ? name.slice(0, dot) : name
      const ext = dot > 0 ? name.slice(dot) : ''
      name = `${base}_${n}${ext}`
    }
    // also stamp index to avoid collisions after PB rewrite
    if ((files || []).length > 1) {
      const dot = name.lastIndexOf('.')
      const base = dot > 0 ? name.slice(0, dot) : name
      const ext = dot > 0 ? name.slice(dot) : ''
      name = `${base}_p${index + 1}${ext}`
    }
    return { file: nf, name }
  })
}

/** Direct (non-chunked) create via PocketBase SDK — for small files / links. */
export async function uploadDirect(files, fields, { coverFile } = {}) {
  const form = new FormData()
  const merged = { ...fields, ...playbackFieldsFor(fields.category, files) }
  delete merged.uploader // server hook binds from authRecord
  Object.entries(merged).forEach(([k, v]) => {
    if (!ALLOWED_FIELD_KEYS.has(k)) return
    const sv = formFieldValue(k, v)
    if (sv == null) return
    form.append(k, sv)
  })
  for (const { file, name } of uniqueUploadNames(files)) {
    form.append('media_files', file, name)
  }
  if (coverFile) {
    const cf = normalizeUploadFile(coverFile)
    form.append('cover_file', cf, safeUploadFilename(cf, 'jpg') || 'cover.jpg')
  }
  // Visible by default (PB bool defaults false without this)
  form.append('listed', true)
  form.append('sort_order', 0)
  try {
    return await pb.collection('archives').create(form, { requestKey: null })
  } catch (e) {
    const msg = zhError(e, '创建档案失败，请检查文件与填写内容')
    const err = new Error(msg)
    err.cause = e
    err.data = e?.data || e?.response
    err.response = e?.response
    err.status = e?.status
    throw err
  }
}

/**
 * Upload many files into ONE archive. Uses direct multipart when possible;
 * if the first file needs chunking, chunk it then append the rest via update
 * (replace with full set after collecting blobs is avoided — we create with
 * first file then PATCH remaining as additional media_files in one request).
 */
export async function uploadManyAsOneArchive(files, fields, { coverFile, onProgress } = {}) {
  const list = Array.from(files || [])
  if (!list.length) return uploadDirect([], fields)
  if (list.length === 1) {
    if (shouldUseChunked(list[0])) {
      const rec = await uploadFileChunked(list[0], fields, { onProgress })
      if (coverFile || fields.duration_sec) {
        try {
          return (
            (await patchMediaMeta(rec.id, {
              coverFile,
              durationSec: fields.duration_sec,
            })) || rec
          )
        } catch {
          return rec
        }
      }
      return rec
    }
    return uploadDirect(list, fields, { coverFile })
  }

  // Prefer single create with all files (PB keeps all media_files).
  // Chunk only when the batch is one large file (handled above).
  onProgress?.({ percent: 5 })
  const record = await uploadDirect(list, fields, { coverFile })
  onProgress?.({ percent: 100 })
  return record
}

/** Attach cover/duration after chunked create (complete API may not take files). */
export async function patchMediaMeta(recordId, { coverFile, durationSec } = {}) {
  if (!recordId) return null
  if (!coverFile && (durationSec == null || durationSec === '')) return null
  const form = new FormData()
  if (durationSec != null && durationSec !== '') form.append('duration_sec', String(durationSec))
  if (coverFile) {
    const cf = normalizeUploadFile(coverFile)
    form.append('cover_file', cf, cf.name || 'cover.jpg')
  }
  try {
    return await pb.collection('archives').update(recordId, form, { requestKey: null })
  } catch (e) {
    const msg = zhError(e, '保存封面或时长失败')
    const err = new Error(msg)
    err.cause = e
    err.data = e?.data || e?.response
    throw err
  }
}
