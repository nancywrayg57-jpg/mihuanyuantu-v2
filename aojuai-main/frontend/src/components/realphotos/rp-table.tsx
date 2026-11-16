'use client'

import type { HTMLAttributes, ReactNode, TdHTMLAttributes, ThHTMLAttributes } from 'react'

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
}

export function RpDialog({ title, label, onClose, children }: RpDialogProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={label || title}
    >
      <div
        className={cn('rp-dialog max-h-[90vh] space-y-3 overflow-y-auto p-4 text-sm shadow', rpCardClass)}
        onClick={(event) => event.stopPropagation()}
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
