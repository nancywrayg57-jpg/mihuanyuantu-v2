/// <reference path="../pb_data/types.d.ts" />

// Public helpers for Chinese-name login (family archive; names only / resolve identity).

routerAdd("GET", "/api/hz/member-names", (c) => {
  try {
    const records = $app.dao().findRecordsByFilter("users", "id != ''", "display_name", 500, 0)
    const items = []
    for (const r of records) {
      items.push({
        display_name: r.get("display_name"),
        role: r.get("role") || "member",
      })
    }
    return c.json(200, { items })
  } catch (e) {
    return c.json(500, { message: "加载成员列表失败" })
  }
})

routerAdd("GET", "/api/hz/resolve-name", (c) => {
  const name = (c.queryParam("name") || "").trim()
  if (!name) {
    return c.json(400, { message: "请提供姓名" })
  }
  try {
    const record = $app.dao().findFirstRecordByFilter(
      "users",
      "display_name = {:name}",
      { name: name },
    )
    return c.json(200, {
      email: record.getString("email"),
      username: record.getString("username"),
      display_name: record.getString("display_name"),
      role: record.getString("role"),
    })
  } catch (e) {
    return c.json(404, { message: "未找到该家族姓名" })
  }
})
