/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("users")

  // Replace options with a plain JSON-serializable object (required for PB 0.22 JSVM)
  collection.options = {
    allowEmailAuth: true,
    allowOAuth2Auth: false,
    allowUsernameAuth: true,
    exceptEmailDomains: null,
    manageRule: null,
    minPasswordLength: 6,
    onlyEmailDomains: null,
    requireEmail: true,
  }

  const nameField = collection.schema.getFieldByName("name")
  if (nameField) {
    collection.schema.removeField(nameField.id)
  }

  if (!collection.schema.getFieldByName("display_name")) {
    collection.schema.addField(new SchemaField({
      system: false,
      id: "dispname01",
      name: "display_name",
      type: "text",
      required: true,
      presentable: true,
      unique: false,
      options: { min: 1, max: 64, pattern: "" },
    }))
  }

  if (!collection.schema.getFieldByName("role")) {
    collection.schema.addField(new SchemaField({
      system: false,
      id: "rolefield01",
      name: "role",
      type: "select",
      required: true,
      presentable: true,
      unique: false,
      options: {
        maxSelect: 1,
        values: ["admin", "member"],
      },
    }))
  }

  if (!collection.schema.getFieldByName("relation")) {
    collection.schema.addField(new SchemaField({
      system: false,
      id: "relfield01",
      name: "relation",
      type: "text",
      required: false,
      presentable: false,
      unique: false,
      options: { min: null, max: 128, pattern: "" },
    }))
  }

  collection.listRule = '@request.auth.id != ""'
  collection.viewRule = '@request.auth.id != ""'
  collection.createRule = null
  collection.updateRule = 'id = @request.auth.id || @request.auth.role = "admin"'
  collection.deleteRule = '@request.auth.role = "admin"'

  return dao.saveCollection(collection)
}, (db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("users")
  ;["display_name", "role", "relation"].forEach((n) => {
    const f = collection.schema.getFieldByName(n)
    if (f) collection.schema.removeField(f.id)
  })
  return dao.saveCollection(collection)
})
