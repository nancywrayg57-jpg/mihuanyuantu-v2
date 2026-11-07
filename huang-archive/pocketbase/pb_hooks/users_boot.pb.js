/// <reference path="../pb_data/types.d.ts" />

// Single bootstrap patch for users auth options (avoid competing hooks / migration churn).
onAfterBootstrap((e) => {
  try {
    const dao = $app.dao()
    const collection = dao.findCollectionByNameOrId("users")
    const wantManage = '@request.auth.role = "admin"'
    const need =
      collection.options.minPasswordLength !== 6 ||
      collection.options.manageRule !== wantManage ||
      collection.createRule !== wantManage
    if (!need) return

    collection.options.minPasswordLength = 6
    collection.options.allowEmailAuth = true
    collection.options.allowUsernameAuth = true
    collection.options.allowOAuth2Auth = false
    collection.options.requireEmail = true
    collection.options.manageRule = wantManage
    collection.createRule = wantManage
    collection.updateRule = 'id = @request.auth.id || @request.auth.role = "admin"'
    dao.saveCollection(collection)
    console.log("users_boot: minPasswordLength=6 manageRule/createRule=admin")
  } catch (err) {
    console.log("users_boot hook error:", err)
  }
})
