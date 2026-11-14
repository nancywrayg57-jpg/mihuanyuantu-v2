/// <reference path="../pb_data/types.d.ts" />

// NOTE: PB JSVM does not share sibling function declarations across routerAdd
// closures — keep helpers inlined inside each route (same as upload_chunk.pb.js).

routerAdd("GET", "/api/hz/site-settings", (c) => {
  try {
    var guest_passwordless = true
    var login_captcha = false
    var id = ""
    try {
      var rows = $app.dao().findRecordsByFilter("site_settings", "id != ''", "-created", 10, 0)
      var row = null
      for (var i = 0; i < rows.length; i++) {
        if (String(rows[i].get("key") || "") === "global") {
          row = rows[i]
          break
        }
      }
      if (!row && rows.length) row = rows[0]
      if (row) {
        id = String(row.id || "")
        try { guest_passwordless = !!row.get("guest_passwordless") } catch (_) {}
        try { login_captcha = !!row.get("login_captcha") } catch (_) {}
      }
    } catch (err) {
      console.log("site-settings load:", err)
    }
    return c.json(200, {
      guest_passwordless: guest_passwordless,
      login_captcha: login_captcha,
      id: id,
    })
  } catch (e) {
    console.log("site-settings GET error:", e)
    return c.json(500, { message: "读取站点设置失败" })
  }
})

routerAdd("PATCH", "/api/hz/site-settings", (c) => {
  try {
    var info = $apis.requestInfo(c)
    var user = info && info.authRecord
    if (!user || String(user.get("role") || "") !== "admin") {
      return c.json(403, { message: "仅管理员可修改全局设置" })
    }
    var body = (info && info.data) || {}
    var row = null
    try {
      var rows = $app.dao().findRecordsByFilter("site_settings", "id != ''", "-created", 10, 0)
      for (var i = 0; i < rows.length; i++) {
        if (String(rows[i].get("key") || "") === "global") {
          row = rows[i]
          break
        }
      }
      if (!row && rows.length) row = rows[0]
    } catch (_) {}
    if (!row) {
      var col = $app.dao().findCollectionByNameOrId("site_settings")
      row = new Record(col)
      row.set("key", "global")
    }
    if (body.guest_passwordless === true || body.guest_passwordless === false) {
      row.set("guest_passwordless", !!body.guest_passwordless)
    }
    if (body.login_captcha === true || body.login_captcha === false) {
      row.set("login_captcha", !!body.login_captcha)
    }
    $app.dao().saveRecord(row)
    return c.json(200, {
      guest_passwordless: !!row.get("guest_passwordless"),
      login_captcha: !!row.get("login_captcha"),
      id: String(row.id || ""),
    })
  } catch (e) {
    console.log("site-settings patch error:", e)
    return c.json(500, { message: "保存站点设置失败" })
  }
})

routerAdd("GET", "/api/hz/captcha", (c) => {
  try {
    try { $os.mkdirAll("/pb/pb_data/captcha_sessions", 0o755) } catch (_) {}
    var chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    var code = ""
    for (var i = 0; i < 4; i++) {
      code += chars[Math.floor(Math.random() * chars.length)]
    }
    var id = $security.randomString(20)
    var payload = { code: String(code).toUpperCase(), exp: Date.now() + 5 * 60 * 1000 }
    $os.writeFile("/pb/pb_data/captcha_sessions/" + id + ".json", JSON.stringify(payload))
    var svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="52">' +
      '<rect width="160" height="52" fill="#f7f4eb"/>' +
      '<line x1="8" y1="14" x2="150" y2="40" stroke="#e2d9c8" stroke-width="2"/>' +
      '<line x1="12" y1="44" x2="148" y2="10" stroke="#d4cbb8" stroke-width="2"/>' +
      '<text x="18" y="36" font-family="monospace" font-size="28" fill="#262422">' +
      code +
      "</text></svg>"
    return c.json(200, { id: id, svg: svg })
  } catch (e) {
    console.log("captcha create error:", e)
    return c.json(500, { message: "验证码生成失败" })
  }
})

routerAdd("POST", "/api/hz/captcha/verify", (c) => {
  try {
    var info = $apis.requestInfo(c)
    var body = (info && info.data) || {}
    var id = body.captcha_id || body.id
    var code = body.captcha_code || body.code
    if (!id || !code) return c.json(400, { message: "请输入验证码" })
    var path = "/pb/pb_data/captcha_sessions/" + id + ".json"
    var raw = ""
    try {
      var bytes = $os.readFile(path)
      if (typeof bytes === "string") raw = bytes
      else {
        try {
          raw = Array.prototype.slice.call(bytes).map(function (b) { return String.fromCharCode(b) }).join("")
        } catch (_) {
          raw = String(bytes || "")
        }
      }
      try { $os.remove(path) } catch (_) {}
    } catch (_) {
      return c.json(400, { message: "验证码错误或已过期" })
    }
    var data = JSON.parse(raw || "{}")
    if (!data.code || Date.now() > Number(data.exp || 0)) {
      return c.json(400, { message: "验证码错误或已过期" })
    }
    if (String(code).trim().toUpperCase() !== String(data.code).toUpperCase()) {
      return c.json(400, { message: "验证码错误或已过期" })
    }
    try { $os.mkdirAll("/pb/pb_data/captcha_sessions", 0o755) } catch (_) {}
    var ticket = $security.randomString(24)
    $os.writeFile(
      "/pb/pb_data/captcha_sessions/ticket_" + ticket + ".json",
      JSON.stringify({ exp: Date.now() + 2 * 60 * 1000, used: false }),
    )
    return c.json(200, { ticket: ticket })
  } catch (e) {
    console.log("captcha verify error:", e)
    return c.json(500, { message: "验证码校验失败" })
  }
})
