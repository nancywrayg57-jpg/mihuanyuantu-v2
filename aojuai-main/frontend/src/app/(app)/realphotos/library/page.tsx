'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'

import { RpPageHeader } from '@/components/realphotos/rp-page-header'
import { RpEmptyState, RpDialog, RpSkeletonRows, RpTableScroll } from '@/components/realphotos/rp-table'
import { toastTask } from '@/components/realphotos/surface'
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
const PAGE_SIZE = 10

/** 2026-11-18 UX-P1-1：长文件名中段省略，保留扩展名。 */
function truncateMiddle(name: string, max = 42): string {
  const value = String(name || '')
  if (value.length <= max) return value
  const head = Math.max(8, Math.floor((max - 1) * 0.6))
  const tail = Math.max(6, max - 1 - head)
  return `${value.slice(0, head)}…${value.slice(-tail)}`
}

export default function RealphotosLibraryPage() {
  const router = useRouter()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [items, setItems] = useState<Asset[]>([])
  const [total, setTotal] = useState(0)
  const [message, setMessage] = useState('')
  const [originFilter, setOriginFilter] = useState('all')
  const [sort, setSort] = useState('newest')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Record<string, true>>({})
  const [thumbs, setThumbs] = useState<Record<string, string>>({})
  const [preview, setPreview] = useState<{ id: string; url: string; fullUrl?: string; loading?: boolean } | null>(null)
  // 2026-11-17：被锁定的图片在资源列表直接申诉（任务详情不再提供入口）
  const [appealTarget, setAppealTarget] = useState<Asset | null>(null)
  const [appealText, setAppealText] = useState('')
  const [appealNote, setAppealNote] = useState('')
  const [appealBusy, setAppealBusy] = useState(false)
  const [frozen, setFrozen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [uploadProgress, setUploadProgress] = useState<{ done: number; total: number } | null>(null)
  const [downloadProgress, setDownloadProgress] = useState<{ done: number; total: number } | null>(null)
  const downloadUsedNames = useRef(new Map<string, number>())

  useEffect(() => {
    void apiFetch<{ preReviewFrozen?: boolean }>('/api/v1/realphotos/me')
      .then((data) => setFrozen(Boolean(data.preReviewFrozen)))
      .catch(() => setFrozen(false))
  }, [])

  const reload = useCallback(async () => {
    setLoading(true)
    const params = new URLSearchParams({
      page: String(page),
      pageSize: String(PAGE_SIZE),
      sort,
    })
    if (originFilter !== 'all') {
      params.set('originKind', originFilter)
    }
    try {
      const data = await apiFetch<{ items: Asset[]; total: number; page: number; pageSize: number }>(
        `/api/v1/realphotos/assets?${params.toString()}`,
      )
      setItems(data.items || [])
      setTotal(Number(data.total || 0))
    } finally {
      setLoading(false)
    }
  }, [page, originFilter, sort])

  useEffect(() => {
    void reload().catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '资源加载失败'))
  }, [reload])

  // 2026-11-17：放大查看先展示缩略图，再拉 1600px 大图，避免只放大 160px 小图。
  async function openPreview(item: { id: string; objectKey?: string | null }) {
    const placeholder = thumbs[item.id]
    setPreview({ id: item.id, url: placeholder || '', loading: Boolean(item.objectKey) })
    if (!item.objectKey) return
    const path = item.objectKey.split('/').map(encodeURIComponent).join('/')
    try {
      const blob = await apiFetchBlob(`/api/v1/realphotos/gateway/objects/${path}?thumb=1600`)
      const url = URL.createObjectURL(blob)
      setPreview((prev) => {
        if (!prev || prev.id !== item.id) {
          URL.revokeObjectURL(url)
          return prev
        }
        if (prev.fullUrl) URL.revokeObjectURL(prev.fullUrl)
        return { ...prev, fullUrl: url, loading: false }
      })
    } catch {
      setPreview((prev) => (prev && prev.id === item.id ? { ...prev, loading: false } : prev))
    }
  }

  useEffect(() => {
    let cancelled = false
    const created: string[] = []
    async function loadThumbs() {
      setThumbs({})
      // 2026-11-17：改拉 160px 缩略图（服务端缓存），并发 4，避免串行下载原图。
      const queue = items.filter((row) => Boolean(row.objectKey))
      const worker = async () => {
        for (;;) {
          const item = queue.shift()
          if (!item || cancelled || !item.objectKey) return
          try {
            const path = item.objectKey.split('/').map(encodeURIComponent).join('/')
            const blob = await apiFetchBlob(`/api/v1/realphotos/gateway/objects/${path}?thumb=160`)
            if (cancelled) return
            const url = URL.createObjectURL(blob)
            created.push(url)
            setThumbs((prev) => ({ ...prev, [item.id]: url }))
          } catch {
            // 网关鉴权失败时保留占位
          }
        }
      }
      await Promise.all(Array.from({ length: Math.min(4, queue.length) }, () => worker()))
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

  function report(text: string, ok: boolean) {
    setMessage(text)
    toastTask(text, ok)
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
      report(`已删除资源 ${id}`, true)
    } catch (error: unknown) {
      report(error instanceof ApiError ? error.message : '删除失败', false)
    }
  }

  async function downloadOne(item: Asset, usedNames: Map<string, number> = downloadUsedNames.current) {
    if (!item.objectKey) {
      report('缺少对象键，无法经网关下载', false)
      return
    }
    try {
      const blob = await apiFetchBlob(
        `/api/v1/realphotos/gateway/objects/${item.objectKey.split('/').map(encodeURIComponent).join('/')}`,
      )
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
      report(error instanceof ApiError ? error.message : '下载失败', false)
    }
  }

  async function downloadSelected() {
    const targets = items.filter((item) => selected[item.id])
    if (targets.length === 0) return
    const batchNames = new Map<string, number>()
    setDownloadProgress({ done: 0, total: targets.length })
    try {
      let done = 0
      for (const item of targets) {
        await downloadOne(item, batchNames)
        done += 1
        setDownloadProgress({ done, total: targets.length })
        setMessage(`正在下载 ${done}/${targets.length}…`)
      }
      setMessage(`批量下载完成 ${targets.length} 张`)
    } finally {
      setDownloadProgress(null)
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
      report(lockedCount ? '所选资源均已锁定，不能去处理' : '请先勾选 1–10 张资源', false)
      return
    }
    if (lockedCount > 0) {
      report(`已跳过 ${lockedCount} 张锁定图；去处理最多 10 张`, true)
    } else if (unlocked.length > 10) {
      report('去处理最多 10 张，已截取前 10 张', true)
    }
    router.push(`/realphotos/batch?assetIds=${ids.join(',')}`)
  }

  async function submitAppeal() {
    if (!appealTarget) return
    const text = appealText.trim()
    if (!text) {
      setAppealNote('请填写申诉原因')
      return
    }
    setAppealBusy(true)
    try {
      await apiFetch('/api/v1/realphotos/support-tickets', {
        method: 'POST',
        body: JSON.stringify({
          ticketType: 'image_appeal',
          reason: `资产 #${appealTarget.id}：${text}`,
        }),
      })
      setAppealTarget(null)
      setAppealText('')
      setAppealNote('')
      toastTask('申诉已提交', true)
    } catch (error: unknown) {
      setAppealNote(error instanceof ApiError ? error.message : '申诉提交失败')
    } finally {
      setAppealBusy(false)
    }
  }

  async function onLocalUpload(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return
    if (frozen) {
      report('账号已因预审冻结，不能上传新资源', false)
      return
    }
    const files = Array.from(fileList)
    if (files.length > UPLOAD_BATCH_MAX) {
      report(`单次最多上传 ${UPLOAD_BATCH_MAX} 张，整批已拒绝`, false)
      return
    }
    for (const file of files) {
      const inspected = await inspectLocalFile(file)
      if (!inspected.ok) {
        report(inspected.message, false)
        return
      }
    }
    try {
      // 2026-11-17：分批上传（每批 5 张），避免单次请求体超过网关体积限制触发 413。
      const UPLOAD_CHUNK = 5
      let uploaded = 0
      setUploadProgress({ done: 0, total: files.length })
      for (let start = 0; start < files.length; start += UPLOAD_CHUNK) {
        const chunk = files.slice(start, start + UPLOAD_CHUNK)
        const send = async () => {
          const body = new FormData()
          if (chunk.length === 1) {
            body.set('file', chunk[0])
            body.set('name', chunk[0].name)
            await apiFetch('/api/v1/realphotos/assets', { method: 'POST', body })
          } else {
            for (const file of chunk) {
              body.append('files', file)
              body.append('names', file.name)
            }
            await apiFetch('/api/v1/realphotos/assets/batch', { method: 'POST', body })
          }
        }
        // 弱网下大文件偶发连接中断，整批重试一次再判定失败。
        try {
          await send()
        } catch {
          await send()
        }
        uploaded += chunk.length
        setUploadProgress({ done: uploaded, total: files.length })
        setMessage(`正在上传 ${uploaded}/${files.length}…`)
      }
      report(`本地上传已入库 ${uploaded} 张`, true)
      setPage(1)
      await reload()
    } catch (error: unknown) {
      report(error instanceof ApiError ? error.message : '上传失败', false)
    } finally {
      setUploadProgress(null)
    }
  }

  return (
    <main className="space-y-6 p-6">
      <RpPageHeader title="图片资源" />
      <p className="text-sm">{message}</p>
      {uploadProgress ? (
        <p className="text-sm text-muted-foreground" role="status">
          上传中 {uploadProgress.done}/{uploadProgress.total} 张…
        </p>
      ) : null}
      {downloadProgress ? (
        <p className="text-sm text-muted-foreground" role="status">
          下载中 {downloadProgress.done}/{downloadProgress.total} 张…
        </p>
      ) : null}
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

      <section className="rp-card flex flex-wrap items-center gap-2 p-3 text-sm">
        <span className="rp-stat-label">添加图片</span>
        {frozen ? (
          <span className="rp-btn rp-btn-sm pointer-events-none opacity-50">URL 导入（已冻结）</span>
        ) : (
          <Link className="rp-btn rp-btn-sm" href="/realphotos/imports">
            URL 导入
          </Link>
        )}
        {frozen ? (
          <span className="rp-btn rp-btn-sm pointer-events-none opacity-50">本地上传（已冻结）</span>
        ) : (
          <button
            className="rp-btn rp-btn-sm"
            type="button"
            disabled={frozen || Boolean(uploadProgress)}
            onClick={() => fileInputRef.current?.click()}
          >
            {uploadProgress ? `上传中 ${uploadProgress.done}/${uploadProgress.total}` : '本地上传'}
          </button>
        )}
        {frozen ? (
          <span className="rp-btn rp-btn-sm pointer-events-none opacity-50">文生图（已冻结）</span>
        ) : (
          <Link className="rp-btn rp-btn-sm" href="/realphotos/generate?mode=text_to_image">
            文生图
          </Link>
        )}
        {frozen ? (
          <span className="rp-btn rp-btn-sm pointer-events-none opacity-50">图生图（已冻结）</span>
        ) : (
          <Link className="rp-btn rp-btn-sm" href="/realphotos/generate?mode=image_to_image">
            图生图
          </Link>
        )}
        <span className="mx-1 h-5 w-px bg-border" aria-hidden />
        <button className="rp-btn rp-btn-primary rp-btn-sm" type="button" onClick={() => goProcess()}>
          去处理（已选 {selectedIds.length}）
        </button>
        <button className="rp-btn rp-btn-sm" type="button" disabled={Boolean(downloadProgress)} onClick={() => void downloadSelected()}>
          {downloadProgress ? `下载中 ${downloadProgress.done}/${downloadProgress.total}` : '批量下载'}
        </button>
        <button className="rp-btn rp-btn-danger rp-btn-sm" type="button" onClick={() => void removeSelected()}>
          批量删除
        </button>
      </section>

      <section className="rp-card rp-filter flex flex-wrap items-center gap-3 p-3 text-sm">
        <label>
          搜索
          <input
            className="rp-input ml-2"
            value={search}
            placeholder="文件名 / 来源 / ID"
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label>
          来源
          <select
            className="rp-input ml-2"
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
            <option value="url_import">URL导入</option>
          </select>
        </label>
        <label>
          排序
          <select
            className="rp-input ml-2"
            value={sort}
            onChange={(event) => {
              setSort(event.target.value)
              setPage(1)
            }}
          >
            <option value="newest">最近上传</option>
            <option value="oldest">最早上传</option>
            <option value="largest">文件最大</option>
            <option value="smallest">文件最小</option>
          </select>
        </label>
        <button
          className="rp-btn rp-btn-sm"
          type="button"
          onClick={() => {
            setSort('newest')
            setOriginFilter('all')
            setPage(1)
          }}
        >
          最近上传
        </button>
        <span>
          第 {page} / {pageCount} 页 · 共 {total} 条 · 已选 {selectedIds.length} 张
        </span>
        <button
          className="rp-btn rp-btn-sm"
          type="button"
          disabled={page <= 1 || loading}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          上一页
        </button>
        <button
          className="rp-btn rp-btn-sm"
          type="button"
          disabled={page >= pageCount || loading}
          onClick={() => setPage((p) => p + 1)}
        >
          下一页
        </button>
      </section>
      <section className="rp-card">
      <RpTableScroll>
      <table className="rp-table">
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
          {loading ? (
            <RpSkeletonRows colSpan={8} />
          ) : visibleItems.length === 0 ? (
            <RpEmptyState
              colSpan={8}
              title="还没有图片"
              description="先从本地上传或 URL 导入开始；同一批最多 10 张可去处理。"
              action={
                <Link className="rp-btn rp-btn-primary rp-btn-sm" href="/realphotos/imports">
                  去导入图片
                </Link>
              }
            />
          ) : (
            visibleItems.map((item) => {
              const fileName = item.displayName || `${item.originKind}_${item.id}`
              return (
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
                      className="relative z-0 block h-14 w-14 rounded border hover:z-10"
                      title="点击查看大图"
                      onClick={() => void openPreview(item)}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={thumbs[item.id]}
                        alt=""
                        loading="lazy"
                        decoding="async"
                        className="h-14 w-14 object-cover transition-transform duration-150 hover:scale-125"
                      />
                    </button>
                  ) : (
                    <span className="inline-block h-14 w-14 border text-center leading-[3.5rem] text-xs">图</span>
                  )}
                </td>
                <td>
                  <span className="block max-w-[18rem] truncate" title={fileName}>
                    {truncateMiddle(fileName)}
                  </span>
                </td>
                <td>{originKindLabel(item.originKind)}</td>
                <td>{item.locked ? '已锁定' : '可用'}</td>
                <td>
                  {item.width}×{item.height}
                </td>
                <td>{formatByteSizeMb(item.byteSize)}</td>
                <td className="space-x-2 whitespace-nowrap">
                  {item.locked ? (
                    <button
                      className="rp-btn rp-btn-sm rp-btn-primary"
                      type="button"
                      onClick={() => {
                        setAppealTarget(item)
                        setAppealText('')
                        setAppealNote('')
                      }}
                    >
                      申诉
                    </button>
                  ) : null}
                  <button className="rp-btn rp-btn-sm" type="button" onClick={() => void downloadOne(item)}>
                    下载
                  </button>
                  <button className="rp-btn rp-btn-sm rp-btn-danger" type="button" onClick={() => void removeOne(item.id)}>
                    删除
                  </button>
                </td>
              </tr>
              )
            })
          )}
        </tbody>
      </table>
      </RpTableScroll>
      </section>
      {preview ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={() => {
            if (preview.fullUrl) URL.revokeObjectURL(preview.fullUrl)
            setPreview(null)
          }}
        >
          <button
            className="absolute right-4 top-4 rp-btn rp-btn-sm bg-white/90"
            type="button"
            onClick={(event) => {
              event.stopPropagation()
              if (preview.fullUrl) URL.revokeObjectURL(preview.fullUrl)
              setPreview(null)
            }}
          >
            关闭
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={preview.fullUrl || preview.url}
            alt={`资源 ${preview.id}`}
            className="max-h-[92vh] max-w-[92vw] rounded bg-white object-contain shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          />
          {preview.loading ? (
            <span className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded bg-black/60 px-3 py-1 text-xs text-white">
              正在加载大图…
            </span>
          ) : null}
        </div>
      ) : null}
      {appealTarget ? (
        <RpDialog
          title={`图片申诉 · ${appealTarget.displayName || appealTarget.id}`}
          label="图片申诉"
          closeOnBackdrop={false}
          onClose={() => setAppealTarget(null)}
        >
          <p className="text-xs text-muted-foreground">
            该图片已被锁定，申诉后由技术客服核实并决定是否解锁。
          </p>
          <textarea
            className="rp-input w-full"
            rows={3}
            placeholder="申诉原因"
            value={appealText}
            onChange={(e) => setAppealText(e.target.value)}
          />
          {appealNote ? <p className="text-xs text-destructive">{appealNote}</p> : null}
          <div className="flex justify-end gap-2">
            <button className="rp-btn rp-btn-sm" type="button" onClick={() => setAppealTarget(null)}>
              取消
            </button>
            <button
              className="rp-btn rp-btn-sm rp-btn-primary"
              type="button"
              disabled={appealBusy}
              onClick={() => void submitAppeal()}
            >
              {appealBusy ? '提交中…' : '提交申诉'}
            </button>
          </div>
        </RpDialog>
      ) : null}
    </main>
  )
}
