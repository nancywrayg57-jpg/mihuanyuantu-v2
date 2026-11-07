/// <reference path="../pb_data/types.d.ts" />

// Chunked / resumable upload (image 30MB / video 600MB / other 100MB).

const LIMITS = {
  image: 30 * 1024 * 1024,
  video: 600 * 1024 * 1024,
  other: 100 * 1024 * 1024,
}
const DEFAULT_CHUNK = 2 * 1024 * 1024
const SESS_ROOT = "/pb/pb_data/upload_sessions"

function kindOf(category, name, mime) {
  const c = String(category || "")
  const n = String(name || "").toLowerCase()
  const t = String(mime || "").toLowerCase()
  if (c === "video" || t.startsWith("video/") || /\.(mp4|mov|webm|m4v|avi|mkv|3gp|mpeg|mpg)$/.test(n)) return "video"
  if (c === "image" || t.startsWith("image/") || /\.(jpe?g|png|gif|webp|heic|heif|avif)$/.test(n)) return "image"
  return "other"
}

function requireUser(c) {
  const info = $apis.requestInfo(c)
  if (!info || !info.authRecord) {
    throw new UnauthorizedError("请先登录")
  }
  return info.authRecord
}

function sessionDir(id) {
  return SESS_ROOT + "/" + id
}

function loadMeta(id) {
  const raw = toString($os.readFile(sessionDir(id) + "/meta.json"))
  return JSON.parse(raw)
}

function saveMeta(id, meta) {
  $os.writeFile(sessionDir(id) + "/meta.json", JSON.stringify(meta))
}

function isNativePlayable(name) {
  return /\.(mp4|m4v|webm)$/i.test(String(name || ""))
}

function safeName(name) {
  return String(name || "file.bin").replace(/[^\w.\-()+]/g, "_")
}

routerAdd(
  "POST",
  "/api/hz/upload/init",
  (c) => {
    try {
      const user = requireUser(c)
      const body = $apis.requestInfo(c).data || {}
      const filename = String(body.filename || "file.bin")
      const size = Number(body.size || 0)
      const mime = String(body.mime || "application/octet-stream")
      const category = String(body.category || "other")
      const chunkSize = Math.max(256 * 1024, Math.min(Number(body.chunkSize || DEFAULT_CHUNK), 5 * 1024 * 1024))
      if (!size || size < 1) return c.json(400, { message: "无效文件大小" })

      const kind = kindOf(category, filename, mime)
      const max = LIMITS[kind]
      if (size > max) {
        const mb = Math.round(max / 1024 / 1024)
        const label = kind === "image" ? "图片" : kind === "video" ? "视频" : "文件"
        return c.json(400, { message: label + "不能超过 " + mb + "MB" })
      }

      const sessionId = $security.randomString(24)
      const totalChunks = Math.ceil(size / chunkSize)
      $os.mkdirAll(sessionDir(sessionId), 0o755)

      const meta = {
        id: sessionId,
        userId: user.id,
        userName: user.getString("display_name") || user.getString("username") || "",
        filename,
        size,
        mime,
        category,
        chunkSize,
        totalChunks,
        received: [],
        title: String(body.title || ""),
        occurred_time: String(body.occurred_time || ""),
        related_persons: String(body.related_persons || ""),
        description: String(body.description || ""),
        external_link: String(body.external_link || ""),
        created: new Date().toISOString(),
      }
      saveMeta(sessionId, meta)
      return c.json(200, { sessionId, chunkSize, totalChunks, size })
    } catch (e) {
      const msg = (e && e.message) || "初始化上传失败"
      return c.json(String(msg).includes("登录") ? 401 : 500, { message: msg })
    }
  },
  $apis.requireRecordAuth(),
)

routerAdd(
  "POST",
  "/api/hz/upload/chunk/:sessionId/:index",
  (c) => {
    try {
      const user = requireUser(c)
      const sessionId = c.pathParam("sessionId")
      const index = Number(c.pathParam("index"))
      const meta = loadMeta(sessionId)
      if (meta.userId !== user.id) return c.json(403, { message: "无权访问该上传会话" })
      if (index < 0 || index >= meta.totalChunks) return c.json(400, { message: "分片序号无效" })

      const files = c.findUploadedFiles("chunk")
      if (!files || !files.length) return c.json(400, { message: "缺少分片文件 chunk" })
      const dest = sessionDir(sessionId) + "/chunk_" + index
      $filesystem.upload(dest, files[0])

      if (meta.received.indexOf(index) < 0) {
        meta.received.push(index)
        meta.received.sort((a, b) => a - b)
        saveMeta(sessionId, meta)
      }
      return c.json(200, {
        sessionId,
        index,
        received: meta.received.length,
        totalChunks: meta.totalChunks,
      })
    } catch (e) {
      console.log("chunk upload error:", e)
      return c.json(500, { message: (e && e.message) || "分片上传失败" })
    }
  },
  $apis.requireRecordAuth(),
)

