import type { HTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

import { rpCardClass } from './surface'

type RpCardProps = HTMLAttributes<HTMLElement> & {
  as?: 'section' | 'article' | 'div'
}

export function RpCard({ as = 'section', className, ...props }: RpCardProps) {
  const Tag = as
  return <Tag className={cn(rpCardClass, 'p-4', className)} {...props} />
}
