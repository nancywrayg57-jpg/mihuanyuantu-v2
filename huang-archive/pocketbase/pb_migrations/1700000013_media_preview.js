/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("archives")

  collection.schema.addField(new SchemaField({
    system: false,
    id: "arccover0001",
    name: "cover_file",
    type: "file",
    required: false,
    options: {
      maxSelect: 1,
      maxSize: 5 * 1024 * 1024,
      mimeTypes: ["image/jpeg", "image/png", "image/webp"],
      thumbs: ["200x0", "600x0"],
      protected: false,
    },
  }))

  collection.schema.addField(new SchemaField({
    system: false,
    id: "arcdur000001",
    name: "duration_sec",
    type: "number",
    required: false,
    options: { min: 0, max: null, noDecimal: false },
  }))

  return dao.saveCollection(collection)
}, (db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("archives")
  ;["cover_file", "duration_sec"].forEach((n) => {
    const f = collection.schema.getFieldByName(n)
    if (f) collection.schema.removeField(f.id)
  })
  return dao.saveCollection(collection)
})
