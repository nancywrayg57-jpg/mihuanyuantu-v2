/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("archives")
  const field = collection.schema.getFieldByName("media_files")
  if (!field) return

  // Keep thumbs non-empty (empty [] broke creates on PB 0.22).
  field.options.thumbs = ["600x0"]
  field.options.maxSelect = 9
  field.options.maxSize = 629145600
  field.options.protected = false
  field.options.mimeTypes = [
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
    "image/png",
    "image/x-png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/x-ms-bmp",
    "image/tiff",
    "image/heic",
    "image/heif",
    "image/avif",
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-m4v",
    "video/3gpp",
    "video/3gpp2",
    "video/x-msvideo",
    "video/avi",
    "video/mpeg",
    "video/x-matroska",
    "application/pdf",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/aac",
    "audio/wav",
    "audio/x-wav",
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
})
