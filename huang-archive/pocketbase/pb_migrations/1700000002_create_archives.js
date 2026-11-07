/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const users = dao.findCollectionByNameOrId("users")

  const collection = new Collection({
    id: "archives00001",
    name: "archives",
    type: "base",
    system: false,
    listRule: '@request.auth.id != ""',
    viewRule: '@request.auth.id != ""',
    createRule: '@request.auth.id != ""',
    updateRule: '@request.auth.role = "admin" || (uploader = @request.auth.id && @request.data.category:isset = false && @request.data.media_files:isset = false && @request.data.external_link:isset = false && @request.data.uploader:isset = false && @request.data.uploader_name:isset = false && @request.data.likes_count:isset = false)',
    deleteRule: '@request.auth.role = "admin"',
    schema: [
      {
        system: false,
        id: "arctitle001",
        name: "title",
        type: "text",
        required: true,
        options: { min: 1, max: 200, pattern: "" },
      },
      {
        system: false,
        id: "arccat00001",
        name: "category",
        type: "select",
        required: true,
        options: {
          maxSelect: 1,
          values: ["image", "video", "scan", "link", "audio", "other"],
        },
      },
      {
        system: false,
        id: "arcmedia001",
        name: "media_files",
        type: "file",
        required: false,
        options: {
          maxSelect: 9,
          maxSize: 629145600,
          mimeTypes: [
            "image/jpeg",
            "image/jpg",
            "image/pjpeg",
            "image/png",
            "image/webp",
            "image/gif",
            "image/heic",
            "image/heif",
            "image/avif",
            "image/bmp",
            "image/tiff",
            "video/mp4",
            "video/quicktime",
            "video/webm",
            "video/x-m4v",
            "application/pdf",
            "audio/mpeg",
            "audio/mp4",
            "audio/x-m4a",
            "audio/wav",
            "audio/wave",
            "audio/x-wav",
            "audio/webm",
            "audio/ogg",
            "application/octet-stream",
          ],
          thumbs: ["600x0"],
          protected: false,
        },
      },
      {
        system: false,
        id: "arclink0001",
        name: "external_link",
        type: "url",
        required: false,
        options: { exceptDomains: null, onlyDomains: null },
      },
      {
        system: false,
        id: "arctime0001",
        name: "occurred_time",
        type: "text",
        required: true,
        options: { min: 1, max: 100, pattern: "" },
      },
      {
        system: false,
        id: "arcrel00001",
        name: "related_persons",
        type: "text",
        required: true,
        options: { min: 1, max: 200, pattern: "" },
      },
      {
        system: false,
        id: "arcdesc0001",
        name: "description",
        type: "text",
        required: false,
        options: { min: null, max: 5000, pattern: "" },
      },
      {
        system: false,
        id: "arcupldr001",
        name: "uploader",
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
        id: "arcupname01",
        name: "uploader_name",
        type: "text",
        required: false,
        options: { min: null, max: 64, pattern: "" },
      },
      {
        system: false,
        id: "arclikes001",
        name: "likes_count",
        type: "number",
        required: false,
        options: { min: 0, max: null, noDecimal: true },
      },
    ],
    indexes: [],
  })

  return dao.saveCollection(collection)
}, (db) => {
  const dao = new Dao(db)
  try {
    const collection = dao.findCollectionByNameOrId("archives00001")
    return dao.deleteCollection(collection)
  } catch (_) {}
})
