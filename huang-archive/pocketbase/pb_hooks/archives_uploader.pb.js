/// <reference path="../pb_data/types.d.ts" />

// Force archives.uploader from the authenticated user on every create.
// Runs after request parsing; uploader field is not required (migration 0016)
// so invalid client values like "[object Object]" can be overwritten here.

onRecordBeforeCreateRequest((e) => {
  try {
    var user = null
    try {
      var info = $apis.requestInfo(e.httpContext)
      if (info) user = info.authRecord
    } catch (err1) {
      console.log("archives_uploader requestInfo:", err1)
    }
    try {
      if (!user && e.auth) user = e.auth
    } catch (err2) {}

    if (!user) {
      // Superuser/admin API without authRecord: keep provided uploader
      var existing = e.record.get("uploader")
      if (existing && String(existing) !== "[object Object]") return
      throw new BadRequestError("请先登录后再上传")
    }

    var uid = ""
    try { uid = user.id || "" } catch (err3) {}
    if (!uid) {
      try { uid = String(user.get("id") || "") } catch (err4) {}
    }
    if (!uid) throw new BadRequestError("无法确认上传者身份，请重新登录后再试")

    // Always overwrite — ignore client uploader (may be truncated / object string)
    e.record.set("uploader", uid)

    var name = ""
    try { name = user.getString("display_name") || "" } catch (err5) {}
    if (!name) {
      try { name = String(user.get("display_name") || "") } catch (err6) {}
    }
    if (name) e.record.set("uploader_name", name)
  } catch (err) {
    if (err instanceof BadRequestError) throw err
    console.log("archives_uploader fatal:", err)
    throw new BadRequestError("无法确认上传者身份，请重新登录后再试")
  }
}, "archives")
