import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export function PageHeader({
  title,
  description,
  actions,
  icon,
  className,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  /** 页面身份图标：渲染为主题色 chip，让页头不再"素" */
  icon?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-col gap-1.5 md:flex-row md:items-start md:justify-between md:gap-3', className)}>
      <div className="flex min-w-0 flex-1 items-start gap-2.5">
        {icon ? (
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            {icon}
          </span>
        ) : null}
        <div className="min-w-0 flex-1">
        <div className="break-words text-base font-semibold leading-6 md:text-lg">{title}</div>
        {description ? (
          // 移动端单行截断保住首屏；桌面完整展示
          <div className="mt-0.5 line-clamp-1 break-words text-xs leading-5 text-muted-foreground md:line-clamp-none md:text-sm" title={typeof description === 'string' ? description : undefined}>
            {description}
          </div>
        ) : null}
        </div>
      </div>
      {actions ? <div className="flex w-full flex-wrap items-center gap-1.5 md:w-auto md:justify-end">{actions}</div> : null}
    </div>
  )
}
