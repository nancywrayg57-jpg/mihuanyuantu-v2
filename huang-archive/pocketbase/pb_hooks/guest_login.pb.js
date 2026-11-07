/// <reference path="../pb_data/types.d.ts" />

// Passwordless entry for the shared 吊唁贵宾 account.
routerAdd("POST", "/api/hz/guest-login", (c) => {
  try {
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
    // PB 0.22 JSVM binds the Go func as-is: (app, c, record, meta)
    return $apis.recordAuthResponse($app, c, record, null)
  } catch (e) {
    console.log("guest-login error:", e)
    // Fallback: mint token manually if response helper binding differs
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

