/// <reference path="../pb_data/types.d.ts" />

// Ensure minPasswordLength=6 after boot (idempotent)
onAfterBootstrap((e) => {
  try {
    const dao = $app.dao()
    const collection = dao.findCollectionByNameOrId("users")
    if (collection.options.minPasswordLength !== 6) {
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
      dao.saveCollection(collection)
      console.log("patched users.minPasswordLength -> 6")
    }
  } catch (err) {
    console.log("min_password hook error:", err)
  }
})
