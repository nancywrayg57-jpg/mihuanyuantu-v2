/**
 * Format ops rate fields for display (BROWSER-E2E-FIX F5).
 * Backend opsMetrics rates are 0–1 fractions; do not double-scale if already percent-like.
 */
export function formatRate(value: number | null | undefined, emptyLabel = '暂无数据'): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return emptyLabel
  }
  const n = Number(value)
  // Contract: 0–1 fraction → percent. Values > 1 treated as already percent-ish (no ×100).
  const percent = n <= 1 ? n * 100 : n
  const rounded = Math.round(percent * 10) / 10
  const text = Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1)
  return `${text}%`
}
