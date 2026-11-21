/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const users = dao.findCollectionByNameOrId("users")
  const archives = dao.findCollectionByNameOrId("archives")

  const collection = new Collection({
    id: "memories00001",
    name: "memories",
    type: "base",
    system: false,
    listRule: '@request.auth.id != ""',
    viewRule: '@request.auth.id != ""',
    createRule: '@request.auth.id != ""',
    updateRule: '@request.auth.id != ""',
    deleteRule: '@request.auth.role = "admin"',
    schema: [
      {
        system: false,
        id: "memarc00001",
        name: "archive_id",
        type: "relation",
        required: true,
        options: {
          collectionId: archives.id,
          cascadeDelete: true,
          minSelect: null,
          maxSelect: 1,
          displayFields: null,
        },
      },
      {
        system: false,
        id: "memauth0001",
        name: "author",
        type: "relation",
        required: true,
        options: {
          collectionId: users.id,
          cascadeDelete: false,
          minSelect: null,
          maxSelect: 1,
          displayFields: ["display_name"],
        },
      },
      {
        system: false,
        id: "memaname001",
        name: "author_name",
        type: "text",
        required: true,
        options: { min: 1, max: 64, pattern: "" },
      },
      {
        system: false,
        id: "memctype001",
        name: "content_type",
        type: "select",
        required: true,
        options: {
          maxSelect: 1,
          values: ["text", "voice"],
        },
      },
      {
        system: false,
        id: "memtext0001",
        name: "text_content",
        type: "text",
        required: false,
        options: { min: null, max: 5000, pattern: "" },
      },
      {
        system: false,
        id: "memvoice001",
        name: "voice_file",
        type: "file",
        required: false,
        options: {
          maxSelect: 1,
          maxSize: 52428800,
          mimeTypes: [
            "audio/webm",
            "audio/mp4",
            "audio/mpeg",
            "audio/wav",
            "audio/ogg",
            "audio/x-m4a",
            "video/webm",
            "video/mp4",
          ],
          thumbs: [],
          protected: false,
        },
      },
      {
        system: false,
        id: "memvdur0001",
        name: "voice_duration",
        type: "number",
        required: false,
        options: { min: 0, max: null, noDecimal: false },
      },
    ],
    indexes: [],
  })

  return dao.saveCollection(collection)
}, (db) => {
  const dao = new Dao(db)
  try {
    const collection = dao.findCollectionByNameOrId("memories00001")
    return dao.deleteCollection(collection)
  } catch (_) {}
})
