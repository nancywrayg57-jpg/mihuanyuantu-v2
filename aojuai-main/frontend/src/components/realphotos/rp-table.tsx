'use client'

import type { HTMLAttributes, ReactNode, ThHTMLAttributes } from 'react'
import { useEffect, useRef } from 'react'

import { cn } from '@/lib/utils'

import { RpButton } from './rp-button'
import { rpCardClass, rpEmptyClass, rpFilterClass, rpTableClass } from './surface'

export function RpFilterBar({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn(rpFilterClass, className)} {...props} />
}

export function RpTable({ className, ...props }: HTMLAttributes<HTMLTableElement>) {
  return <table className={cn(rpTableClass, className)} {...props} />
}

export function RpTh({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={cn('text-left', className)} {...props} />
}

export function RpEmpty({ colSpan, children }: { colSpan: number; children: ReactNode }) {
  return (
    <tr>
      <td className={rpEmptyClass} colSpan={colSpan}>
        {children}
      </td>
    </tr>
  )
}

/** 2026-11-18 UX-P2-2：带主行动的空态。 */
export function RpEmptyState({
  colSpan,
  title,
  description,
  action,
}: {
  colSpan: number
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <tr>
      <td className={rpEmptyClass} colSpan={colSpan}>
        <div className="space-y-1">
          <div className="font-medium text-foreground">{title}</div>
          {description ? <div className="text-xs text-muted-foreground">{description}</div> : null}
          {action ? <div className="pt-1">{action}</div> : null}
        </div>
      </td>
    </tr>
  )
}

/** 2026-11-18 UX-P2-1：小屏横向滚动 + 右侧阴影/滑动提示。 */
export function RpTableScroll({
  children,
  hint = '左右滑动查看完整列',
}: {
  children: ReactNode
  hint?: string
}) {
  return (
    <div className="rp-table-scroll relative">
      <div className="overflow-x-auto [&_table]:min-w-[720px]">{children}</div>
      <div
        className="pointer-events-none absolute inset-y-0 right-0 w-6 bg-gradient-to-l from-background/90 to-transparent sm:hidden"
        aria-hidden
      />
      <p className="mt-1 text-[11px] text-muted-foreground sm:hidden">{hint}</p>
    </div>
  )
}

/** 2026-11-18 UX-P2-5：列表加载骨架。 */
export function RpSkeletonRows({ colSpan, rows = 5 }: { colSpan: number; rows?: number }) {
  return (
    <>
      {Array.from({ length: rows }, (_, index) => (
        <tr key={`skeleton-${index}`} aria-hidden>
          <td colSpan={colSpan} className="px-2 py-2">
            <div className="h-4 animate-pulse rounded bg-muted" />
          </td>
        </tr>
      ))}
    </>
  )
}

type RpPaginationProps = {
  page: number
  pageCount: number
  total?: number
  extra?: ReactNode
  onPrev: () => void
  onNext: () => void
}

export function RpPagination({ page, pageCount, total, extra, onPrev, onNext }: RpPaginationProps) {
  return (
    <div className="rp-pager flex flex-wrap items-center gap-2 text-sm">
      <span>
        第 {page} / {pageCount} 页{total != null ? ` · 共 ${total}` : ''}
        {extra ? ` · ${extra}` : ''}
      </span>
      <RpButton size="sm" disabled={page <= 1} onClick={onPrev}>
        上一页
      </RpButton>
      <RpButton size="sm" disabled={page >= pageCount} onClick={onNext}>
        下一页
      </RpButton>
    </div>
  )
}

type RpDialogProps = {
  title: string
  label?: string
  onClose: () => void
  children: ReactNode
  /** 表单类弹窗可设为 false，避免误点遮罩丢失输入。Esc 仍可关闭。 */
  closeOnBackdrop?: boolean
}

const FOCUSABLE =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])'

export function RpDialog({
  title,
  label,
  onClose,
  children,
  closeOnBackdrop = true,
}: RpDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const closeRef = useRef(onClose)

  useEffect(() => {
    closeRef.current = onClose
  }, [onClose])

  // 2026-11-18 UX-P2-4：初始焦点、Tab 焦点陷阱、Esc 关闭、关闭后恢复焦点。
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const node = dialogRef.current
    const initial = node?.querySelector<HTMLElement>(FOCUSABLE)
    initial?.focus()

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeRef.current()
        return
      }
      if (event.key !== 'Tab' || !node) return
      const items = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (item) => item.offsetParent !== null,
      )
      if (items.length === 0) {
        event.preventDefault()
        node.focus()
        return
      }
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      previous?.focus?.()
    }
  }, [])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={() => {
        if (closeOnBackdrop) onClose()
      }}
      role="presentation"
    >
      <div
        ref={dialogRef}
        className={cn('rp-dialog max-h-[90vh] space-y-3 overflow-y-auto p-4 text-sm shadow', rpCardClass)}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={label || title}
        tabIndex={-1}
      >
        <div className="flex items-center justify-between gap-2">
          <strong className="text-base">{title}</strong>
          <RpButton size="sm" onClick={onClose}>
            关闭
          </RpButton>
        </div>
        {children}
      </div>
    </div>
  )
}

export function RpStatus({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: 'neutral' | 'ok' | 'bad' | 'warn'
}) {
  return (
    <span className="rp-pill" data-tone={tone === 'neutral' ? undefined : tone}>
      {children}
    </span>
  )
}
