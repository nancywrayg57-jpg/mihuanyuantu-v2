/** Kinship enum for family members (relative to 黄志松). */
export const RELATION_OPTIONS = [
  '儿子',
  '女儿',
  '儿媳',
  '女婿',
  '外甥',
  '外甥女',
  '曾孙',
  '曾孙女',
  '曾外孙',
  '曾外甥女',
]

/** Upload CTA from relation enum (with name-based fallback for legacy). */
export function uploadLabelFromRelation(relation, displayName = '') {
  const r = String(relation || '').trim()
  if (['儿子', '女儿'].includes(r)) return '上传父亲的资料'
  if (['儿媳', '女婿'].includes(r)) return '上传岳父的资料'
  if (['曾孙', '曾孙女'].includes(r)) return '上传爷爷的资料'
  if (['外甥', '外甥女', '曾外孙', '曾外甥女'].includes(r)) return '上传外公的资料'
  // legacy name groups
  return null
}

export function genMemberIdentity(displayName) {
  const stamp = Date.now().toString(36)
  const rand = Math.random().toString(36).slice(2, 8)
  return {
    email: `m${stamp}${rand}@huangzhisong.com`,
    username: `u${stamp}${rand}`,
  }
}
