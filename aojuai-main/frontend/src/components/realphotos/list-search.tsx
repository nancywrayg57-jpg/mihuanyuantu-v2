'use client'

type ListSearchProps = {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}

/** Shared keyword search for realphotos list / form pages. */
export function ListSearch({ value, onChange, placeholder = '关键词', className }: ListSearchProps) {
  return (
    <label className={className || 'inline-flex items-center gap-2 text-sm'}>
      <span>搜索</span>
      <input
        className="border px-2 py-1"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}

export function matchSearchText(query: string, ...parts: Array<string | number | null | undefined>) {
  const q = String(query || '').trim().toLowerCase()
  if (!q) return true
  return parts.some((part) => String(part ?? '').toLowerCase().includes(q))
}
