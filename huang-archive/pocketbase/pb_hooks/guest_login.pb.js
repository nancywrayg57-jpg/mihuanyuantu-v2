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
    return $apis.recordAuthResponse(c, record, null)
  } catch (e) {
    console.log("guest-login error:", e)
    return c.json(500, { message: "吊唁贵宾登录失败，请稍后重试" })
  }
})
