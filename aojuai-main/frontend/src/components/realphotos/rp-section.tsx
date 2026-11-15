import type { ReactNode } from 'react'

export type RpSectionTone =
  | 'basic'
  | 'credit'
  | 'failure'
  | 'gps'
  | 'report'
  | 'preview'
  | 'items'
  | 'billing'

type RpSectionProps = {
  title: string
  tone?: RpSectionTone
  children: ReactNode
}

/** Report block: title bar + bordered body. Tones stay on aojuai tokens. */
export function RpSection({ title, tone = 'basic', children }: RpSectionProps) {
  return (
    <section className="rp-section" data-tone={tone} data-module={title}>
      <h3 className="rp-section-head">{title}</h3>
      <div className="rp-section-body">{children}</div>
    </section>
  )
}
