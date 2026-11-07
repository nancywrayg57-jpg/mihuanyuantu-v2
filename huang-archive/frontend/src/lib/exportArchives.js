import { zipSync, strToU8 } from 'fflate'
import pb from './pb'

/** Build a JSON export of archives (+ memories/likes) — metadata only. */
export async function buildArchiveExport() {
  const archives = await pb.collection('archives').getFullList({ sort: '-created' })
  const memories = await pb.collection('memories').getFullList({ sort: '-created' }).catch(() => [])
  const likes = await pb.collection('archive_likes').getFullList().catch(() => [])
  return {
    exported_at: new Date().toISOString(),
    service: 'huang-archive',
    counts: {
      archives: archives.length,
      memories: memories.length,
      likes: likes.length,
    },
    archives,
    memories,
    likes,
  }
}

export function downloadJson(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  downloadBlob(blob, filename)
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

async function fetchFileBytes(record, filename) {
  if (!record || !filename) return null
  const url = pb.files.getUrl(record, filename)
  const headers = {}
  if (pb.authStore.token) headers.Authorization = pb.authStore.token
  const res = await fetch(url, { headers })
  if (!res.ok) throw new Error(`下载文件失败：${filename}`)
  return new Uint8Array(await res.arrayBuffer())
}

function fileNames(value) {
  if (!value) return []
  return Array.isArray(value) ? value.filter(Boolean) : [value]
}

/**
 * One-click full backup: ZIP with manifest + every archive media/cover/playback
 * and memory voice files. Progress callback: ({ done, total, label }).
 */
export async function downloadFullBackup({ onProgress } = {}) {
  const archives = await pb.collection('archives').getFullList({ sort: '-created' })
  const memories = await pb.collection('memories').getFullList({ sort: '-created' }).catch(() => [])
  const likes = await pb.collection('archive_likes').getFullList().catch(() => [])

  const jobs = []
  for (const a of archives) {
    for (const name of fileNames(a.media_files)) {
      jobs.push({ kind: 'archive-media', archive: a, filename: name })
    }
    for (const name of fileNames(a.cover_file)) {
      jobs.push({ kind: 'archive-cover', archive: a, filename: name })
    }
    for (const name of fileNames(a.playback_file)) {
      jobs.push({ kind: 'archive-playback', archive: a, filename: name })
    }
  }
  for (const m of memories) {
    for (const name of fileNames(m.voice_file)) {
      jobs.push({ kind: 'memory-voice', memory: m, filename: name })
    }
  }

  const total = jobs.length + 1
  let done = 0
  const bump = (label) => {
    done += 1
    onProgress?.({ done, total, label })
  }

  onProgress?.({ done: 0, total, label: '整理清单…' })

  /** @type {Record<string, Uint8Array>} */
  const out = {}
  const manifest = {
    exported_at: new Date().toISOString(),
    service: 'huang-archive',
    format: 'zip-v1',
    counts: {
      archives: archives.length,
      memories: memories.length,
      likes: likes.length,
      files: jobs.length,
    },
    archives,
    memories,
    likes,
  }
  out['manifest.json'] = strToU8(JSON.stringify(manifest, null, 2))
  bump('写入清单')

  for (const a of archives) {
    out[`archives/${a.id}/meta.json`] = strToU8(JSON.stringify(a, null, 2))
  }
  for (const m of memories) {
    out[`memories/${m.id}.json`] = strToU8(JSON.stringify(m, null, 2))
  }

  for (const job of jobs) {
    try {
      if (job.kind.startsWith('archive')) {
        const bytes = await fetchFileBytes(job.archive, job.filename)
        if (bytes) {
          const folder =
            job.kind === 'archive-cover'
              ? 'cover'
              : job.kind === 'archive-playback'
                ? 'playback'
                : 'media'
          out[`archives/${job.archive.id}/${folder}/${job.filename}`] = bytes
        }
      } else if (job.kind === 'memory-voice') {
        const bytes = await fetchFileBytes(job.memory, job.filename)
        if (bytes) out[`memories/${job.memory.id}/${job.filename}`] = bytes
      }
      bump(job.filename)
    } catch (e) {
      out[`_errors/${job.filename || 'file'}.txt`] = strToU8(String(e?.message || e))
      bump(`失败:${job.filename}`)
    }
  }

  const zipped = zipSync(out, { level: 1 })
  const day = new Date().toISOString().slice(0, 10)
  downloadBlob(new Blob([zipped], { type: 'application/zip' }), `huang-archive-backup-${day}.zip`)
  return manifest.counts
}
