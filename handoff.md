# 蜜獾原图 v2 · 新会话移交

## 1. 一分钟接手

项目：蜜獾原图 v2（多租户图片资源 + 相机参数处理 + 积分）。

**开工入口（编码工具）**：`docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md`  
必读根目录职责文件：`AGENTS.md`、`handoff.md`（本文件）、`anchor.md`、`checkpoint.md`。  
过程续作权威：`docs/mihuanyuantu-v2/progress.yaml` 的 `next_action` / 阶段状态（本文件与 `checkpoint.md` 只作同步摘要）。

再按需打开现行 PRD、项目架构、生产物料清单、Gemini 方案、`prototype/`。  
不要把离线 HTML 原型或文档齐全误当成后端已上线。

## 2. 权威顺序

1. 产品行为 → `docs/蜜獾原图-v2-PRD-v2.0.md`
2. 落地结构 → `docs/蜜獾原图-v2-项目架构-v1.0.md`
3. 阶段划分与路径 → `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md`

冲突则停并提问。过程技能见 `aidevops/SKILL.md`。

## 3. 位置与版本

| 项 | 路径 / 说明 |
| --- | --- |
| 仓库根 | `AGENTS.md`、`handoff.md`、`anchor.md`、`checkpoint.md`、`aojuai-main/`、`docs/`、`prototype/`、`输入材料/`、`aidevops/` |
| 本功能文档区 | `docs/mihuanyuantu-v2/` |
| 编码指令 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| 底座 | `aojuai-main/`（上游固定版本见 `aojuai-main/UPSTREAM_PIN.txt`） |
| 业务包 | `aojuai-main/backend/app/capabilities/realphotos/` |
| 原型 | `prototype/index.html`；改 `prototype.js` 后跑 `node prototype/sync-inline.js` |
| 分支约定 | 见 `AGENTS.md` §7；后缀保持 `-9973` |
| 密钥 | 仓库忽略 `生产物料/`；需要时只读本机物料，不入库 |

当前实现状态摘要见 `checkpoint.md`。

## 4. 关键导航

| 范围 | 打开 |
| --- | --- |
| 阶段 S0–S7、上线门槛、验证环境 | `docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md` |
| 约束条目 | `anchor.md` |
| 就绪/未就绪事实表 | `checkpoint.md` |
| 协作纪律 | `AGENTS.md` |
| AidevOps 阶段 | `docs/mihuanyuantu-v2/` 下 `progress.yaml` 与阶段 yaml、`wiki.md` |
| 界面约定 | `prototype/README.md` |
| 旧算法/405 预设只读 | `输入材料/旧版可复用模块/` |
| 开发/生产主机与目录登记 | `docs/蜜獾原图-v2-生产物料清单-v1.0.md` |

## 5. 下一步（摘要；以 progress 为准）

- **main 基线**：`origin/main` 已含 S0–S5（S5 squash `d6f4b5d` / #23）。不是生产收费就绪。
- **待合入 PR**：`cursor/ia-page-fix-9973`（含未合入的 S6 运营控制 + 工单 IA-PAGE-2026-11-06 页面/信息架构修复）。PR URL 以 GitHub 当前页为准；合入仅 Owner、非本人作者账号。
- **IA 裁决已落地**：IA_C2 订单/技术客服分角色工作台；IA_C3 生图/URL 仅资源页入口、侧栏清除；IA_C7 订单客服铃铛仅充值通知。冒烟 `/tmp/ia-page-smoke-c2c3c7.txt`。
- **S6**：管理员已结束；证据 `/tmp/s6-pg-e2e.log`；`supplier_connected=false`，`production_billing=false`。不重跑当验收。
- **供应商补测**：`/tmp/supplier-live-e2e.log`；导入未接通；不是生产节点、不是对外检测通过。
- **不得开 S7**；技术失败积分仍 `held_until_tech_support`。
- **协作**：见 `AGENTS.md` §7（功能分支 `-9973`、仅 PR squash 合入 `main`、不得自评自合）。

## 6. 风险提醒

- 原型里的检测替身 ≠ Gemini 真验收；文档齐全 ≠ 后端已交付。
- Cloud 服务端测 ≠ 开发机 PostgreSQL 验收。S2 规则替身检测不等于生产检测通过。
- 租户共用积分是现行产品选择；账号隔离 ≠ 余额隔离。
- 首版 LocalDisk；不要按「必须先买 OSS」开工。
- 客户业务 API ≠ 上游模型 Key 自助 ≠ 外部平台代发；能力名 scope 外接口必须拒绝。
- 菜单 reconcile 后若 live uvicorn 仍吐旧侧栏，需重启 API（见 progress `IA_C6_MENU_CACHE_STALE`）。
- `docs/architecture_decisions/`、`docs/archive/`、待决策清单正文不作为开发指令依据路径；ND-017 现行口径以 PRD **2.10** 为准。

## 7. 新会话粘贴提示词（复制即用）

```text
你是蜜獾原图 v2 的续作 Agent。先按顺序只读、不要改代码：
1) 仓库根 handoff.md、anchor.md、checkpoint.md、AGENTS.md
2) docs/mihuanyuantu-v2/DEV_INSTRUCTIONS.md
3) docs/mihuanyuantu-v2/progress.yaml（以 next_action / 冲突裁决为准）
4) 需要时再读 aidevops/SKILL.md、现行 PRD 2.10、架构 1.7

硬约束：中文回复、标识符英语；不提交真实密钥；不直推/不合并 main；不开 S7；不得自评自合。
当前工作：读 checkpoint §0 与 progress.next_action；找到 cursor/ia-page-fix-9973 的开放 PR 状态；区分「已合入 main / 仅在 PR / 仅有本地证据」。
先用不超过 10 行中文汇报：当前阶段、分支/PR、已证实证据路径、未决冲突、你建议的下一步（等授权再改代码）。
```