routerAdd(
  "GET",
  "/api/hz/upload/status/:sessionId",
  (c) => {
    try {
      const user = requireUser(c)
      const sessionId = c.pathParam("sessionId")
      const meta = loadMeta(sessionId)
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
  },
  $apis.requireRecordAuth(),
)

routerAdd(
  "POST",
  "/api/hz/upload/complete/:sessionId",
  (c) => {
    try {
      const user = requireUser(c)
      const sessionId = c.pathParam("sessionId")
      const meta = loadMeta(sessionId)
      if (meta.userId !== user.id) return c.json(403, { message: "无权访问该上传会话" })
      if ((meta.received || []).length < meta.totalChunks) {
        return c.json(400, {
          message: "分片未传完",
          received: meta.received.length,
          totalChunks: meta.totalChunks,
        })
      }

      const body = ($apis.requestInfo(c).data) || {}
      if (body.title) meta.title = String(body.title)
      if (body.occurred_time) meta.occurred_time = String(body.occurred_time)
      if (body.related_persons) meta.related_persons = String(body.related_persons)
      if (body.description != null) meta.description = String(body.description)

      if (!meta.title || !meta.occurred_time || !meta.related_persons) {
        return c.json(400, { message: "请填写标题、发生时间与关系人" })
      }

      const dir = sessionDir(sessionId)
      const assembled = dir + "/assembled_" + safeName(meta.filename)

      const cmd = $os.cmd(
        "sh",
        "-c",
        'rm -f "' + assembled + '"; i=0; while [ $i -lt ' + meta.totalChunks + ' ]; do cat "' + dir + '/chunk_$i" >> "' + assembled + '"; i=$((i+1)); done',
      )
      if (cmd.run() !== 0) return c.json(500, { message: "合并分片失败" })

      const collection = $app.dao().findCollectionByNameOrId("archives")
      const record = new Record(collection)
      record.set("title", meta.title)
      record.set("category", meta.category)
      record.set("occurred_time", meta.occurred_time)
      record.set("related_persons", meta.related_persons)
      record.set("description", meta.description || "")
      record.set("uploader", meta.userId)
      record.set("uploader_name", meta.userName)
      record.set("likes_count", 0)
      if (meta.external_link) record.set("external_link", meta.external_link)

      const f = $filesystem.fileFromPath(assembled)
      try {
        f.name = meta.filename
      } catch (_) {}
      record.set("media_files", f)

      if (meta.category === "video") {
        if (isNativePlayable(meta.filename)) {
          record.set("playback_status", "native")
          record.set("playback_note", "浏览器可直接播放原文件")
        } else {
          record.set("playback_status", "pending")
          record.set("playback_note", "正在转码为微信友好 MP4，请稍候…")
        }
      } else {
        record.set("playback_status", "none")
      }

      $app.dao().saveRecord(record)

      try {
        const entries = $os.readDir(dir)
        for (let i = 0; i < entries.length; i++) {
          $os.remove(dir + "/" + entries[i].name())
        }
        $os.remove(dir)
      } catch (_) {}

      return c.json(200, {
        id: record.id,
        collectionId: collection.id,
        collectionName: collection.name,
        title: record.get("title"),
        category: record.get("category"),
        media_files: record.get("media_files"),
        playback_status: record.get("playback_status"),
        playback_file: record.get("playback_file"),
        playback_note: record.get("playback_note"),
        occurred_time: record.get("occurred_time"),
        related_persons: record.get("related_persons"),
        description: record.get("description"),
        uploader: record.get("uploader"),
        uploader_name: record.get("uploader_name"),
        likes_count: record.get("likes_count"),
        created: record.get("created"),
        updated: record.get("updated"),
      })
    } catch (e) {
      console.log("upload complete error:", e)
      return c.json(500, { message: (e && e.message) || "合并上传失败" })
    }
  },
  $apis.requireRecordAuth(),
)

routerAdd(
  "DELETE",
  "/api/hz/upload/session/:sessionId",
  (c) => {
    try {
      const user = requireUser(c)
      const sessionId = c.pathParam("sessionId")
      const meta = loadMeta(sessionId)
      if (meta.userId !== user.id) return c.json(403, { message: "无权访问该上传会话" })
      const dir = sessionDir(sessionId)
      try {
        const entries = $os.readDir(dir)
        for (let i = 0; i < entries.length; i++) $os.remove(dir + "/" + entries[i].name())
        $os.remove(dir)
      } catch (_) {}
      return c.json(200, { ok: true })
    } catch (e) {
      return c.json(404, { message: "会话不存在" })
    }
  },
  $apis.requireRecordAuth(),
)
