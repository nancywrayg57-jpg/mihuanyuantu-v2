/// <reference path="../pb_data/types.d.ts" />

// Single bootstrap patch for users auth options (idempotent).
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

    // Replace whole options object — nested property assign fails on host objects.
    collection.options = {
      allowEmailAuth: true,
      allowOAuth2Auth: false,
      allowUsernameAuth: true,
      exceptEmailDomains: null,
      manageRule: wantManage,
      minPasswordLength: 6,
      onlyEmailDomains: null,
      requireEmail: true,
    }
    collection.createRule = wantManage
    collection.updateRule = 'id = @request.auth.id || @request.auth.role = "admin"'
    dao.saveCollection(collection)
    console.log("users_boot: minPasswordLength=6 manageRule/createRule=admin")
  } catch (err) {
    console.log("users_boot hook error:", err)
  }
})
