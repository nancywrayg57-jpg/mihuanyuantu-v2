/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const users = dao.findCollectionByNameOrId("users")
  const archives = dao.findCollectionByNameOrId("archives")

  const collection = new Collection({
    id: "arclikes00001",
    name: "archive_likes",
    type: "base",
    system: false,
    listRule: '@request.auth.id != ""',
    viewRule: '@request.auth.id != ""',
    createRule: '@request.auth.id != ""',
    updateRule: 'user_id = @request.auth.id',
    deleteRule: 'user_id = @request.auth.id || @request.auth.role = "admin"',
    schema: [
      {
        system: false,
        id: "likearc0001",
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
        id: "likeusr0001",
        name: "user_id",
        type: "relation",
        required: true,
        options: {
          collectionId: users.id,
          cascadeDelete: true,
          minSelect: null,
          maxSelect: 1,
          displayFields: null,
        },
      },
    ],
    indexes: [
      "CREATE UNIQUE INDEX idx_archive_likes_unique ON archive_likes (archive_id, user_id)",
    ],
  })

  return dao.saveCollection(collection)
}, (db) => {
  const dao = new Dao(db)
  try {
    const collection = dao.findCollectionByNameOrId("arclikes00001")
    return dao.deleteCollection(collection)
  } catch (_) {}
})
