/// <reference path="../pb_data/types.d.ts" />

// Chunked / resumable upload. All logic inlined inside routerAdd (PB JSVM
// closures do not reliably see sibling function declarations).

routerAdd("POST", "/api/hz/upload/init", (c) => {
  try {
    const info = $apis.requestInfo(c)
    const user = info && info.authRecord
    if (!user) return c.json(401, { message: "请先登录" })

    const body = info.data || {}
    const filename = String(body.filename || "file.bin")
    const size = Number(body.size || 0)
    const mime = String(body.mime || "application/octet-stream")
    const category = String(body.category || "other")
    const chunkSize = Math.max(256 * 1024, Math.min(Number(body.chunkSize || 2 * 1024 * 1024), 5 * 1024 * 1024))
    if (!size || size < 1) return c.json(400, { message: "无效文件大小" })

    const n = filename.toLowerCase()
    const t = mime.toLowerCase()
    let kind = "other"
    if (category === "video" || t.startsWith("video/") || /\.(mp4|mov|webm|m4v|avi|mkv|3gp|mpeg|mpg)$/.test(n)) kind = "video"
    else if (category === "image" || t.startsWith("image/") || /\.(jpe?g|png|gif|webp|heic|heif|avif)$/.test(n)) kind = "image"

    const limits = { image: 30 * 1024 * 1024, video: 600 * 1024 * 1024, other: 100 * 1024 * 1024 }
    const max = limits[kind]
    if (size > max) {
      const mb = Math.round(max / 1024 / 1024)
      const label = kind === "image" ? "图片" : kind === "video" ? "视频" : "文件"
      return c.json(400, { message: label + "不能超过 " + mb + "MB" })
    }

    const sessionId = $security.randomString(24)
    const totalChunks = Math.ceil(size / chunkSize)
    const dir = "/pb/pb_data/upload_sessions/" + sessionId
    $os.mkdirAll(dir, 0o755)

    const meta = {
      id: sessionId,
      userId: user.id,
      userName: user.getString("display_name") || user.getString("username") || "",
      filename, size, mime, category, chunkSize, totalChunks,
      received: [],
      title: String(body.title || ""),
      occurred_time: String(body.occurred_time || ""),
      related_persons: String(body.related_persons || ""),
      description: String(body.description || ""),
      external_link: String(body.external_link || ""),
    }
    $os.writeFile(dir + "/meta.json", JSON.stringify(meta))
    return c.json(200, { sessionId, chunkSize, totalChunks, size })
  } catch (e) {
    console.log("upload init error:", e)
    return c.json(500, { message: (e && e.message) || "初始化上传失败" })
  }
}, $apis.requireRecordAuth())

routerAdd("POST", "/api/hz/upload/chunk/:sessionId/:index", (c) => {
  try {
    const info = $apis.requestInfo(c)
    const user = info && info.authRecord
    if (!user) return c.json(401, { message: "请先登录" })

    const sessionId = c.pathParam("sessionId")
    const index = Number(c.pathParam("index"))
    const dir = "/pb/pb_data/upload_sessions/" + sessionId
    const meta = JSON.parse(toString($os.readFile(dir + "/meta.json")))
    if (meta.userId !== user.id) return c.json(403, { message: "无权访问该上传会话" })
    if (index < 0 || index >= meta.totalChunks) return c.json(400, { message: "分片序号无效" })

    const fh = c.formFile("chunk")
    if (!fh) return c.json(400, { message: "缺少分片文件 chunk" })
    // PB 0.22: persist via storage abstraction (cmd.run() returns void on success)
    const file = $filesystem.fileFromMultipart(fh)
    const fs = $app.newFilesystem()
    const key = "hz_chunks/" + sessionId + "/chunk_" + index
    try {
      fs.uploadFile(file, key)
    } finally {
      fs.close()
    }
    try {
      $os.cmd("cp", "-f", "/pb/pb_data/storage/" + key, dir + "/chunk_" + index).run()
    } catch (e) {
      return c.json(500, { message: "分片落盘失败" })
    }

    if (meta.received.indexOf(index) < 0) {
      meta.received.push(index)
      meta.received.sort((a, b) => a - b)
      $os.writeFile(dir + "/meta.json", JSON.stringify(meta))
    }
    return c.json(200, {
      sessionId, index,
      received: meta.received.length,
      totalChunks: meta.totalChunks,
    })
  } catch (e) {
    console.log("chunk upload error:", e)
    return c.json(500, { message: (e && e.message) || "分片上传失败" })
  }
}, $apis.requireRecordAuth())

routerAdd("GET", "/api/hz/upload/status/:sessionId", (c) => {
  try {
    const info = $apis.requestInfo(c)
    const user = info && info.authRecord
    if (!user) return c.json(401, { message: "请先登录" })
    const sessionId = c.pathParam("sessionId")
    const dir = "/pb/pb_data/upload_sessions/" + sessionId
    const meta = JSON.parse(toString($os.readFile(dir + "/meta.json")))
    if (meta.userId !== user.id) return c.json(403, { message: "无权访问该上传会话" })
    return c.json(200, {
      sessionId,
      received: meta.received,
      totalChunks: meta.totalChunks,
      size: meta.size,
      filename: meta.filename,
    })
  } catch (e) {
    return c.json(404, { message: "上传会话不存在" })
  }
}, $apis.requireRecordAuth())

