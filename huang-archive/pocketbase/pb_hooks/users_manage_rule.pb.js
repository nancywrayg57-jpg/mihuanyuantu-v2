/// <reference path="../pb_data/types.d.ts" />

onAfterBootstrap((e) => {
  try {
    const dao = $app.dao()
    const collection = dao.findCollectionByNameOrId("users")
    const want = '@request.auth.role = "admin"'
    if (collection.options.manageRule !== want || collection.createRule !== want) {
      collection.options = {
        allowEmailAuth: true,
        allowOAuth2Auth: false,
        allowUsernameAuth: true,
        exceptEmailDomains: null,
        manageRule: want,
        minPasswordLength: 6,
        onlyEmailDomains: null,
        requireEmail: true,
      }
      collection.createRule = want
      collection.updateRule = 'id = @request.auth.id || @request.auth.role = "admin"'
      dao.saveCollection(collection)
      console.log("patched users.manageRule/createRule for admin member mgmt")
    }
  } catch (err) {
    console.log("users_manage_rule hook error:", err)
  }
})
