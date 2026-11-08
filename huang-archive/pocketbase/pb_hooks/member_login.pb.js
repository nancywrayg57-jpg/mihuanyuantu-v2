/// <reference path="../pb_data/types.d.ts" />

function mlSettings() {
  try {
    const row = $app.dao().findFirstRecordByFilter("site_settings", "key = {:k}", { k: "global" })
    return { login_captcha: !!row.get("login_captcha") }
  } catch (_) {
    return { login_captcha: false }
  }
}

function mlToString(v) {
  if (v == null) return ""
  if (typeof v === "string") return v
  try {
    return Array.prototype.slice.call(v).map((b) => String.fromCharCode(b)).join("")
  } catch (_) {
    return String(v)
  }
}

function mlConsumeTicket(ticket) {
  if (!ticket) return false
  const path = "/pb/pb_data/captcha_sessions/ticket_" + ticket + ".json"
  try {
    const raw = mlToString($os.readFile(path))
    try { $os.remove(path) } catch (_) {}
    const data = JSON.parse(raw || "{}")
    if (!data || data.used) return false
    if (Date.now() > Number(data.exp || 0)) return false
    return true
  } catch (_) {
    return false
  }
}

function mlConsumeCaptcha(id, code) {
  if (!id || !code) return false
  const path = "/pb/pb_data/captcha_sessions/" + id + ".json"
  try {
    const raw = mlToString($os.readFile(path))
    try { $os.remove(path) } catch (_) {}
    const data = JSON.parse(raw || "{}")
    if (!data || !data.code || !data.exp) return false
    if (Date.now() > Number(data.exp)) return false
    return String(code).trim().toUpperCase() === String(data.code).toUpperCase()
  } catch (_) {
    return false
  }
}

routerAdd("POST", "/api/hz/member-login", (c) => {
  try {
    const info = $apis.requestInfo(c)
    const body = (info && info.data) || {}
    const settings = mlSettings()
    if (settings.login_captcha) {
      const ok =
        mlConsumeTicket(body.ticket) ||
        mlConsumeCaptcha(body.captcha_id || body.id, body.captcha_code || body.code)
      if (!ok) return c.json(400, { message: "请先完成图形验证码" })
    }

    const name = String(body.name || body.display_name || "").trim()
    const password = String(body.password || "")
    if (!name || !password) return c.json(400, { message: "请输入姓名与密码" })

    let record = null
    try {
      record = $app.dao().findFirstRecordByFilter("users", "display_name = {:n}", { n: name })
    } catch (_) {
      return c.json(400, { message: "未找到该家族姓名，请点选列表中的姓名" })
    }
    if (String(record.get("role") || "") === "guest") {
      return c.json(400, { message: "贵宾请使用免密入口（若已开启）" })
    }
    try {
      if (record.getBool("disabled") || record.get("disabled") === true) {
        return c.json(403, { message: "该成员账号已停用，请联系管理员" })
      }
    } catch (_) {}

    let okPwd = false
    try {
      okPwd = !!record.validatePassword(password)
    } catch (_) {
      okPwd = false
    }
    if (!okPwd) {
      return c.json(400, { message: "登录失败：姓名或密码不正确" })
    }
    return $apis.recordAuthResponse($app, c, record, null)
  } catch (e) {
    console.log("member-login error:", e)
    return c.json(500, { message: "登录失败，请稍后重试" })
  }
})
