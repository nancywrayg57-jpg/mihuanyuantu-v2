# 手机管理员上传失败修复

## 根因

队列报错「上传者：内容不符合要求」对应 PocketBase `uploader` 关系字段校验失败（`validation_missing_rel_records`）。

复现：`FormData` 写入 `String(user对象)` → `"[object Object]"`，关系 ID 无效。手机/微信 WebView 更容易把整份 auth record 当值序列化；并非图片二进制路径被截断。

**影响范围：全部类型**（image / video / audio / pdf / link）——共用 `uploadQueue` → `uploadDirect` / 分片完成写 `uploader`。

## 修复

1. 客户端：不再提交 `uploader`；`resolveRecordId` 防止对象串化；文件名清理
2. 服务端：`archives_uploader.pb.js` 在 create 时用 `authRecord` 强制绑定 uploader / uploader_name
3. Migration 0016：`uploader.required=false`，使缺省字段可走 hook（PB 在 hook 前会拦无效已填值）
4. 中文：`validation_missing_rel` →「关联数据无效，请重新登录后再试」

## 验证

- API：admin「管六安」+ member「测成员乙」五类上传（不传 uploader）全部 200 且 uploader 绑定正确
- 窄视口/微信 UA UI：队列「完成 · image」
- 测后已删临时账号与测试档案
