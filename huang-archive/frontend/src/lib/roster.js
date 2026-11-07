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
]

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
