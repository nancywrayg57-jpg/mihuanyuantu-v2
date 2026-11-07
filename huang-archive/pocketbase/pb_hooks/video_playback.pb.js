/// <reference path="../pb_data/types.d.ts" />

// Mark video archives for native playback or async ffmpeg transcode.

function isNativePlayable(name) {
  const n = String(name || "").toLowerCase()
  return /\.(mp4|m4v|webm)$/.test(n)
}

function markPlayback(record) {
  try {
    if (record.get("category") !== "video") {
      if (!record.get("playback_status")) {
        record.set("playback_status", "none")
        $app.dao().saveRecord(record)
      }
      return
    }
    const files = record.get("media_files") || []
    const first = Array.isArray(files) ? files[0] : files
    if (!first) {
      record.set("playback_status", "failed")
      record.set("playback_note", "未找到视频文件")
      $app.dao().saveRecord(record)
      return
    }
    const status = record.get("playback_status")
    if (status === "ready" || status === "pending") return

    if (isNativePlayable(first)) {
      record.set("playback_status", "native")
      record.set("playback_note", "浏览器可直接播放原文件")
    } else {
      record.set("playback_status", "pending")
      record.set("playback_note", "正在转码为微信友好 MP4，请稍候…")
    }
    $app.dao().saveRecord(record)
  } catch (err) {
    console.log("video_playback mark error:", err)
  }
}

onRecordAfterCreateRequest((e) => {
  markPlayback(e.record)
}, "archives")

onRecordAfterUpdateRequest((e) => {
  // Only re-mark when media changes and not already ready
  try {
    if (e.record.get("category") !== "video") return
    const st = e.record.get("playback_status")
    if (st === "ready" || st === "pending") return
    markPlayback(e.record)
  } catch (err) {
    console.log("video_playback update error:", err)
  }
}, "archives")
