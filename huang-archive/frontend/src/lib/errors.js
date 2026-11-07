/** Map PocketBase / network errors to Simplified Chinese for UI. */

const PHRASES = [
  [/failed to authenticate/i, '登录失败：姓名或密码不正确'],
  [/invalid login/i, '登录失败：姓名或密码不正确'],
  [/missing or invalid authentication header/i, '登录已失效，请重新登录'],
  [/authorization/i, '登录已失效，请重新登录'],
  [/wasn't found|was not found|not found/i, '未找到相关记录'],
  [/already exists|unique constraint/i, '记录已存在，请勿重复操作'],
  [/failed to create/i, '创建失败，请检查填写内容'],
  [/failed to update/i, '保存失败，请稍后重试'],
  [/failed to delete/i, '删除失败，请稍后重试'],
  [/validation|invalid|out of range|required/i, '提交内容不符合要求，请检查后重试'],
  [/file type|max file|file size|mime|不能超过/i, '文件不符合要求（格式或大小）'],
  [/failed to upload|upload/i, '上传失败，请检查网络与文件后重试'],
  [/forbidden|not allowed|only superusers|403/i, '没有权限执行此操作'],
  [/network|failed to fetch|load failed|timeout/i, '网络异常，请检查网络后重试'],
  [/something went wrong/i, '操作失败，请稍后重试'],
]

export function zhError(err, fallback = '操作失败，请稍后重试') {
  if (!err) return fallback
  if (typeof err === 'string') return translate(err) || fallback

  const data = err?.data || err?.response?.data || {}
  const fieldMsgs = []
  if (data?.data && typeof data.data === 'object') {
    for (const [k, v] of Object.entries(data.data)) {
      const m = v?.message || v
      if (typeof m === 'string') fieldMsgs.push(`${fieldLabel(k)}：${translate(m) || '内容不符合要求'}`)
    }
  }

  const raw = err?.message || data?.message || String(err)
  if (fieldMsgs.length) return fieldMsgs.join('；')
  return translate(raw) || fallback
}

function fieldLabel(key) {
  const map = {
    title: '标题',
    occurred_time: '发生时间',
    related_persons: '关系人',
    description: '说明',
    password: '密码',
    passwordConfirm: '确认密码',
    oldPassword: '当前密码',
    identity: '姓名',
    media_files: '文件',
    external_link: '链接',
    category: '分类',
  }
  return map[key] || key
}

function translate(text) {
  const s = String(text || '').trim()
  if (!s) return ''
  if (/[\u4e00-\u9fff]/.test(s) && !/failed|invalid|error|forbidden|authenticate/i.test(s)) {
    return s
  }
  for (const [re, zh] of PHRASES) {
    if (re.test(s)) return zh
  }
  return ''
}
