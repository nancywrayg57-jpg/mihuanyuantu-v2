/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("users")

  const people = [
    {
      display_name: "黄祥财",
      email: "huangxiangcai@huangzhisong.com",
      username: "huangxiangcai",
      password: "3599263",
      role: "admin",
      relation: "长子",
    },
    { display_name: "黄纲生", email: "user1@huangzhisong.com", username: "huanggangsheng", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄成生", email: "user2@huangzhisong.com", username: "huangchengsheng", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄爱眉", email: "user3@huangzhisong.com", username: "huangaimei", password: "hzs1933", role: "member", relation: "" },
    { display_name: "张银财", email: "user4@huangzhisong.com", username: "zhangyincai", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄爱秀", email: "user5@huangzhisong.com", username: "huangaixiu", password: "hzs1933", role: "member", relation: "" },
    { display_name: "吴雨齐", email: "user6@huangzhisong.com", username: "wuyuqi", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄纲富", email: "user7@huangzhisong.com", username: "huanggangfu", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄纲兴", email: "user8@huangzhisong.com", username: "huanggangxing", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄纲财", email: "user9@huangzhisong.com", username: "huanggangcai", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄纲平", email: "user10@huangzhisong.com", username: "huanggangping", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄祥贵", email: "user11@huangzhisong.com", username: "huangxianggui", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄祥文", email: "user12@huangzhisong.com", username: "huangxiangwen", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄祥明", email: "user13@huangzhisong.com", username: "huangxiangming", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄祥健", email: "user14@huangzhisong.com", username: "huangxiangjian", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄祥鑫", email: "user15@huangzhisong.com", username: "huangxiangxin", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄祥琳", email: "user16@huangzhisong.com", username: "huangxianglin", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄祥瑞", email: "user17@huangzhisong.com", username: "huangxiangrui", password: "hzs1933", role: "member", relation: "" },
    { display_name: "张惠", email: "user18@huangzhisong.com", username: "zhanghui", password: "hzs1933", role: "member", relation: "" },
    { display_name: "吴玲玲", email: "user19@huangzhisong.com", username: "wulingling", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄祥伟", email: "user20@huangzhisong.com", username: "huangxiangwei", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄祥妹", email: "user21@huangzhisong.com", username: "huangxiangmei", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄媛媛", email: "user22@huangzhisong.com", username: "huangyuanyuan", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄晓芳", email: "user23@huangzhisong.com", username: "huangxiaofang", password: "hzs1933", role: "member", relation: "" },
    { display_name: "黄嘉颖", email: "user24@huangzhisong.com", username: "huangjiaying", password: "hzs1933", role: "member", relation: "" },
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
    record.set("relation", p.relation || "")
    record.setPassword(p.password)
    dao.saveRecord(record)
  }
}, (db) => {
  const dao = new Dao(db)
  const emails = ["huangxiangcai@huangzhisong.com"]
  for (let i = 1; i <= 24; i++) emails.push("user" + i + "@huangzhisong.com")
  for (const email of emails) {
    try {
      const record = dao.findAuthRecordByEmail("users", email)
      dao.deleteRecord(record)
    } catch (_) {}
  }
})
