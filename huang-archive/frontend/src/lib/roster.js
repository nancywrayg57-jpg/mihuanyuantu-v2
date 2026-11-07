import { uploadLabelFromRelation } from './relations'

/** Family login roster: Chinese display names map to PocketBase identity (email/username). */
export const FAMILY_ROSTER = [
  { display_name: '黄祥财', email: 'huangxiangcai@huangzhisong.com', username: 'huangxiangcai', role: 'admin' },
  { display_name: '黄纲生', email: 'user1@huangzhisong.com', username: 'huanggangsheng', role: 'member' },
  { display_name: '黄成生', email: 'user2@huangzhisong.com', username: 'huangchengsheng', role: 'member' },
  { display_name: '黄爱眉', email: 'user3@huangzhisong.com', username: 'huangaimei', role: 'member' },
  { display_name: '张银财', email: 'user4@huangzhisong.com', username: 'zhangyincai', role: 'member' },
  { display_name: '黄爱秀', email: 'user5@huangzhisong.com', username: 'huangaixiu', role: 'member' },
  { display_name: '吴雨齐', email: 'user6@huangzhisong.com', username: 'wuyuqi', role: 'member' },
  { display_name: '黄纲富', email: 'user7@huangzhisong.com', username: 'huanggangfu', role: 'member' },
  { display_name: '黄纲兴', email: 'user8@huangzhisong.com', username: 'huanggangxing', role: 'member' },
  { display_name: '黄纲财', email: 'user9@huangzhisong.com', username: 'huanggangcai', role: 'member' },
  { display_name: '黄纲平', email: 'user10@huangzhisong.com', username: 'huanggangping', role: 'member' },
  { display_name: '黄祥贵', email: 'user11@huangzhisong.com', username: 'huangxianggui', role: 'member' },
  { display_name: '黄祥文', email: 'user12@huangzhisong.com', username: 'huangxiangwen', role: 'member' },
  { display_name: '黄祥明', email: 'user13@huangzhisong.com', username: 'huangxiangming', role: 'member' },
  { display_name: '黄祥健', email: 'user14@huangzhisong.com', username: 'huangxiangjian', role: 'member' },
  { display_name: '黄祥鑫', email: 'user15@huangzhisong.com', username: 'huangxiangxin', role: 'member' },
  { display_name: '黄祥琳', email: 'user16@huangzhisong.com', username: 'huangxianglin', role: 'member' },
  { display_name: '黄祥瑞', email: 'user17@huangzhisong.com', username: 'huangxiangrui', role: 'member' },
  { display_name: '张惠', email: 'user18@huangzhisong.com', username: 'zhanghui', role: 'member' },
  { display_name: '吴玲玲', email: 'user19@huangzhisong.com', username: 'wulingling', role: 'member' },
  { display_name: '黄祥伟', email: 'user20@huangzhisong.com', username: 'huangxiangwei', role: 'member' },
  { display_name: '黄祥妹', email: 'user21@huangzhisong.com', username: 'huangxiangmei', role: 'member' },
  { display_name: '黄媛媛', email: 'user22@huangzhisong.com', username: 'huangyuanyuan', role: 'member' },
  { display_name: '黄晓芳', email: 'user23@huangzhisong.com', username: 'huangxiaofang', role: 'member' },
  { display_name: '黄嘉颖', email: 'user24@huangzhisong.com', username: 'huangjiaying', role: 'member' },
  { display_name: '张建华', email: 'user25@huangzhisong.com', username: 'zhangjianhua', role: 'member' },
  { display_name: '吴泽强', email: 'user26@huangzhisong.com', username: 'wuzeqiang', role: 'member' },
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

export function uploadLabelFor(displayName, relation = '') {
  const fromRel = uploadLabelFromRelation(relation, displayName)
  if (fromRel) return fromRel
  const name = normalizePersonName(displayName)
  if (UPLOAD_FATHER.has(name)) return '上传父亲的资料'
  if (UPLOAD_FATHER_IN_LAW.has(name)) return '上传岳父的资料'
  if (UPLOAD_GRANDFATHER.has(name)) return '上传爷爷的资料'
  if (UPLOAD_MATERNAL_GRANDFATHER.has(name)) return '上传外公的资料'
  return '上传资料'
}

/** Trim + NFC; strip zero-width chars that IMEs sometimes insert. */
export function normalizePersonName(value) {
  return String(value || '')
    .normalize('NFC')
    .replace(/[\u200B-\u200D\uFEFF]/g, '')
    .replace(/\s+/g, '')
    .trim()
}

/** Convert fullwidth ASCII (common on CN phone IMEs) to halfwidth. */
export function normalizePassword(value) {
  return String(value || '')
    .normalize('NFKC')
    .replace(/[\u200B-\u200D\uFEFF]/g, '')
    .trim()
}

export function resolveIdentity(nameOrEmail) {
  const raw = normalizePersonName(nameOrEmail)
  if (!raw) return null
  const byName = FAMILY_ROSTER.find((p) => p.display_name === raw)
  if (byName) return byName
  const byEmail = FAMILY_ROSTER.find((p) => p.email === raw)
  if (byEmail) return byEmail
  const byUser = FAMILY_ROSTER.find((p) => p.username === raw)
  if (byUser) return byUser
  return { display_name: raw, email: raw.includes('@') ? raw : null, username: raw.includes('@') ? null : raw, role: null }
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
