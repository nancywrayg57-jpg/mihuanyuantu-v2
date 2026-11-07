/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("archives")
  const field = collection.schema.getFieldByName("media_files")
  if (!field) return

  // Keep thumbs non-empty — empty thumbs [] broke creates on PB 0.22.
  // maxSize = video cap; image/other caps enforced in frontend.
  field.options.maxSelect = 9
  field.options.maxSize = 629145600 // 600MB
  field.options.thumbs = ["600x0"]
  field.options.protected = false
  field.options.mimeTypes = [
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/heic",
    "image/heif",
    "image/avif",
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "application/pdf",
    "audio/mpeg",
    "audio/mp4",
    "audio/x-m4a",
    "audio/wav",
    "audio/webm",
    "audio/ogg",
    "application/octet-stream",
  ]

  return dao.saveCollection(collection)
}, (db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("archives")
  const field = collection.schema.getFieldByName("media_files")
  if (!field) return
  field.options.maxSize = 524288000
  return dao.saveCollection(collection)
})
