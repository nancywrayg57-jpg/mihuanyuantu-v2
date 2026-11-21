/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("users")
  const field = collection.schema.getFieldByName("relation")
  if (!field) return
  field.options.values = [
    "儿子",
    "女儿",
    "儿媳",
    "女婿",
    "孙子",
    "孙女",
    "孙女婿",
    "孙媳",
    "外甥",
    "外甥女",
    "外甥女婿",
    "外甥媳",
    "侄儿",
    "侄女",
    "侄孙",
    "侄孙媳",
    "侄外甥",
    "侄外甥媳",
    "曾孙",
    "曾孙女",
    "曾外孙",
    "曾外甥女",
    "学生",
    "晚辈",
  ]
  return dao.saveCollection(collection)
}, (db) => {
  const dao = new Dao(db)
  const collection = dao.findCollectionByNameOrId("users")
  const field = collection.schema.getFieldByName("relation")
  if (!field) return
  field.options.values = [
    "儿子",
    "女儿",
    "儿媳",
    "女婿",
    "外甥",
    "外甥女",
    "曾孙",
    "曾孙女",
    "曾外孙",
    "曾外甥女",
  ]
  return dao.saveCollection(collection)
})
