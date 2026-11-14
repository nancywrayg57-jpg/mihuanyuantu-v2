/// <reference path="../pb_data/types.d.ts" />

// Family member login with optional captcha gate (helpers inlined for PB JSVM).
routerAdd("POST", "/api/hz/member-login", (c) => {
  try {
    var info = $apis.requestInfo(c)
    var body = (info && info.data) || {}
    var login_captcha = false
    try {
      var rows = $app.dao().findRecordsByFilter("site_settings", "id != ''", "-created", 10, 0)
      for (var i = 0; i < rows.length; i++) {
        if (String(rows[i].get("key") || "") === "global") {
          try { login_captcha = !!rows[i].get("login_captcha") } catch (_) {}
          break
        }
      }
    } catch (_) {}

    if (login_captcha) {
      var ok = false
      var ticket = body.ticket
      if (ticket) {
        try {
          var tpath = "/pb/pb_data/captcha_sessions/ticket_" + ticket + ".json"
          var traw = $os.readFile(tpath)
          try { $os.remove(tpath) } catch (_) {}
          var tstr = typeof traw === "string" ? traw : String(traw || "")
          try {
            if (typeof traw !== "string") {
              tstr = Array.prototype.slice.call(traw).map(function (b) { return String.fromCharCode(b) }).join("")
            }
          } catch (_) {}
          var tdata = JSON.parse(tstr || "{}")
          if (tdata && !tdata.used && Date.now() <= Number(tdata.exp || 0)) ok = true
        } catch (_) {}
      }
      if (!ok) {
        var cid = body.captcha_id || body.id
        var ccode = body.captcha_code || body.code
        if (cid && ccode) {
          try {
            var cpath = "/pb/pb_data/captcha_sessions/" + cid + ".json"
            var craw = $os.readFile(cpath)
            try { $os.remove(cpath) } catch (_) {}
            var cstr = typeof craw === "string" ? craw : String(craw || "")
            try {
              if (typeof craw !== "string") {
                cstr = Array.prototype.slice.call(craw).map(function (b) { return String.fromCharCode(b) }).join("")
              }
            } catch (_) {}
            var cdata = JSON.parse(cstr || "{}")
            if (cdata && cdata.code && Date.now() <= Number(cdata.exp || 0) &&
                String(ccode).trim().toUpperCase() === String(cdata.code).toUpperCase()) {
              ok = true
            }
          } catch (_) {}
        }
      }
      if (!ok) return c.json(400, { message: "请先完成图形验证码" })
    }

    var name = String(body.name || body.display_name || "").trim()
    var password = String(body.password || "")
    if (!name || !password) return c.json(400, { message: "请输入姓名与密码" })

    var record = null
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

    var okPwd = false
    try { okPwd = !!record.validatePassword(password) } catch (_) { okPwd = false }
    if (!okPwd) return c.json(400, { message: "登录失败：姓名或密码不正确" })
    return $apis.recordAuthResponse($app, c, record, null)
  } catch (e) {
    console.log("member-login error:", e)
    return c.json(500, { message: "登录失败，请稍后重试" })
  }
})
