/// <reference path="../pb_data/types.d.ts" />

routerAdd("GET", "/api/health", (c) => {
  return c.json(200, { status: "ok", service: "huang-archive" })
})
