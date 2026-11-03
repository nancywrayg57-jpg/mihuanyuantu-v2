import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/**
 * 标准筛选网格：移动端 2 列（而不是 1 列全宽堆叠），桌面按宽度自动增列。
 * 跨整行的控件（如长搜索框/按钮组）可加 `col-span-2 md:col-span-1`。
 */
export function FilterGrid({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn('grid grid-cols-2 items-end gap-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6', className)}>
      {children}
    </div>
  )
}
