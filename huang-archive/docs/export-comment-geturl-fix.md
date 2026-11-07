# 导出权限 / 删除留言 / getURL 警告

## 1) 普通用户关闭导出
- 备份导出按钮仅 `auth.isAdmin` 可见；`doExport` 再拦一层「仅管理员可导出」。
- 端测：管理员有按钮，成员无按钮。

## 2) 删除评论（追忆）
- Migration 0017：`memories.deleteRule = admin || author = auth.id`
- 卡片留言区：本人或管理员可见「删除」。
- 端测：成员删自己 204；管理员删他人 204；成员删管理员留言 404。

## 3) `getUrl` 控制台警告
- 原因：PocketBase JS SDK ≥0.22 将 `files.getUrl` 标为废弃，调用即 `console.warn`，应使用 `files.getURL`。
- 修复：业务代码全部改为 `getURL`（`ArchiveCard` / `mediaPrepare` / `videoPlayback` / `exportArchives`）。
- 打包内仍保留 SDK 自带的废弃别名定义，但不再被调用；端测加载首页无相关 warning。
