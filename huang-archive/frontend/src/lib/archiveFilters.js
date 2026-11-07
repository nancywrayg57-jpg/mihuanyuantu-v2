/** Client-side archive search & filters (works on loaded list). */

export function normalizeQuery(q) {
  return String(q || '')
    .normalize('NFC')
    .trim()
    .toLowerCase()
}

/** Extract comparable YYYYMMDD int from occurred_time (date or year). */
export function occurredKey(value) {
  const s = String(value || '').trim()
  const m = s.match(/(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?/)
  if (!m) return null
  const y = Number(m[1])
  const mo = Number(m[2] || 1)
  const d = Number(m[3] || 1)
  return y * 10000 + mo * 100 + d
}

export function matchArchive(archive, { q, person, dateFrom, dateTo, category } = {}) {
  if (!archive) return false
  if (category && category !== 'all' && archive.category !== category) return false

  const query = normalizeQuery(q)
  if (query) {
    const hay = [
      archive.title,
      archive.related_persons,
      archive.description,
      archive.uploader_name,
      archive.occurred_time,
      archive.external_link,
    ]
      .map((x) => String(x || '').toLowerCase())
      .join('\n')
    if (!hay.includes(query)) return false
  }

  const p = normalizeQuery(person)
  if (p) {
    const blob = `${archive.related_persons || ''} ${archive.uploader_name || ''} ${archive.title || ''}`.toLowerCase()
    if (!blob.includes(p)) return false
  }

  const key = occurredKey(archive.occurred_time)
  if (dateFrom) {
    const from = occurredKey(dateFrom)
    if (from != null && key != null && key < from) return false
  }
  if (dateTo) {
    const to = occurredKey(dateTo)
    if (to != null && key != null && key > to) return false
  }
  return true
}

export function filterArchives(list, opts) {
  return (list || []).filter((a) => matchArchive(a, opts))
}