routerAdd("POST", "/api/hz/upload/complete/:sessionId", (c) => {
  try {
    const info = $apis.requestInfo(c)
    const user = info && info.authRecord
    if (!user) return c.json(401, { message: "请先登录" })

    const sessionId = c.pathParam("sessionId")
    const dir = "/pb/pb_data/upload_sessions/" + sessionId
    const meta = JSON.parse(toString($os.readFile(dir + "/meta.json")))
    if (meta.userId !== user.id) return c.json(403, { message: "无权访问该上传会话" })
    if ((meta.received || []).length < meta.totalChunks) {
      return c.json(400, {
        message: "分片未传完",
        received: meta.received.length,
        totalChunks: meta.totalChunks,
      })
    }

    const body = info.data || {}
    if (body.title) meta.title = String(body.title)
    if (body.occurred_time) meta.occurred_time = String(body.occurred_time)
    if (body.related_persons) meta.related_persons = String(body.related_persons)
    if (body.description != null) meta.description = String(body.description)
    if (!meta.title || !meta.occurred_time || !meta.related_persons) {
      return c.json(400, { message: "请填写标题、发生时间与关系人" })
    }

    const safe = String(meta.filename || "file.bin").replace(/[^\w.\-()+]/g, "_")
    const assembled = dir + "/assembled_" + safe
    try {
      $os.cmd(
        "sh", "-c",
        'rm -f "' + assembled + '"; i=0; while [ $i -lt ' + meta.totalChunks + ' ]; do cat "' + dir + '/chunk_$i" >> "' + assembled + '"; i=$((i+1)); done',
      ).run()
    } catch (e) {
      return c.json(500, { message: "合并分片失败" })
    }

    // Create via internal HTTP multipart — dao fileFromPath attach is unreliable in this PB build
    const safeName = String(meta.filename || "file.bin").replace(/[^\w.\-()+]/g, "_")
    const named = dir + "/" + safeName
    try { $os.cmd("cp", "-f", assembled, named).run() } catch (e) {}

    let playbackStatus = "none"
    let playbackNote = ""
    if (meta.category === "video") {
      if (/\.(mp4|m4v|webm)$/i.test(String(meta.filename || ""))) {
        playbackStatus = "native"
        playbackNote = "浏览器可直接播放原文件"
      } else {
        playbackStatus = "pending"
        playbackNote = "正在转码为微信友好 MP4，请稍候…"
      }
    }

    let authHeader = ""
    try { authHeader = c.request().header.get("Authorization") || "" } catch (e) {}
    if (!authHeader && info.headers) {
      authHeader = info.headers["Authorization"] || info.headers["authorization"] || ""
    }
    const outFile = dir + "/create_result.json"
    const mime = meta.mime || "application/octet-stream"
    const sh =
      'curl -fsS -X POST "http://127.0.0.1:8090/api/collections/archives/records" ' +
      '-H "Authorization: ' + authHeader.replace(/"/g, "") + '" ' +
      '-F "title=' + meta.title.replace(/"/g, "") + '" ' +
      '-F "category=' + meta.category + '" ' +
      '-F "occurred_time=' + meta.occurred_time + '" ' +
      '-F "related_persons=' + meta.related_persons.replace(/"/g, "") + '" ' +
      '-F "description=' + String(meta.description || "").replace(/"/g, "") + '" ' +
      '-F "uploader=' + meta.userId + '" ' +
      '-F "uploader_name=' + String(meta.userName || "").replace(/"/g, "") + '" ' +
      '-F "likes_count=0" ' +
      '-F "playback_status=' + playbackStatus + '" ' +
      '-F "playback_note=' + playbackNote.replace(/"/g, "") + '" ' +
      (meta.external_link ? '-F "external_link=' + meta.external_link + '" ' : "") +
      '-F "media_files=@' + named + ';type=' + mime + ';filename=' + safeName + '" ' +
      '> "' + outFile + '"'
    try {
      $os.cmd("sh", "-c", sh).run()
    } catch (e) {
      return c.json(500, { message: "创建档案失败: " + ((e && e.message) || "") })
    }

    let created
    try {
      created = JSON.parse(toString($os.readFile(outFile)))
    } catch (e) {
      return c.json(500, { message: "创建档案响应无效" })
    }
    if (!created || !created.id) {
      return c.json(500, { message: (created && created.message) || "创建档案失败" })
    }

    try {
      const entries = $os.readDir(dir)
      for (let i = 0; i < entries.length; i++) $os.remove(dir + "/" + entries[i].name())
      $os.remove(dir)
    } catch (e) {}
    try {
      const fs = $app.newFilesystem()
      try { fs.deletePrefix("hz_chunks/" + sessionId + "/") } catch (e2) {}
      fs.close()
    } catch (e) {}

    return c.json(200, created)
  } catch (e) {
    console.log("upload complete error:", e)
    return c.json(500, { message: (e && e.message) || "合并上传失败" })
  }
}, $apis.requireRecordAuth())

routerAdd("DELETE", "/api/hz/upload/session/:sessionId", (c) => {
  try {
    const info = $apis.requestInfo(c)
    const user = info && info.authRecord
    if (!user) return c.json(401, { message: "请先登录" })
    const sessionId = c.pathParam("sessionId")
    const dir = "/pb/pb_data/upload_sessions/" + sessionId
    const meta = JSON.parse(toString($os.readFile(dir + "/meta.json")))
    if (meta.userId !== user.id) return c.json(403, { message: "无权访问该上传会话" })
    try {
      const entries = $os.readDir(dir)
      for (let i = 0; i < entries.length; i++) $os.remove(dir + "/" + entries[i].name())
      $os.remove(dir)
    } catch (e) {}
    return c.json(200, { ok: true })
  } catch (e) {
    return c.json(404, { message: "会话不存在" })
  }
}, $apis.requireRecordAuth())
