# 紧急修复：管理员上传 `Failed to create record`

## 结论

管理员视图图片上传已修复并部署至 `https://huangzhisong.com`。UI 上传队列现显示中文「完成」，不再透出英文 `Failed to create record`。

## 根因

1. **前端队列绕过中文错误映射**  
   `uploadQueue.js` 使用 `e?.message`，PocketBase `ClientResponseError` 原文为 `Failed to create record.`，用户直接看到英文。
2. **校验失败时字段信息未中文化**  
   缺必填（如关系人）、MIME 不支持（如 BMP）时，PB 统一外层消息也是英文；需 `zhError` 解析 `response.data` 字段错误。
3. **分片合并 curl 经 `sh -c` 拼接**  
   标题含引号/`$` 等字符时，内部创建可能失败；已改为 argv + `--form-string`。
4. **MIME 白名单偏窄**  
   `image/bmp` 等常见类型被拒，外层同样是 `Failed to create record.`。

## 修复

| 位置 | 改动 |
|------|------|
| `frontend/src/stores/uploadQueue.js` | `zhError`；必填校验；字段白名单化 |
| `frontend/src/lib/chunkedUpload.js` | MIME 归一化；创建/更新错误中文化 |
| `frontend/src/lib/errors.js` | MIME/必填短语；字段级中文 |
| `frontend/src/components/UploadModal.vue` | 预处理错误走 `zhError` |
| `pocketbase/pb_hooks/upload_chunk.pb.js` | 安全 curl；失败消息中文 |
| `pb_migrations/1700000015_upload_mime_harden.js` | 扩展 BMP/TIFF/音频等 MIME |

## 端测（临时账号）

- 临时管理员：**管六安**（`guanliuan.tmp@…`）
- 临时成员：**测成员甲**（`chengyuan.tmp@…`）
- 全媒体：图片 / 视频 / 录音 / PDF / 光明网链接 — **全部 HTTP 200**
- 分片 + 标题含 `'` — **成功**
- BMP — **成功**（迁移后）
- 回归：登录、点赞、留言、搜索、成员列表、删除 RBAC（仅管理员可删）— **通过**
- 测后：**已删除**临时账号与测试档案（含诊断残留 `[diag]`）

## 截图

见 store `media/`：

- `01-login-home.png` — 管理员已登录主页
- `02-upload-modal.png` — 上传弹窗
- `03-upload-success.png` — 队列「完成 · image」，卡片「紧急修复验收图」
- `04-archive-card.png` / `05-like.png`
- `e2e-upload-emergency-results.json` / `e2e-regression-results.json`

## 部署

已同步 `frontend/dist` 并重建 `huang-pb`（hooks + migration 0015）。健康检查通过。
