/** Public + admin site settings helpers. */

export async function fetchSiteSettings() {
  const res = await fetch('/api/hz/site-settings')
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data?.message || '读取站点设置失败')
  return {
    guest_passwordless: data.guest_passwordless !== false,
    login_captcha: !!data.login_captcha,
    id: data.id || '',
  }
}

export async function patchSiteSettings(token, patch) {
  const res = await fetch('/api/hz/site-settings', {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Authorization: token,
    },
    body: JSON.stringify(patch),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data?.message || '保存站点设置失败')
  return data
}

export async function fetchCaptcha() {
  const res = await fetch('/api/hz/captcha')
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data?.message || '验证码生成失败')
  return data
}

export async function verifyCaptcha(captchaId, captchaCode) {
  const res = await fetch('/api/hz/captcha/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ captcha_id: captchaId, captcha_code: captchaCode }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data?.message || '验证码错误或已过期')
  return data.ticket
}

export const SITE_TITLE = '黄志松人生纪念馆'
