# 蜜獾原图 v2 · 任务工单

| 字段 | 内容 |
| --- | --- |
| 工单编号 | `OPS-SUPPLIER-KEY-UX-2026-11-13` |
| 创建日期 | 2026-11-13 |
| 执行角色 | 主代理整理工单并分发；子代理实现+端测；主代理审计证据；Owner 审合（**不得自评自合**） |
| 分支 | `cursor/ops-supplier-key-ux-9973`（worktree：`/home/hbs/hbs-projects/mihuanyuantu-v2-ops-supplier-ux`） |
| 基线 | `origin/main` @ `bb79bfb`（#52）；承接已合入 MODEL-API-CONFIG（#43） |
| 不做 | S7；生产收费；客户自建上游 Key；**按权重自动轮询**（多 Key 共存但同时只启用一套）；开另一会话五层对齐分支；密钥入库 |
| 证据总日志 | `/tmp/ops-supplier-key-ux-e2e.log`（须含 `T1_E2E_PASS`…`T5_E2E_PASS` 与汇总 `OPS_SUPPLIER_KEY_UX_E2E_PASS`） |
| 红线 | 不提交真实 Key/口令；不伪造 GPS；不降低默认检测线到擅自值（可配置但默认仍 75）；不直推 `main` |

---

## 0. 背景与裁决

管理员本轮要求相对 MODEL-API-CONFIG / FR-012「第一版单 Key」做**有界扩展**：

1. **多 Key 共存**：同用途登记新 Key **不得覆盖**旧 Key；管理员选择启用哪一套；**不是**原型权重轮询。
2. **提供商级联**：切换提供商时，模型版本改为下拉（选项=当前 Key 实际可调用模型；无 Key 时可用静态目录兜底），Base URL **跟随默认值而非空**。
3. **种子诚实**：当前生图 `gpt-image-2` 不支持种子；前端按合同 `capabilities.seed`：支持则可填，不支持则灰显不可填（后端 `SEED_UNSUPPORTED` 保留）。
4. **检测及格线可配**：Gemini 最终检测通过线在系统管理可设，**仅管理员**；默认 75。
5. **全站样式**：延续 aojuai 底座；圆角卡片分区；按钮 hover 高亮；布局参考 `prototype/`；提交生图/处理、客服/管理员完成工单时弹窗或 toast 提示。

与旧台账 C1「禁止多 Key」冲突：**以本工单管理员裁决为准**（多槽存储 + 单启用；仍禁止自动轮询）。

---

## 1. 任务拆分（子代理执行边界）

### T1 · 提供商切换级联（模型下拉 + Base URL）

| 项 | 内容 |
| --- | --- |
| 范围 | `system-client.tsx` 模型 API 表单；可选 `POST /provider-contracts/probe-models`；`supplier_clients` 默认 URL 目录 |
| 做法 | 提供商 `onChange` → 写入该提供商默认 Base URL；模型字段改为 `<select>`（探活列表优先，失败回落静态 map）；禁止切提供商后 Base URL 变空 |
| 端测 | `T1_E2E_PASS`：切换 DeepSeek/aoju/千问等，Base URL 非空且变化正确；有 Key 时下拉含可调用模型（DeepSeek 临时测试 Key **只读物料文件**，禁止写进 Git） |

### T2 · 同用途多 Key 共存 + 启用同步模型

| 项 | 内容 |
| --- | --- |
| 范围 | `supplier_secrets` / `supplier_config` / `supplier_admin` / ORM+迁移；系统管理已登记渠道表 |
| 做法 | 秘密存储升级为按 duty 的多条目（兼容旧扁平 `duty→string`）；登记=追加；启用某条=该 duty 唯一 enabled，并同步合同 `provider/modelId/baseUrl`；列表展示掩码+启停 |
| 端测 | `T2_E2E_PASS`：同 duty 连续登记 2 条均保留；启用 B 后运行时读 B；旧 A 仍在列表且停用 |

### T3 · 生图种子字段随模型能力

| 项 | 内容 |
| --- | --- |
| 范围 | `generate-client.tsx`；generation 合同 `capabilities.seed`；必要时补合同说明 |
| 做法 | `gpt-image-2` / `gap-not-sent|unsupported` → 种子灰显不可填；支持则开放；后端门禁不删 |
| 端测 | `T3_E2E_PASS`：UI disabled + 强制带 seed 的 API 仍 `SEED_UNSUPPORTED` |

### T4 · 管理员可配 Gemini 检测及格线

| 项 | 内容 |
| --- | --- |
| 范围 | 新平台设置（或合同/设置表）+ 系统管理 UI；`redo_policy.PASS_SCORE` / `gemini_detector` / 任务 payload `passScoreThreshold` / FE 展示 |
| 做法 | 默认 75；仅 admin 可写；商家/客服只读或不可见写入口；改线后新检测任务用新阈值（旧任务报告可保留原快照） |
| 端测 | `T4_E2E_PASS`：admin 改为非 75 后 API/提示对齐；非 admin 403；默认恢复场景可测 |

### T5 · 全站样式 + 任务/工单提示

| 项 | 内容 |
| --- | --- |
| 范围 | `realphotos/**` 主要页面；复用/贴近底座与 `prototype/index.html` 的 card/btn/toast；Sonner 已在 `providers.tsx` |
| 做法 | 内容区块圆角卡片；按钮 hover 高亮；提交生图/处理、tech-desk 完成工单等成功/失败 toast 或对话框（对齐原型密度，勿堆无意义卡片） |
| 端测 | `T5_E2E_PASS`：关键页有卡片/hover class 或截图；至少 2 条用户触发路径有 toast/dialog 证据（源码合同 + 可选浏览器） |

---

## 2. 子代理协作纪律

1. 只在本 worktree / 本分支改代码；**禁止**改 `/home/hbs/hbs-projects/mihuanyuantu-v2` 上五层对齐脏工作区。
2. 密钥：临时 DeepSeek 测试 Key 由主代理写入 **gitignored** `生产物料/realphotos-duty-secrets.json`（或 `.secrets/`）；子代理只读；**禁止**写入工单正文、commit、日志全文。
3. 每任务端测通过后写标记到 `/tmp/ops-supplier-key-ux-e2e.log`；主代理审计前不得宣称整单完成。
4. 不自行 push/PR，除非主代理或管理员另授权。

---

## 3. 完成门槛

| 检查 | 要求 |
| --- | --- |
| T1–T5 | 各自 `_E2E_PASS` |
| 汇总 | `OPS_SUPPLIER_KEY_UX_E2E_PASS` |
| 密钥扫描 | 仓库 diff 无明文 `sk-` 测试 Key |
| 合入 | 仅 PR；非作者 squash；不开 S7 |

缺任一 PASS → 不得标工单完成。
