'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'

import { ApiError, apiFetch, apiFetchBlob } from '@/lib/api'
import { originKindLabel } from '@/lib/realphotos-labels'
import { inspectLocalFile } from '@/lib/realphotos-s1'

type Asset = {
  id: string
  originKind: string
  width: number
  height: number
  byteSize: number
  objectKey?: string
  displayName?: string
  downloadBasename?: string
  degraded?: boolean
  requestedWidth?: number | null
  requestedHeight?: number | null
  actualWidth?: number
  actualHeight?: number
}

const PAGE_SIZE = 20

export default function RealphotosLibraryPage() {
  const router = useRouter()
  const [items, setItems] = useState<Asset[]>([])
  const [message, setMessage] = useState('')
  const [originFilter, setOriginFilter] = useState('all')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Record<string, true>>({})
  const [thumbs, setThumbs] = useState<Record<string, string>>({})
  const [preview, setPreview] = useState<{ id: string; url: string } | null>(null)

  async function reload() {
    const data = await apiFetch<{ items: Asset[] }>('/api/v1/realphotos/assets')
    setItems(data.items || [])
  }

  useEffect(() => {
    void reload().catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '资源加载失败'))
  }, [])

  useEffect(() => {
    let cancelled = false
    const created: string[] = []
    async function loadThumbs() {
      // Progressive updates: waiting for all 60 (incl. multi-MB generation PNGs)
      // before setState left the column stuck on 「图」 even when the gateway was healthy (F8).
      setThumbs({})
      for (const item of items.slice(0, 60)) {
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

  const filtered = useMemo(() => {
    if (originFilter === 'all') return items
    return items.filter((item) => item.originKind === originFilter)
  }, [items, originFilter])

  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const selectedIds = Object.keys(selected)

  function toggle(id: string) {
    setSelected((prev) => {
      const next = { ...prev }
      if (next[id]) delete next[id]
      else next[id] = true
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

  async function downloadOne(item: Asset) {
    if (!item.objectKey) {
      setMessage('缺少对象键，无法经网关下载')
      return
    }
    try {
      const blob = await apiFetchBlob(`/api/v1/realphotos/gateway/objects/${item.objectKey}`)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${item.downloadBasename || item.displayName || `${item.originKind}_${item.id}`}.jpg`
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '下载失败')
    }
  }

  async function downloadSelected() {
    const targets = items.filter((item) => selected[item.id])
    for (const item of targets) {
      await downloadOne(item)
    }
  }

  async function removeSelected() {
    for (const id of selectedIds) {
      await removeOne(id)
    }
  }

  function goProcess() {
    const ids = selectedIds.slice(0, 10)
    if (!ids.length) {
      setMessage('请先勾选 1–10 张资源')
      return
    }
    if (selectedIds.length > 10) {
      setMessage('去处理最多 10 张，已截取前 10 张')
    }
    router.push(`/realphotos/batch?assetIds=${ids.join(',')}`)
  }

  async function onLocalUpload(file: File | null) {
    if (!file) return
    const inspected = await inspectLocalFile(file)
    if (!inspected.ok) {
      setMessage(inspected.message)
      return
    }
    const body = new FormData()
    body.set('file', file)
    try {
      await apiFetch('/api/v1/realphotos/assets', { method: 'POST', body })
      setMessage('本地上传已入库，未创建处理任务')
      await reload()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '上传失败')
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">图片资源</h1>
      <p className="text-sm text-muted-foreground">统一入口。四入口进入添加；列表为表格，不是卡片网格。</p>
      <p className="text-sm">{message}</p>
      <section className="flex flex-wrap gap-2 text-sm">
        <span className="font-medium">添加图片：</span>
        <Link className="border px-2 py-1" href="/realphotos/generate?mode=text_to_image">
          文生图
        </Link>
        <Link className="border px-2 py-1" href="/realphotos/generate?mode=image_to_image">
          图生图
        </Link>
        <a className="border px-2 py-1" href="#local-upload">
          本地上传
        </a>
        <Link className="border px-2 py-1" href="/realphotos/imports">
          URL 导入
        </Link>
        <button className="border px-2 py-1" type="button" onClick={() => goProcess()}>
          去处理（已选 {selectedIds.length}）
        </button>
        <span className="text-xs text-muted-foreground">
          单张/批量均进入处理页；GPS 不可用将拦截，缺坐标会提示跳过写入
        </span>
        <button className="border px-2 py-1" type="button" onClick={() => void downloadSelected()}>
          批量下载
        </button>
        <button className="border px-2 py-1" type="button" onClick={() => void removeSelected()}>
          批量删除
        </button>
      </section>
      <section id="local-upload" className="space-y-2 text-sm">
        <p>本地上传（仅入库，不自动处理）</p>
        <label className="inline-flex cursor-pointer items-center border px-3 py-1">
          选择文件
          <input
            className="sr-only"
            type="file"
            accept="image/jpeg,image/png,.jpg,.jpeg,.png"
            onChange={(event) => void onLocalUpload(event.target.files?.[0] || null)}
          />
        </label>
      </section>
      <section className="flex flex-wrap items-center gap-3 text-sm">
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
          第 {page} / {pageCount} 页 · 默认 20 条 · 跨筛选勾选保留 {selectedIds.length} 张
        </span>
        <button className="border px-2 py-1" type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
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
            <th className="text-left">勾选</th>
            <th className="text-left">缩略图</th>
            <th className="text-left">拼接文件名</th>
            <th className="text-left">来源</th>
            <th className="text-left">尺寸</th>
            <th className="text-left">字节</th>
            <th className="text-left">操作</th>
          </tr>
        </thead>
        <tbody>
          {pageItems.length === 0 ? (
            <tr>
              <td colSpan={7}>暂无资源</td>
            </tr>
          ) : (
            pageItems.map((item) => (
              <tr key={item.id}>
                <td>
                  <input type="checkbox" checked={Boolean(selected[item.id])} onChange={() => toggle(item.id)} />
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
                  {item.degraded ? '（降级）' : ''}
                  {item.requestedWidth && item.actualWidth && item.requestedWidth !== item.actualWidth
                    ? ` · 请求${item.requestedWidth}×${item.requestedHeight} / 实际${item.actualWidth}×${item.actualHeight}`
                    : ''}
                </td>
                <td>{originKindLabel(item.originKind)}</td>
                <td>
                  {item.width}×{item.height}
                </td>
                <td>{item.byteSize}</td>
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
      <p className="text-xs text-muted-foreground">
        元数据字段未齐时文件名按「来源_尺寸_id」降级显示。缩略图经鉴权网关读取，不暴露 LocalDisk 裸路径。运行中资源删除会被后端拒绝。
      </p>
    </main>
  )
}
