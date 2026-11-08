/// <reference path="../pb_data/types.d.ts" />

function hzLoadSettings() {
  try {
    const row = $app.dao().findFirstRecordByFilter("site_settings", "key = {:k}", { k: "global" })
    return {
      guest_passwordless: !!row.get("guest_passwordless"),
      login_captcha: !!row.get("login_captcha"),
    }
  } catch (_) {
    return { guest_passwordless: true, login_captcha: false }
  }
}

function hzToString(v) {
  if (v == null) return ""
  if (typeof v === "string") return v
  try {
    return Array.prototype.slice.call(v).map((b) => String.fromCharCode(b)).join("")
  } catch (_) {
    return String(v)
  }
}

function hzConsumeTicket(ticket) {
  if (!ticket) return false
  const path = "/pb/pb_data/captcha_sessions/ticket_" + ticket + ".json"
  try {
    const raw = hzToString($os.readFile(path))
    try { $os.remove(path) } catch (_) {}
    const data = JSON.parse(raw || "{}")
    if (!data || data.used) return false
    if (Date.now() > Number(data.exp || 0)) return false
    return true
  } catch (_) {
    return false
  }
}

function hzConsumeCaptcha(id, code) {
  if (!id || !code) return false
  const path = "/pb/pb_data/captcha_sessions/" + id + ".json"
  try {
    const raw = hzToString($os.readFile(path))
    try { $os.remove(path) } catch (_) {}
    const data = JSON.parse(raw || "{}")
    if (!data || !data.code || !data.exp) return false
    if (Date.now() > Number(data.exp)) return false
    return String(code).trim().toUpperCase() === String(data.code).toUpperCase()
  } catch (_) {
    return false
  }
}

function hzRequireCaptcha(body, settings) {
  if (!settings.login_captcha) return null
  if (body && body.ticket && hzConsumeTicket(body.ticket)) return null
  if (body && hzConsumeCaptcha(body.captcha_id || body.id, body.captcha_code || body.code)) return null
  return "请先完成图形验证码"
}

// Passwordless entry for the shared 吊唁贵宾 account (when enabled).
routerAdd("POST", "/api/hz/guest-login", (c) => {
  try {
    const settings = hzLoadSettings()
    if (!settings.guest_passwordless) {
      return c.json(403, { message: "吊唁免登录模式已关闭，请使用家族姓名与密码登录" })
    }
    const info = $apis.requestInfo(c)
    const body = (info && info.data) || {}
    const captchaErr = hzRequireCaptcha(body, settings)
    if (captchaErr) return c.json(400, { message: captchaErr })

    const record = $app.dao().findFirstRecordByFilter(
      "users",
      'role = {:role} && display_name = {:name}',
      { role: "guest", name: "吊唁贵宾" },
    )
    try {
      if (record.getBool("disabled") || record.get("disabled") === true) {
        return c.json(403, { message: "吊唁贵宾入口暂不可用" })
      }
    } catch (_) {}
    return $apis.recordAuthResponse($app, c, record, null)
  } catch (e) {
    console.log("guest-login error:", e)
    try {
      const record2 = $app.dao().findFirstRecordByFilter(
        "users",
        'role = {:role} && display_name = {:name}',
        { role: "guest", name: "吊唁贵宾" },
      )
      const token = $tokens.recordAuthToken($app, record2)
      return c.json(200, {
        token: token,
        record: {
          id: record2.id,
          email: record2.getString("email"),
          username: record2.getString("username"),
          display_name: record2.getString("display_name"),
          role: record2.getString("role"),
          collectionId: record2.collection().id,
          collectionName: "users",
        },
      })
    } catch (e2) {
      console.log("guest-login fallback error:", e2)
      return c.json(500, { message: "吊唁贵宾登录失败，请稍后重试" })
    }
  }
})
