/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("archives")

  if (!collection.schema.getFieldByName("sort_order")) {
    collection.schema.addField(new SchemaField({
      system: false,
      id: "arcsort00001",
      name: "sort_order",
      type: "number",
      required: false,
      options: { min: 0, max: null, noDecimal: true },
    }))
  }

  if (!collection.schema.getFieldByName("listed")) {
    collection.schema.addField(new SchemaField({
      system: false,
      id: "arclisted001",
      name: "listed",
      type: "bool",
      // PB bool defaults to false when unset — migration loop forces true on existing rows.
      required: false,
      options: {},
    }))
  }

  // Owners may not change home order / visibility; admin can.
  collection.updateRule =
    '@request.auth.role = "admin" || (uploader = @request.auth.id && @request.data.category:isset = false && @request.data.external_link:isset = false && @request.data.uploader:isset = false && @request.data.uploader_name:isset = false && @request.data.likes_count:isset = false && @request.data.sort_order:isset = false && @request.data.listed:isset = false)'

  dao.saveCollection(collection)

  // PB bool fields default to false — force listed=true on ALL existing rows after add.
  try {
    const rows = dao.findRecordsByFilter("archives", "id != ''", "-created", 500, 0)
    rows.forEach((r) => {
      r.set("listed", true)
      try {
        const so = r.get("sort_order")
        if (so === null || so === undefined || so === "") r.set("sort_order", 0)
      } catch (_) {
        r.set("sort_order", 0)
      }
      dao.saveRecord(r)
    })
  } catch (_) {}
}, (db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("archives")
  ;["sort_order", "listed"].forEach((n) => {
    const f = collection.schema.getFieldByName(n)
    if (f) collection.schema.removeField(f.id)
  })
  collection.updateRule =
    '@request.auth.role = "admin" || (uploader = @request.auth.id && @request.data.category:isset = false && @request.data.external_link:isset = false && @request.data.uploader:isset = false && @request.data.uploader_name:isset = false && @request.data.likes_count:isset = false)'
  dao.saveCollection(collection)
})
