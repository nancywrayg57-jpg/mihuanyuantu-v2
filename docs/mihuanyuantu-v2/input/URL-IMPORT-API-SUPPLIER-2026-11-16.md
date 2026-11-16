# URL 导入 · API 型供应商

| 字段 | 内容 |
| --- | --- |
| 日期 | 2026-11-16 |
| 分支 | `cursor/url-import-api-supplier-9973` |
| 范围 | 商家后台 `/realphotos/imports`；不做对外业务 API；不做清单勾选；不做本机先上传图床 |
| S7 | 搁置 |

## 行为

- 粘贴完整 URL：`/images/<file>` 或 `/api/images/<file>` 均可。
- 运行时统一 `GET {base}/api/images/<file>`。
- 启用条件：`duty=import` 合同已启用且有有效 Base URL（不再依赖 `REALPHOTOS_IMPORT_STAGING`）。
- 管理端「模型 API」可配置/启停 `URL导入`；无需 API Key。
- 默认/验收基址：`http://47.85.47.252`（可用 `REALPHOTOS_IMPORT_BASE_URL` 兜底）。

## 联调站接口（摘要）

- `GET /api/images` 清单
- `GET /api/images/<文件名>` 下载（本功能使用）
- `POST /upload` 上传（本单商家页不使用）
