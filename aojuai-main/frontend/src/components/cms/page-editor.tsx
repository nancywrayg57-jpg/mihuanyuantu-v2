'use client'

import '@measured/puck/puck.css'

import { Puck } from '@measured/puck'
import type { Data } from '@measured/puck'
import { X } from 'lucide-react'

import { puckConfig } from '@/components/cms/puck-config'

const EMPTY: Data = { content: [], root: { props: {} }, zones: {} } as Data

function normalize(data: unknown): Data {
  const d = (data || {}) as Partial<Data>
  if (!Array.isArray((d as { content?: unknown }).content)) return EMPTY
  return { content: d.content || [], root: d.root || { props: {} }, zones: d.zones || {} } as Data
}

/**
 * Full-screen Puck editor. We use Puck's own header (it fills 100dvh exactly,
 * so the fields panel scrolls within the viewport — no bottom overflow) and add
 * a Close action via overrides.headerActions.
 */
export function PageEditor({
  title,
  initialData,
  onSave,
  onClose,
}: {
  title: string
  initialData: unknown
  onSave: (data: Data) => void
  onClose: () => void
}) {
  return (
    <div className="cms-puck-editor fixed inset-0 z-50 bg-background">
      <Puck
        config={puckConfig}
        data={normalize(initialData)}
        onPublish={(data) => onSave(data)}
        headerTitle={title}
        overrides={{
          headerActions: ({ children }: { children?: React.ReactNode }) => (
            <>
              {children}
              <button
                type="button"
                onClick={onClose}
                className="ml-2 inline-flex h-9 items-center gap-1 rounded-md border border-border/60 px-3 text-sm hover:bg-muted"
              >
                <X className="h-4 w-4" /> 退出
              </button>
            </>
          ),
        }}
      />
    </div>
  )
}

export default PageEditor
