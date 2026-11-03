'use client'

import type { ReactNode } from 'react'
import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useT } from '@/lib/i18n'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { cn } from '@/lib/utils'

export function CollapsibleFilters({
  title = '',
  className,
  children,
  defaultExpanded = false,
}: {
  title?: ReactNode
  className?: string
  children: ReactNode
  defaultExpanded?: boolean
}) {
  const isMobile = useIsMobile()
  const t = useT()
  // 移动端永远默认折叠（defaultExpanded 仅语义保留）：保住首屏核心内容占比
  const [expanded, setExpanded] = useState(false)
  void defaultExpanded
  const body = <div className="aoju-filter-body min-w-0">{children}</div>

  if (!isMobile) {
    return <div className={cn('aoju-filter-panel min-w-0', className)}>{body}</div>
  }

  return (
    <div className={cn('aoju-filter-panel min-w-0 space-y-2', className)}>
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-medium">{title || t('common.filters')}</div>
        <Button variant="outline" size="sm" onClick={() => setExpanded((v) => !v)}>
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          <span className="ml-1">{expanded ? t('common.collapseFilters') : t('common.expandFilters')}</span>
        </Button>
      </div>
      {expanded ? body : null}
    </div>
  )
}
