import type { ReactNode } from 'react'

import '@/components/realphotos/realphotos-surface.css'

export default function RealphotosLayout({ children }: { children: ReactNode }) {
  return <div className="realphotos-shell">{children}</div>
}
