import pb from './pb'

/** Build a JSON export of archives (+ memory counts) for backup download. */
export async function buildArchiveExport() {
  const archives = await pb.collection('archives').getFullList({ sort: '-created' })
  const memories = await pb.collection('memories').getFullList({ sort: '-created' }).catch(() => [])
  const likes = await pb.collection('archive_likes').getFullList().catch(() => [])
  return {
    exported_at: new Date().toISOString(),
    service: 'huang-archive',
    counts: {
      archives: archives.length,
      memories: memories.length,
      likes: likes.length,
    },
    archives,
    memories,
    likes,
  }
}

export function downloadJson(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
