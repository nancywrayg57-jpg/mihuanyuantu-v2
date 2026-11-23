/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("memories")
  // Author may delete own comments; admin may delete any.
  collection.deleteRule =
    '@request.auth.role = "admin" || author = @request.auth.id'
  return dao.saveCollection(collection)
}, (db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("memories")
  collection.deleteRule = '@request.auth.role = "admin"'
  return dao.saveCollection(collection)
})
