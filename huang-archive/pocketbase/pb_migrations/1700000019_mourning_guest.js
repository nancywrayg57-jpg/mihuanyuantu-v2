/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)

  // Expand users.role with guest
  const users = dao.findCollectionByNameOrId("users")
  const roleField = users.schema.getFieldByName("role")
  if (roleField) {
    roleField.options.values = ["admin", "member", "guest"]
  }
  dao.saveCollection(users)

  // Seed shared 吊唁贵宾 account (password unused by UI; token login via hook)
  const email = "guest@huangzhisong.com"
  let guest = null
  try {
    guest = dao.findAuthRecordByEmail("users", email)
  } catch (_) {}
  if (!guest) {
    guest = new Record(users)
    guest.set("email", email)
    guest.set("username", "mourningguest")
    guest.set("emailVisibility", true)
    guest.set("verified", true)
    guest.set("display_name", "吊唁贵宾")
    guest.set("role", "guest")
    guest.set("disabled", false)
    guest.setPassword("HzsGuest#1933")
    dao.saveRecord(guest)
  } else {
    guest.set("display_name", "吊唁贵宾")
    guest.set("role", "guest")
    guest.set("disabled", false)
    guest.set("verified", true)
    dao.saveRecord(guest)
  }

  // Guests may browse / like / comment — not upload archives
  const archives = dao.findCollectionByNameOrId("archives")
  archives.createRule =
    '@request.auth.id != "" && (@request.auth.role = "admin" || @request.auth.role = "member")'
  dao.saveCollection(archives)
}, (db) => {
  const dao = new Dao(db)
  try {
    const guest = dao.findAuthRecordByEmail("users", "guest@huangzhisong.com")
    dao.deleteRecord(guest)
  } catch (_) {}

  const users = dao.findCollectionByNameOrId("users")
  const roleField = users.schema.getFieldByName("role")
  if (roleField) {
    roleField.options.values = ["admin", "member"]
  }
  dao.saveCollection(users)

  const archives = dao.findCollectionByNameOrId("archives")
  archives.createRule = '@request.auth.id != ""'
  dao.saveCollection(archives)
})
