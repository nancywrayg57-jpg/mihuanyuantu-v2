/// <reference path="../pb_data/types.d.ts" />

function loadGlobalSettings() {
  try {
    const row = $app.dao().findFirstRecordByFilter("site_settings", "key = {:k}", { k: "global" })
    return {
      guest_passwordless: !!row.get("guest_passwordless"),
      login_captcha: !!row.get("login_captcha"),
      id: row.id,
    }
  } catch (_) {
    return { guest_passwordless: true, login_captcha: false, id: "" }
  }
}

function captchaDir() {
  return "/pb/pb_data/captcha_sessions"
}

function ensureCaptchaDir() {
  try {
    $os.mkdirAll(captchaDir(), 0o755)
  } catch (_) {}
}

function randomCaptchaCode() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
  let out = ""
  for (let i = 0; i < 4; i++) {
    out += chars[Math.floor(Math.random() * chars.length)]
  }
  return out
}

function captchaSvg(code) {
  const c = String(code || "")
  return (
    '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="52">' +
    '<rect width="160" height="52" fill="#f7f4eb"/>' +
    '<line x1="8" y1="14" x2="150" y2="40" stroke="#e2d9c8" stroke-width="2"/>' +
    '<line x1="12" y1="44" x2="148" y2="10" stroke="#d4cbb8" stroke-width="2"/>' +
    '<text x="18" y="36" font-family="monospace" font-size="28" fill="#262422">' +
    c +
    "</text></svg>"
  )
}

function toString(v) {
  if (v == null) return ""
  if (typeof v === "string") return v
  try {
    return Array.prototype.slice.call(v).map((b) => String.fromCharCode(b)).join("")
  } catch (_) {
    return String(v)
  }
}

routerAdd("GET", "/api/hz/site-settings", (c) => {
  try {
    return c.json(200, loadGlobalSettings())
  } catch (e) {
    return c.json(500, { message: "读取站点设置失败" })
  }
})

routerAdd("PATCH", "/api/hz/site-settings", (c) => {
  try {
    const info = $apis.requestInfo(c)
    const user = info && info.authRecord
    if (!user || String(user.get("role") || "") !== "admin") {
      return c.json(403, { message: "仅管理员可修改全局设置" })
    }
    const body = (info && info.data) || {}
    let row = null
    try {
      row = $app.dao().findFirstRecordByFilter("site_settings", "key = {:k}", { k: "global" })
    } catch (_) {}
    if (!row) {
      const col = $app.dao().findCollectionByNameOrId("site_settings")
      row = new Record(col)
      row.set("key", "global")
    }
    if (Object.prototype.hasOwnProperty.call(body, "guest_passwordless")) {
      row.set("guest_passwordless", !!body.guest_passwordless)
    }
    if (Object.prototype.hasOwnProperty.call(body, "login_captcha")) {
      row.set("login_captcha", !!body.login_captcha)
    }
    $app.dao().saveRecord(row)
    return c.json(200, {
      guest_passwordless: !!row.get("guest_passwordless"),
      login_captcha: !!row.get("login_captcha"),
      id: row.id,
    })
  } catch (e) {
    console.log("site-settings patch error:", e)
    return c.json(500, { message: "保存站点设置失败" })
  }
})

routerAdd("GET", "/api/hz/captcha", (c) => {
  try {
    ensureCaptchaDir()
    const id = $security.randomString(20)
    const code = randomCaptchaCode()
    const payload = { code: String(code).toUpperCase(), exp: Date.now() + 5 * 60 * 1000 }
    $os.writeFile(captchaDir() + "/" + id + ".json", JSON.stringify(payload))
    const svg = captchaSvg(code)
    return c.json(200, { id: id, svg: svg })
  } catch (e) {
    console.log("captcha create error:", e)
    return c.json(500, { message: "验证码生成失败" })
  }
})

routerAdd("POST", "/api/hz/captcha/verify", (c) => {
  try {
    const info = $apis.requestInfo(c)
    const body = (info && info.data) || {}
    const id = body.captcha_id || body.id
    const code = body.captcha_code || body.code
    if (!id || !code) return c.json(400, { message: "请输入验证码" })
    const path = captchaDir() + "/" + id + ".json"
    let raw = ""
    try {
      raw = toString($os.readFile(path))
      try { $os.remove(path) } catch (_) {}
    } catch (_) {
      return c.json(400, { message: "验证码错误或已过期" })
    }
    const data = JSON.parse(raw || "{}")
    if (!data.code || Date.now() > Number(data.exp || 0)) {
      return c.json(400, { message: "验证码错误或已过期" })
    }
    if (String(code).trim().toUpperCase() !== String(data.code).toUpperCase()) {
      return c.json(400, { message: "验证码错误或已过期" })
    }
    ensureCaptchaDir()
    const ticket = $security.randomString(24)
    $os.writeFile(
      captchaDir() + "/ticket_" + ticket + ".json",
      JSON.stringify({ exp: Date.now() + 2 * 60 * 1000, used: false }),
    )
    return c.json(200, { ticket: ticket })
  } catch (e) {
    console.log("captcha verify error:", e)
    return c.json(500, { message: "验证码校验失败" })
  }
})
