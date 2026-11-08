/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)

  let collection = null
  try {
    collection = dao.findCollectionByNameOrId("site_settings")
  } catch (_) {}

  if (!collection) {
    collection = new Collection({
      id: "sitesettings01",
      name: "site_settings",
      type: "base",
      system: false,
      // Public read so login page can load toggles; only admin may write.
      listRule: "",
      viewRule: "",
      createRule: '@request.auth.role = "admin"',
      updateRule: '@request.auth.role = "admin"',
      deleteRule: '@request.auth.role = "admin"',
      schema: [
        {
          system: false,
          id: "setkey00001",
          name: "key",
          type: "text",
          required: true,
          unique: true,
          options: { min: 1, max: 64, pattern: "" },
        },
        {
          system: false,
          id: "setguest001",
          name: "guest_passwordless",
          type: "bool",
          required: false,
          options: {},
        },
        {
          system: false,
          id: "setcaptcha1",
          name: "login_captcha",
          type: "bool",
          required: false,
          options: {},
        },
      ],
      indexes: [
        "CREATE UNIQUE INDEX idx_site_settings_key ON site_settings (key)",
      ],
    })
    dao.saveCollection(collection)
  }

  // Seed singleton row
  let row = null
  try {
    row = dao.findFirstRecordByFilter("site_settings", "key = {:k}", { k: "global" })
  } catch (_) {}
  if (!row) {
    row = new Record(collection)
    row.set("key", "global")
    row.set("guest_passwordless", true)
    row.set("login_captcha", false)
    dao.saveRecord(row)
  }

  // Reinforce memories delete: admin any, author own (incl. guest)
  const memories = dao.findCollectionByNameOrId("memories")
  memories.deleteRule =
    '@request.auth.role = "admin" || author = @request.auth.id'
  dao.saveCollection(memories)
}, (db) => {
  const dao = new Dao(db)
  try {
    const collection = dao.findCollectionByNameOrId("site_settings")
    dao.deleteCollection(collection)
  } catch (_) {}
})
