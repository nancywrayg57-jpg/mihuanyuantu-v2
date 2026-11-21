/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("users")

  const people = [
    {
      display_name: "张建华",
      email: "user25@huangzhisong.com",
      username: "zhangjianhua",
      password: "hzs1933",
      role: "member",
      relation: "maternal_grandfather",
    },
    {
      display_name: "吴泽强",
      email: "user26@huangzhisong.com",
      username: "wuzeqiang",
      password: "hzs1933",
      role: "member",
      relation: "maternal_grandfather",
    },
  ]

  for (const p of people) {
    let existing = null
    try {
      existing = dao.findAuthRecordByEmail("users", p.email)
    } catch (_) {}
    if (existing) continue

    const record = new Record(collection)
    record.set("email", p.email)
    record.set("username", p.username)
    record.set("emailVisibility", true)
    record.set("verified", true)
    record.set("display_name", p.display_name)
    record.set("role", p.role)
    record.set("relation", p.relation)
    record.setPassword(p.password)
    dao.saveRecord(record)
  }
}, (db) => {
  const dao = new Dao(db)
  for (const email of ["user25@huangzhisong.com", "user26@huangzhisong.com"]) {
    try {
      const record = dao.findAuthRecordByEmail("users", email)
      dao.deleteRecord(record)
    } catch (_) {}
  }
})
