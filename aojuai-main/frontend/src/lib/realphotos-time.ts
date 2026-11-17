/**
 * 2026-11-17：全站时间展示统一简化为「年-月-日 时:分」（本地时区）。
 * 传入 ISO 字符串（后端返回 UTC 或带偏移），无效输入原样返回，空值返回 ''。
 */
export function formatDateTimeShort(value?: string | null): string {
  const raw = String(value ?? '').trim()
  if (!raw) return ''
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

/** 只到日：年-月-日。 */
export function formatDateShort(value?: string | null): string {
  const full = formatDateTimeShort(value)
  return full ? full.slice(0, 10) : ''
}
