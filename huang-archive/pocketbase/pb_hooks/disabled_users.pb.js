/// <reference path="../pb_data/types.d.ts" />

onRecordAuthRequest((e) => {
  try {
    if (e.record && e.record.getBool("disabled")) {
      throw new BadRequestError("该成员账号已停用，请联系管理员")
    }
  } catch (err) {
    if (err instanceof BadRequestError) throw err
    // getBool may not exist on older bindings
    try {
      if (e.record && e.record.get("disabled") === true) {
        throw new BadRequestError("该成员账号已停用，请联系管理员")
      }
    } catch (err2) {
      if (err2 instanceof BadRequestError) throw err2
    }
  }
}, "users")
