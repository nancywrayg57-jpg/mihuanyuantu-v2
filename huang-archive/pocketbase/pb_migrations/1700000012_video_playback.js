/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("archives")

  // Expand video / container MIME coverage for phone camera exports.
  const field = collection.schema.getFieldByName("media_files")
  if (field) {
    field.options.maxSize = 629145600
    field.options.thumbs = ["600x0"]
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
      "video/x-m4v",
      "video/3gpp",
      "video/3gpp2",
      "video/x-msvideo",
      "video/avi",
      "video/mpeg",
      "video/x-matroska",
      "application/pdf",
      "audio/mpeg",
      "audio/mp4",
      "audio/x-m4a",
      "audio/wav",
      "audio/webm",
      "audio/ogg",
      "application/octet-stream",
    ]
  }

  collection.schema.addField(new SchemaField({
    system: false,
    id: "arcplaystat1",
    name: "playback_status",
    type: "select",
    required: false,
    options: {
      maxSelect: 1,
      values: ["none", "native", "pending", "ready", "failed"],
    },
  }))

  collection.schema.addField(new SchemaField({
    system: false,
    id: "arcplayfile1",
    name: "playback_file",
    type: "file",
    required: false,
    options: {
      maxSelect: 1,
      maxSize: 629145600,
      mimeTypes: ["video/mp4"],
      thumbs: [],
      protected: false,
    },
  }))

  collection.schema.addField(new SchemaField({
    system: false,
    id: "arcplaynote1",
    name: "playback_note",
    type: "text",
    required: false,
    options: { min: 0, max: 500, pattern: "" },
  }))

  return dao.saveCollection(collection)
}, (db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("archives")
  ;["playback_status", "playback_file", "playback_note"].forEach((n) => {
    const f = collection.schema.getFieldByName(n)
    if (f) collection.schema.removeField(f.id)
  })
  return dao.saveCollection(collection)
})
