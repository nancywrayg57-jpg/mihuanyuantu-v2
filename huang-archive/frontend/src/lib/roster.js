/** Family login roster: Chinese display names map to PocketBase identity (email). */
export const FAMILY_ROSTER = [
  { display_name: '黄祥财', email: 'huangxiangcai@huangzhisong.com', role: 'admin' },
  { display_name: '黄纲生', email: 'user1@huangzhisong.com', role: 'member' },
  { display_name: '黄成生', email: 'user2@huangzhisong.com', role: 'member' },
  { display_name: '黄爱眉', email: 'user3@huangzhisong.com', role: 'member' },
  { display_name: '张银财', email: 'user4@huangzhisong.com', role: 'member' },
  { display_name: '黄爱秀', email: 'user5@huangzhisong.com', role: 'member' },
  { display_name: '吴雨齐', email: 'user6@huangzhisong.com', role: 'member' },
  { display_name: '黄纲富', email: 'user7@huangzhisong.com', role: 'member' },
  { display_name: '黄纲兴', email: 'user8@huangzhisong.com', role: 'member' },
  { display_name: '黄纲财', email: 'user9@huangzhisong.com', role: 'member' },
  { display_name: '黄纲平', email: 'user10@huangzhisong.com', role: 'member' },
  { display_name: '黄祥贵', email: 'user11@huangzhisong.com', role: 'member' },
  { display_name: '黄祥文', email: 'user12@huangzhisong.com', role: 'member' },
  { display_name: '黄祥明', email: 'user13@huangzhisong.com', role: 'member' },
  { display_name: '黄祥健', email: 'user14@huangzhisong.com', role: 'member' },
  { display_name: '黄祥鑫', email: 'user15@huangzhisong.com', role: 'member' },
  { display_name: '黄祥琳', email: 'user16@huangzhisong.com', role: 'member' },
  { display_name: '黄祥瑞', email: 'user17@huangzhisong.com', role: 'member' },
  { display_name: '张惠', email: 'user18@huangzhisong.com', role: 'member' },
  { display_name: '吴玲玲', email: 'user19@huangzhisong.com', role: 'member' },
  { display_name: '黄祥伟', email: 'user20@huangzhisong.com', role: 'member' },
  { display_name: '黄祥妹', email: 'user21@huangzhisong.com', role: 'member' },
  { display_name: '黄媛媛', email: 'user22@huangzhisong.com', role: 'member' },
  { display_name: '黄晓芳', email: 'user23@huangzhisong.com', role: 'member' },
  { display_name: '黄嘉颖', email: 'user24@huangzhisong.com', role: 'member' },
  { display_name: '张建华', email: 'user25@huangzhisong.com', role: 'member' },
  { display_name: '吴泽强', email: 'user26@huangzhisong.com', role: 'member' },
]

/** Upload CTA by kinship group (display_name → label). */
const UPLOAD_FATHER = new Set([
  '黄纲生', '黄成生', '黄爱眉', '黄爱秀', '黄纲富', '黄纲兴', '黄纲财', '黄纲平',
])
const UPLOAD_FATHER_IN_LAW = new Set(['张银财', '吴雨齐'])
const UPLOAD_GRANDFATHER = new Set([
  '黄祥财', '黄祥贵', '黄祥文', '黄祥明', '黄祥健', '黄祥鑫', '黄祥琳', '黄祥瑞',
  '黄祥伟', '黄祥妹', '黄媛媛', '黄晓芳', '黄嘉颖',
])
const UPLOAD_MATERNAL_GRANDFATHER = new Set(['张惠', '张建华', '吴玲玲', '吴泽强'])

export function uploadLabelFor(displayName) {
  const name = String(displayName || '').trim()
  if (UPLOAD_FATHER.has(name)) return '上传父亲的资料'
  if (UPLOAD_FATHER_IN_LAW.has(name)) return '上传岳父的资料'
  if (UPLOAD_GRANDFATHER.has(name)) return '上传爷爷的资料'
  if (UPLOAD_MATERNAL_GRANDFATHER.has(name)) return '上传外公的资料'
  return '上传资料'
}

export function resolveIdentity(nameOrEmail) {
  const raw = String(nameOrEmail || '').trim()
  if (!raw) return null
  const byName = FAMILY_ROSTER.find((p) => p.display_name === raw)
  if (byName) return byName
  const byEmail = FAMILY_ROSTER.find((p) => p.email === raw)
  if (byEmail) return byEmail
  return { display_name: raw, email: raw.includes('@') ? raw : null, role: null }
}

export const CATEGORY_TABS = [
  { key: 'all', label: '全部珍藏' },
  { key: 'image', label: '图片' },
  { key: 'video', label: '视频' },
  { key: 'scan', label: '扫描件' },
  { key: 'link', label: '新闻链接' },
  { key: 'audio', label: '录音' },
  { key: 'other', label: '其他' },
]
