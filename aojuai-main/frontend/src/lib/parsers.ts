export function parseIdList(raw: string) {
  const items = raw
    .split(/[\s,]+/g)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => Number(s))
    .filter((n) => Number.isInteger(n) && n > 0)
  return Array.from(new Set(items))
}

