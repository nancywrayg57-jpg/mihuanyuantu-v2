import pb from './pb'

const CHUNK_THRESHOLD = 1 * 1024 * 1024 // use chunked path above 1MB
const DEFAULT_CHUNK = 2 * 1024 * 1024
const RESUME_KEY = 'hz_upload_sessions_v1'

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

async function authHeaders() {
  const token = pb.authStore.token
  return {
    Authorization: token,
  }
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
  if (!res.ok) throw new Error(data.message || '初始化分片上传失败')
  return data
}

export async function getStatus(sessionId) {
  const res = await fetch(`/api/hz/upload/status/${sessionId}`, {
    headers: await authHeaders(),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.message || '查询上传状态失败')
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
      if (!res.ok) throw new Error(data.message || `分片 ${index} 上传失败`)
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
  if (!res.ok) throw new Error(data.message || '合并上传失败')
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
  const key = fileKey(file)
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
      filename: file.name,
      size: file.size,
      mime: file.type || 'application/octet-stream',
      category: fields.category,
      chunkSize: DEFAULT_CHUNK,
      ...fields,
    })
    sessionId = init.sessionId
    chunkSize = init.chunkSize
    totalChunks = init.totalChunks
    received = new Set()
  }

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
      onProgress?.({ received: received.size, totalChunks, percent: Math.round((received.size / totalChunks) * 100) })
      continue
    }
    const start = i * chunkSize
    const end = Math.min(file.size, start + chunkSize)
    const blob = file.slice(start, end)
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
    })
  }

  const record = await completeSession(sessionId, fields)
  delete resumeMap[key]
  saveResumeMap(resumeMap)
  return record
}

/** Direct (non-chunked) create via PocketBase SDK — for small files / links. */
export async function uploadDirect(files, fields) {
  const form = new FormData()
  Object.entries(fields).forEach(([k, v]) => {
    if (v != null && v !== '') form.append(k, String(v))
  })
  for (const f of files || []) {
    form.append('media_files', f, f.name || `upload-${Date.now()}`)
  }
  return pb.collection('archives').create(form, { requestKey: null })
}
