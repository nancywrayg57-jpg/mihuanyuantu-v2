import type { ReactNode } from 'react'

type RpPageHeaderProps = {
  title: string
  description?: ReactNode
  actions?: ReactNode
}

export function RpPageHeader({ title, description, actions }: RpPageHeaderProps) {
  return (
    <header className="rp-page-header flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1>{title}</h1>
        {description ? <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  )
}
