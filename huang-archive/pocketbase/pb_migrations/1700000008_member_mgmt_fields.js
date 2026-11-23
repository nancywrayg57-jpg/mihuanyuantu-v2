/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("users")

  const RELATION_VALUES = [
    "儿子", "女儿", "儿媳", "女婿", "外甥", "外甥女", "曾孙", "曾孙女", "曾外孙", "曾外甥女",
  ]

  // Snapshot existing relation text before schema change
  const existing = []
  try {
    const rows = dao.findRecordsByFilter("users", "id != ''", "-created", 500, 0)
    for (const r of rows) {
      existing.push({ id: r.id, relation: r.get("relation") || "", display_name: r.get("display_name") || "" })
    }
  } catch (_) {}

  if (!collection.schema.getFieldByName("birth_date")) {
    collection.schema.addField(new SchemaField({
      system: false,
      id: "birthdate01",
      name: "birth_date",
      type: "text",
      required: false,
      presentable: false,
      unique: false,
      options: { min: null, max: 32, pattern: "" },
    }))
  }

  const oldRel = collection.schema.getFieldByName("relation")
  if (oldRel) {
    collection.schema.removeField(oldRel.id)
  }

  if (!collection.schema.getFieldByName("relation")) {
    collection.schema.addField(new SchemaField({
      system: false,
      id: "relfield02",
      name: "relation",
      type: "select",
      required: false,
      presentable: true,
      unique: false,
      options: {
        maxSelect: 1,
        values: RELATION_VALUES,
      },
    }))
  }

  collection.createRule = '@request.auth.role = "admin"'
  collection.updateRule = 'id = @request.auth.id || @request.auth.role = "admin"'
  collection.deleteRule = '@request.auth.role = "admin"'
  collection.listRule = '@request.auth.id != ""'
  collection.viewRule = '@request.auth.id != ""'
  // Allow admin to set passwords without oldPassword
  collection.options = {
    allowEmailAuth: true,
    allowOAuth2Auth: false,
    allowUsernameAuth: true,
    exceptEmailDomains: null,
    manageRule: '@request.auth.role = "admin"',
    minPasswordLength: 6,
    onlyEmailDomains: null,
    requireEmail: true,
  }

  dao.saveCollection(collection)

  function mapRelation(displayName, old) {
    if (RELATION_VALUES.indexOf(old) >= 0) return old
    const name = displayName || ""
    // Best-effort for seeded accounts
    const sons = ["黄纲生", "黄成生", "黄纲富", "黄纲兴", "黄纲财", "黄纲平"]
    const daughters = ["黄爱眉", "黄爱秀"]
    const sonsInLaw = ["张银财", "吴雨齐"]
    const grandsons = ["黄祥财", "黄祥贵", "黄祥文", "黄祥明", "黄祥健", "黄祥鑫", "黄祥琳", "黄祥瑞", "黄祥伟"]
    const granddaughters = ["黄祥妹", "黄媛媛", "黄晓芳", "黄嘉颖"]
    const maternal = ["张惠", "吴玲玲", "张建华", "吴泽强"]
    if (sons.indexOf(name) >= 0) return "儿子"
    if (daughters.indexOf(name) >= 0) return "女儿"
    if (sonsInLaw.indexOf(name) >= 0) return "女婿"
    if (grandsons.indexOf(name) >= 0) return "曾孙"
    if (granddaughters.indexOf(name) >= 0) return "曾孙女"
    if (maternal.indexOf(name) >= 0) return "女婿"
    if (old === "长子") return "儿子"
    if (old === "maternal_grandfather") return "女婿"
    return ""
  }

  for (const row of existing) {
    try {
      const rec = dao.findRecordById("users", row.id)
      const mapped = mapRelation(row.display_name, row.relation)
      if (mapped) {
        rec.set("relation", mapped)
        dao.saveRecord(rec)
      }
    } catch (_) {}
  }
}, (db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("users")
  const birth = collection.schema.getFieldByName("birth_date")
  if (birth) collection.schema.removeField(birth.id)
  collection.createRule = null
  dao.saveCollection(collection)
})
