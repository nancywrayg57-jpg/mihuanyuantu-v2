import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

type RpFieldProps = {
  label: ReactNode
  children: ReactNode
  className?: string
}

export function RpField({ label, children, className }: RpFieldProps) {
  return (
    <label className={cn('rp-field inline-flex items-center gap-2 text-sm', className)}>
      <span className="shrink-0 text-muted-foreground">{label}</span>
      {children}
    </label>
  )
}
