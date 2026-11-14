/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("archives")
  // Admin: any update. Owner: may update media_files/cover_file + text fields;
  // still cannot change category/external_link/uploader/likes_count.
  collection.updateRule =
    '@request.auth.role = "admin" || (uploader = @request.auth.id && @request.data.category:isset = false && @request.data.external_link:isset = false && @request.data.uploader:isset = false && @request.data.uploader_name:isset = false && @request.data.likes_count:isset = false)'
  return dao.saveCollection(collection)
}, (db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("archives")
  collection.updateRule =
    '@request.auth.role = "admin" || (uploader = @request.auth.id && @request.data.category:isset = false && @request.data.media_files:isset = false && @request.data.external_link:isset = false && @request.data.uploader:isset = false && @request.data.uploader_name:isset = false && @request.data.likes_count:isset = false)'
  return dao.saveCollection(collection)
})
