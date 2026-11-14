'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'

import { ApiError, apiFetch, apiFetchBlob } from '@/lib/api'
import { allocateDownloadFileName, extensionForContentType } from '@/lib/realphotos-download'
import { formatByteSizeMb, originKindLabel } from '@/lib/realphotos-labels'
import { inspectLocalFile } from '@/lib/realphotos-s1'

type Asset = {
  id: string
  originKind: string
  width: number
  height: number
  byteSize: number
  objectKey?: string
  contentType?: string
  displayName?: string
  downloadBasename?: string
  degraded?: boolean
  locked?: boolean
  requestedWidth?: number | null
  requestedHeight?: number | null
  actualWidth?: number
  actualHeight?: number
}

const UPLOAD_BATCH_MAX = 20
const PAGE_SIZE = 20

export default function RealphotosLibraryPage() {
  const router = useRouter()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [items, setItems] = useState<Asset[]>([])
  const [total, setTotal] = useState(0)
  const [message, setMessage] = useState('')
  const [originFilter, setOriginFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Record<string, true>>({})
  const [thumbs, setThumbs] = useState<Record<string, string>>({})
  const [preview, setPreview] = useState<{ id: string; url: string } | null>(null)
  const [frozen, setFrozen] = useState(false)
  const downloadUsedNames = useRef(new Map<string, number>())

  useEffect(() => {
    void apiFetch<{ preReviewFrozen?: boolean }>('/api/v1/realphotos/me')
      .then((data) => setFrozen(Boolean(data.preReviewFrozen)))
      .catch(() => setFrozen(false))
  }, [])

  const reload = useCallback(async () => {
    const params = new URLSearchParams({
      page: String(page),
      pageSize: String(PAGE_SIZE),
    })
    if (originFilter !== 'all') {
      params.set('originKind', originFilter)
    }
    const data = await apiFetch<{ items: Asset[]; total: number; page: number; pageSize: number }>(
      `/api/v1/realphotos/assets?${params.toString()}`,
    )
    setItems(data.items || [])
    setTotal(Number(data.total || 0))
  }, [page, originFilter])

  useEffect(() => {
    void reload().catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '资源加载失败'))
  }, [reload])

  useEffect(() => {
    let cancelled = false
    const created: string[] = []
    async function loadThumbs() {
      setThumbs({})
      for (const item of items) {
        if (cancelled) return
        if (!item.objectKey) continue
        try {
          const blob = await apiFetchBlob(`/api/v1/realphotos/gateway/objects/${item.objectKey}`)
          if (cancelled) return
          const url = URL.createObjectURL(blob)
          created.push(url)
          setThumbs((prev) => ({ ...prev, [item.id]: url }))
        } catch {
          // 网关鉴权失败时保留占位
        }
      }
    }
    void loadThumbs()
    return () => {
      cancelled = true
      for (const url of created) URL.revokeObjectURL(url)
    }
  }, [items])

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const selectedIds = Object.keys(selected)
  const query = search.trim().toLowerCase()
  const visibleItems = useMemo(() => {
    if (!query) return items
    return items.filter((item) => {
      const name = String(item.displayName || item.downloadBasename || '').toLowerCase()
      const origin = String(item.originKind || '').toLowerCase()
      const id = String(item.id || '').toLowerCase()
      return name.includes(query) || origin.includes(query) || id.includes(query) || originKindLabel(item.originKind).includes(search.trim())
    })
  }, [items, query, search])

  const selectableOnPage = visibleItems.filter((item) => !item.locked)
  const allPageSelected =
    selectableOnPage.length > 0 && selectableOnPage.every((item) => Boolean(selected[item.id]))
  const somePageSelected = selectableOnPage.some((item) => Boolean(selected[item.id]))

  function toggle(id: string) {
    setSelected((prev) => {
      const next = { ...prev }
      if (next[id]) delete next[id]
      else next[id] = true
      return next
    })
  }

  function toggleSelectAllPage() {
    setSelected((prev) => {
      const next = { ...prev }
      if (allPageSelected) {
        for (const item of selectableOnPage) {
          delete next[item.id]
        }
      } else {
        for (const item of selectableOnPage) {
          next[item.id] = true
        }
      }
      return next
    })
  }

  async function removeOne(id: string) {
    try {
      await apiFetch(`/api/v1/realphotos/assets/${id}`, { method: 'DELETE' })
      setSelected((prev) => {
        const next = { ...prev }
        delete next[id]
        return next
      })
      await reload()
      setMessage(`已删除资源 ${id}`)
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '删除失败')
    }
  }

  async function downloadOne(item: Asset, usedNames: Map<string, number> = downloadUsedNames.current) {
    if (!item.objectKey) {
      setMessage('缺少对象键，无法经网关下载')
      return
    }
    try {
      const blob = await apiFetchBlob(`/api/v1/realphotos/gateway/objects/${item.objectKey}`)
      const ext = extensionForContentType(item.contentType || blob.type)
      const base = item.downloadBasename || item.displayName || `${item.originKind}_${item.id}`
      const fileName = allocateDownloadFileName(base, ext, usedNames)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = fileName
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '下载失败')
    }
  }

  async function downloadSelected() {
    const targets = items.filter((item) => selected[item.id])
    const batchNames = new Map<string, number>()
    for (const item of targets) {
      await downloadOne(item, batchNames)
    }
  }

  async function removeSelected() {
    for (const id of selectedIds) {
      await removeOne(id)
    }
  }

  function goProcess() {
    const unlocked = selectedIds.filter((id) => {
      const onPage = items.find((item) => item.id === id)
      if (onPage) return !onPage.locked
      return true
    })
    const lockedCount = selectedIds.length - unlocked.length
    const ids = unlocked.slice(0, 10)
    if (!ids.length) {
      setMessage(lockedCount ? '所选资源均已锁定，不能去处理' : '请先勾选 1–10 张资源')
      return
    }
    if (lockedCount > 0) {
      setMessage(`已跳过 ${lockedCount} 张锁定图；去处理最多 10 张`)
    } else if (unlocked.length > 10) {
      setMessage('去处理最多 10 张，已截取前 10 张')
    }
    router.push(`/realphotos/batch?assetIds=${ids.join(',')}`)
  }

  async function onLocalUpload(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return
    if (frozen) {
      setMessage('账号已因预审冻结，不能上传新资源')
      return
    }
    const files = Array.from(fileList)
    if (files.length > UPLOAD_BATCH_MAX) {
      setMessage(`单次最多上传 ${UPLOAD_BATCH_MAX} 张，整批已拒绝`)
      return
    }
    for (const file of files) {
      const inspected = await inspectLocalFile(file)
      if (!inspected.ok) {
        setMessage(inspected.message)
        return
      }
    }
    try {
      if (files.length === 1) {
        const body = new FormData()
        body.set('file', files[0])
        await apiFetch('/api/v1/realphotos/assets', { method: 'POST', body })
      } else {
        const body = new FormData()
        for (const file of files) {
          body.append('files', file)
        }
        await apiFetch('/api/v1/realphotos/assets/batch', { method: 'POST', body })
      }
      setMessage(`本地上传已入库 ${files.length} 张`)
      setPage(1)
      await reload()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '上传失败')
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">图片资源</h1>
      <p className="text-sm">{message}</p>
      {frozen ? (
        <p className="text-sm text-amber-800">
          账号已因预审冻结：不可上传/导入/生图；仍可登录、列表与经网关下载保留期内资源。
        </p>
      ) : null}

      <input
        ref={fileInputRef}
        className="sr-only"
        type="file"
        multiple
        disabled={frozen}
        accept="image/jpeg,image/png,.jpg,.jpeg,.png"
        onChange={(event) => {
          void onLocalUpload(event.target.files)
          event.target.value = ''
        }}
      />

      <section className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">添加图片：</span>
        {frozen ? (
          <span className="border px-2 py-1 opacity-50">URL 导入（已冻结）</span>
        ) : (
          <Link className="border px-2 py-1" href="/realphotos/imports">
            URL 导入
          </Link>
        )}
        {frozen ? (
          <span className="border px-2 py-1 opacity-50">本地上传（已冻结）</span>
        ) : (
          <button
            className="border px-2 py-1"
            type="button"
            onClick={() => fileInputRef.current?.click()}
          >
            本地上传
          </button>
        )}
        {frozen ? (
          <span className="border px-2 py-1 opacity-50">文生图（已冻结）</span>
        ) : (
          <Link className="border px-2 py-1" href="/realphotos/generate?mode=text_to_image">
            文生图
          </Link>
        )}
        {frozen ? (
          <span className="border px-2 py-1 opacity-50">图生图（已冻结）</span>
        ) : (
          <Link className="border px-2 py-1" href="/realphotos/generate?mode=image_to_image">
            图生图
          </Link>
        )}
      </section>

      <section className="flex flex-wrap gap-2 text-sm">
        <button className="border px-2 py-1" type="button" onClick={() => goProcess()}>
          去处理（已选 {selectedIds.length}）
        </button>
        <button className="border px-2 py-1" type="button" onClick={() => void downloadSelected()}>
          批量下载
        </button>
        <button className="border px-2 py-1" type="button" onClick={() => void removeSelected()}>
          批量删除
        </button>
      </section>

      <section className="flex flex-wrap items-center gap-3 text-sm">
        <label>
          搜索
          <input
            className="ml-2 border px-2 py-1"
            value={search}
            placeholder="文件名 / 来源 / ID"
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label>
          来源
          <select
            className="ml-2 border px-2 py-1"
            value={originFilter}
            onChange={(event) => {
              setOriginFilter(event.target.value)
              setPage(1)
            }}
          >
            <option value="all">全部</option>
            <option value="local_upload">本地上传</option>
            <option value="text_to_image">文生图</option>
            <option value="image_to_image">图生图</option>
          </select>
        </label>
        <span>
          第 {page} / {pageCount} 页 · 共 {total} 条 · 已选 {selectedIds.length} 张
        </span>
        <button
          className="border px-2 py-1"
          type="button"
          disabled={page <= 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          上一页
        </button>
        <button
          className="border px-2 py-1"
          type="button"
          disabled={page >= pageCount}
          onClick={() => setPage((p) => p + 1)}
        >
          下一页
        </button>
      </section>
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="text-left">
              <label className="inline-flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={allPageSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = !allPageSelected && somePageSelected
                  }}
                  disabled={selectableOnPage.length === 0}
                  onChange={() => toggleSelectAllPage()}
                  aria-label="全选本页"
                />
                全选
              </label>
            </th>
            <th className="text-left">缩略图</th>
            <th className="text-left">文件名</th>
            <th className="text-left">来源</th>
            <th className="text-left">状态</th>
            <th className="text-left">分辨率</th>
            <th className="text-left">大小</th>
            <th className="text-left">操作</th>
          </tr>
        </thead>
        <tbody>
          {visibleItems.length === 0 ? (
            <tr>
              <td colSpan={8}>暂无资源</td>
            </tr>
          ) : (
            visibleItems.map((item) => (
              <tr key={item.id} className={item.locked ? 'opacity-70' : undefined}>
                <td>
                  <input
                    type="checkbox"
                    checked={Boolean(selected[item.id])}
                    disabled={Boolean(item.locked)}
                    onChange={() => toggle(item.id)}
                  />
                </td>
                <td>
                  {thumbs[item.id] ? (
                    <button
                      type="button"
                      className="block"
                      onClick={() => setPreview({ id: item.id, url: thumbs[item.id] })}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={thumbs[item.id]} alt="" className="h-10 w-10 object-cover border" />
                    </button>
                  ) : (
                    <span className="inline-block h-10 w-10 border text-center leading-10 text-xs">图</span>
                  )}
                </td>
                <td>
                  {item.displayName || `${item.originKind}_${item.id}`}
                  {item.requestedWidth && item.actualWidth && item.requestedWidth !== item.actualWidth
                    ? ` · 请求${item.requestedWidth}×${item.requestedHeight} / 实际${item.actualWidth}×${item.actualHeight}`
                    : ''}
                </td>
                <td>{originKindLabel(item.originKind)}</td>
                <td>{item.locked ? '图片锁定' : '可用'}</td>
                <td>
                  {item.width}×{item.height}
                </td>
                <td>{formatByteSizeMb(item.byteSize)}</td>
                <td className="space-x-2">
                  <button className="border px-2 py-0.5" type="button" onClick={() => void downloadOne(item)}>
                    下载
                  </button>
                  <button className="border px-2 py-0.5" type="button" onClick={() => void removeOne(item.id)}>
                    删除
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      {preview ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6" onClick={() => setPreview(null)}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={preview.url} alt={`资源 ${preview.id}`} className="max-h-full max-w-full border bg-white" />
        </div>
      ) : null}
    </main>
  )
}
