/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("users")
  collection.options = {
    allowEmailAuth: true,
    allowOAuth2Auth: false,
    allowUsernameAuth: true,
    exceptEmailDomains: null,
    manageRule: '@request.auth.role = "admin"',
    minPasswordLength: 6,
    onlyEmailDomains: null,
    requireEmail: true,
  }
  collection.createRule = '@request.auth.role = "admin"'
  return dao.saveCollection(collection)
}, (db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("users")
  collection.options = {
    allowEmailAuth: true,
    allowOAuth2Auth: false,
    allowUsernameAuth: true,
    exceptEmailDomains: null,
    manageRule: null,
    minPasswordLength: 6,
    onlyEmailDomains: null,
    requireEmail: true,
  }
  return dao.saveCollection(collection)
})
