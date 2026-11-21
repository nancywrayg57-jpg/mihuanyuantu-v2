/// <reference path="../pb_data/types.d.ts" />

// Passwordless entry for 吊唁贵宾 (when guest_passwordless enabled).
// Helpers inlined — PB JSVM routerAdd closures cannot see sibling decls.
routerAdd("POST", "/api/hz/guest-login", (c) => {
  try {
    var guest_passwordless = true
    var login_captcha = false
    try {
      var rows = $app.dao().findRecordsByFilter("site_settings", "id != ''", "-created", 10, 0)
      for (var i = 0; i < rows.length; i++) {
        if (String(rows[i].get("key") || "") === "global") {
          try { guest_passwordless = !!rows[i].get("guest_passwordless") } catch (_) {}
          try { login_captcha = !!rows[i].get("login_captcha") } catch (_) {}
          break
        }
      }
    } catch (_) {}

    if (!guest_passwordless) {
      return c.json(403, { message: "吊唁免登录模式已关闭，请使用家族姓名与密码登录" })
    }

    var info = $apis.requestInfo(c)
    var body = (info && info.data) || {}

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

    var record = $app.dao().findFirstRecordByFilter(
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
      var record2 = $app.dao().findFirstRecordByFilter(
        "users",
        'role = {:role} && display_name = {:name}',
        { role: "guest", name: "吊唁贵宾" },
      )
      var token = $tokens.recordAuthToken($app, record2)
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
