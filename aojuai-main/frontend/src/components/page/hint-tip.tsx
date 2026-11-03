'use client'

import type { ReactNode } from 'react'
import { useState } from 'react'
import { HelpCircle } from 'lucide-react'

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/**
 * 标题旁的说明浮层：替代标题下的小字说明段。
 * 桌面 hover 即显，移动端点按切换；基于 Popover，无额外依赖。
 *
 * 用法：<CardTitle>Skill <HintTip content="工作方法、提示词规则…" /></CardTitle>
 */
export function HintTip({ content, className }: { content: ReactNode; className?: string }) {
  const t = useT()
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={t('system.common.viewDescription')}
          className={cn(
            'inline-flex h-4 w-4 shrink-0 items-center justify-center align-middle text-muted-foreground/60 transition-colors hover:text-foreground',
            className,
          )}
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
          onClick={() => setOpen((v) => !v)}
        >
          <HelpCircle className="h-3.5 w-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        side="top"
        align="start"
        className="w-auto max-w-[min(18rem,calc(100vw-2rem))] p-2.5 text-xs leading-5 text-muted-foreground"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        {content}
      </PopoverContent>
    </Popover>
  )
}
