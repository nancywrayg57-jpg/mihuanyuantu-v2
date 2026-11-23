/** Kinship enum for family members (relative to 黄志松). */
export const RELATION_OPTIONS = [
  '儿子',
  '女儿',
  '儿媳',
  '女婿',
  '孙子',
  '孙女',
  '孙女婿',
  '孙媳',
  '外甥',
  '外甥女',
  '外甥女婿',
  '外甥媳',
  '侄儿',
  '侄女',
  '侄孙',
  '侄孙媳',
  '侄外甥',
  '侄外甥媳',
  '曾孙',
  '曾孙女',
  '曾外孙',
  '曾外甥女',
  '学生',
  '晚辈',
]

/** Upload CTA from relation enum (with name-based fallback for legacy). */
export function uploadLabelFromRelation(relation, displayName = '') {
  const r = String(relation || '').trim()
  if (['儿子', '女儿'].includes(r)) return '上传父亲的资料'
  if (['儿媳', '女婿'].includes(r)) return '上传岳父的资料'
  if (
    ['孙子', '孙女', '孙女婿', '孙媳', '曾孙', '曾孙女', '侄孙', '侄孙媳'].includes(r)
  ) {
    return '上传爷爷的资料'
  }
  if (
    [
      '外甥',
      '外甥女',
      '外甥女婿',
      '外甥媳',
      '曾外孙',
      '曾外甥女',
      '侄外甥',
      '侄外甥媳',
    ].includes(r)
  ) {
    return '上传外公的资料'
  }
  if (['侄儿', '侄女'].includes(r)) return '上传伯父的资料'
  if (['学生', '晚辈'].includes(r)) return '上传资料'
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
