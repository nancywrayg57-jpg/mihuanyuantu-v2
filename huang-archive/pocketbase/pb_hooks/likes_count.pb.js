/// <reference path="../pb_data/types.d.ts" />

// Keep archives.likes_count in sync without clients PATCHing archives (RBAC-safe).

onRecordAfterCreateRequest((e) => {
  try {
    const archiveId = e.record.get("archive_id")
    if (!archiveId) return
    const dao = $app.dao()
    const archive = dao.findRecordById("archives", archiveId)
    const n = Number(archive.get("likes_count") || 0)
    archive.set("likes_count", n + 1)
    dao.saveRecord(archive)
  } catch (err) {
    console.log("likes_count create hook:", err)
  }
}, "archive_likes")

onRecordAfterDeleteRequest((e) => {
  try {
    const archiveId = e.record.get("archive_id")
    if (!archiveId) return
    const dao = $app.dao()
    const archive = dao.findRecordById("archives", archiveId)
    const n = Math.max(0, Number(archive.get("likes_count") || 0) - 1)
    archive.set("likes_count", n)
    dao.saveRecord(archive)
  } catch (err) {
    console.log("likes_count delete hook:", err)
  }
}, "archive_likes")
