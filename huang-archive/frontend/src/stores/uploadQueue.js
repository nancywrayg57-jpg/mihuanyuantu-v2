import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  shouldUseChunked,
  uploadDirect,
  uploadFileChunked,
  abortSession,
  patchMediaMeta,
} from '../lib/chunkedUpload'
import { validateUploadFiles } from '../lib/uploadLimits'
import { useAuthStore } from './auth'

let seq = 1

export const useUploadQueueStore = defineStore('uploadQueue', () => {
  const items = ref([])
  const concurrency = 1
  let active = 0

  const pendingCount = computed(() => items.value.filter((i) => i.status === 'queued' || i.status === 'uploading').length)
  const visible = computed(() => items.value.slice(0, 20))

  function enqueue(job) {
    const id = `uq_${Date.now()}_${seq++}`
    const entry = {
      id,
      status: 'queued', // queued|uploading|done|error|cancelled
      progress: 0,
      error: '',
      title: job.title,
      category: job.category,
      files: job.files || [],
      coverFile: job.coverFile || null,
      durationSec: job.durationSec || 0,
      fields: job.fields,
      record: null,
      sessionId: '',
      createdAt: Date.now(),
    }
    const sizeErr = job.category === 'link' ? '' : validateUploadFiles(job.files, job.category)
    if (sizeErr) {
      entry.status = 'error'
      entry.error = sizeErr
      items.value.unshift(entry)
      return entry
    }
    items.value.unshift(entry)
    pump()
    return entry
  }

  async function pump() {
    if (active >= concurrency) return
    const next = items.value.find((i) => i.status === 'queued')
    if (!next) return
    active += 1
    next.status = 'uploading'
    next.progress = 2
    try {
      const auth = useAuthStore()
      const baseFields = {
        ...next.fields,
        uploader: auth.user.id,
        uploader_name: auth.displayName,
        likes_count: '0',
      }

      let record
      const metaFields = {
        ...baseFields,
        category: next.category,
        title: next.title,
        occurred_time: next.fields.occurred_time,
        related_persons: next.fields.related_persons,
        description: next.fields.description || '',
        external_link: next.fields.external_link || '',
        duration_sec: next.durationSec ? String(next.durationSec) : next.fields.duration_sec || '',
      }
      if (next.category === 'link' || !next.files.length) {
        record = await uploadDirect([], metaFields)
      } else if (next.files.length === 1 && shouldUseChunked(next.files[0])) {
        record = await uploadFileChunked(next.files[0], metaFields, {
          onProgress: ({ percent }) => {
            next.progress = Math.max(2, Math.min(99, percent))
          },
        })
        if (record?.id && (next.coverFile || next.durationSec)) {
          record = (await patchMediaMeta(record.id, {
            coverFile: next.coverFile,
            durationSec: next.durationSec,
          })) || record
        }
      } else {
        record = await uploadDirect(next.files, metaFields, { coverFile: next.coverFile })
      }
      next.record = record
      next.status = 'done'
      next.progress = 100
    } catch (e) {
      next.status = 'error'
      next.error = e?.message || '上传失败'
    } finally {
      active -= 1
      pump()
    }
  }

  function dismiss(id) {
    items.value = items.value.filter((i) => i.id !== id)
  }

  function clearFinished() {
    items.value = items.value.filter((i) => i.status === 'queued' || i.status === 'uploading')
  }

  async function cancel(id) {
    const it = items.value.find((i) => i.id === id)
    if (!it) return
    it.status = 'cancelled'
    if (it.sessionId) await abortSession(it.sessionId)
  }

  return {
    items,
    visible,
    pendingCount,
    enqueue,
    dismiss,
    clearFinished,
    cancel,
  }
})
