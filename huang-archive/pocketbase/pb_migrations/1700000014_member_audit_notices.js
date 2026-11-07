/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)

  // users.disabled for soft-deactivate
  const users = dao.findCollectionByNameOrId("users")
  if (!users.schema.getFieldByName("disabled")) {
    users.schema.addField(new SchemaField({
      system: false,
      id: "userdisabl01",
      name: "disabled",
      type: "bool",
      required: false,
      options: {},
    }))
  }
  dao.saveCollection(users)

  // audit_logs
  try {
    dao.findCollectionByNameOrId("audit_logs")
  } catch (_) {
    const audit = new Collection({
      id: "auditlogs00001",
      name: "audit_logs",
      type: "base",
      system: false,
      listRule: '@request.auth.role = "admin"',
      viewRule: '@request.auth.role = "admin"',
      createRule: '@request.auth.role = "admin"',
      updateRule: null,
      deleteRule: '@request.auth.role = "admin"',
      schema: [
        {
          system: false,
          id: "audact00001",
          name: "action",
          type: "text",
          required: true,
          options: { min: 1, max: 80, pattern: "" },
        },
        {
          system: false,
          id: "audtgt00001",
          name: "target",
          type: "text",
          required: false,
          options: { min: null, max: 200, pattern: "" },
        },
        {
          system: false,
          id: "auddet00001",
          name: "detail",
          type: "text",
          required: false,
          options: { min: null, max: 2000, pattern: "" },
        },
        {
          system: false,
          id: "audactor001",
          name: "actor_name",
          type: "text",
          required: false,
          options: { min: null, max: 100, pattern: "" },
        },
        {
          system: false,
          id: "audactid001",
          name: "actor",
          type: "relation",
          required: false,
          options: {
            collectionId: users.id,
            cascadeDelete: false,
            minSelect: null,
            maxSelect: 1,
            displayFields: ["display_name"],
          },
        },
      ],
    })
    dao.saveCollection(audit)
  }

  // notices (family update digest)
  try {
    dao.findCollectionByNameOrId("notices")
  } catch (_) {
    const notices = new Collection({
      id: "notices000001",
      name: "notices",
      type: "base",
      system: false,
      listRule: '@request.auth.id != ""',
      viewRule: '@request.auth.id != ""',
      createRule: '@request.auth.role = "admin"',
      updateRule: '@request.auth.role = "admin"',
      deleteRule: '@request.auth.role = "admin"',
      schema: [
        {
          system: false,
          id: "nottitle001",
          name: "title",
          type: "text",
          required: true,
          options: { min: 1, max: 200, pattern: "" },
        },
        {
          system: false,
          id: "notbody0001",
          name: "body",
          type: "text",
          required: true,
          options: { min: 1, max: 5000, pattern: "" },
        },
        {
          system: false,
          id: "notpin00001",
          name: "pinned",
          type: "bool",
          required: false,
          options: {},
        },
      ],
    })
    dao.saveCollection(notices)
  }
}, (db) => {
  const dao = new Dao(db)
  try { dao.deleteCollection(dao.findCollectionByNameOrId("notices")) } catch (_) {}
  try { dao.deleteCollection(dao.findCollectionByNameOrId("audit_logs")) } catch (_) {}
  try {
    const users = dao.findCollectionByNameOrId("users")
    const f = users.schema.getFieldByName("disabled")
    if (f) users.schema.removeField(f.id)
    dao.saveCollection(users)
  } catch (_) {}
})
