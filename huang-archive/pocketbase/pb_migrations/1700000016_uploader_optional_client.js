/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("archives")
  const field = collection.schema.getFieldByName("uploader")
  if (!field) return
  // Client may omit uploader; archives_uploader.pb.js binds it from auth
  // before save. Keeping required=true caused validation to run before the
  // hook and reject mobile uploads with bad/missing relation ids.
  field.required = false
  return dao.saveCollection(collection)
}, (db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("archives")
  const field = collection.schema.getFieldByName("uploader")
  if (!field) return
  field.required = true
  return dao.saveCollection(collection)
})
