# KEY-MODEL-SET · 工单（2026-11-15）

分支：`cursor/key-model-set-9973`  
基线：`origin/main` @ `cabbd5b`（含 OPS-DESK-UX-FIX #60）  
工作区：`/home/hbs/hbs-projects/mihuanyuantu-v2/.worktrees/ops-desk-ux`  
禁：S7 生产部署、改五层默认 / PASS_SCORE 合同、清空业务数据、自评自合、提交真实密钥。

## T1 模型 API · 按密钥「设置」模型

入口：`/realphotos/system?tab=models`（`system-client.tsx`）

1. 「已登记渠道」列表：在 **Keys / 操作** 相关列，对**每个密钥**新增 **「设置」** 按钮。
2. 点击打开弹窗：可单独选择/填写该密钥使用的 **model**（可复用现有 provider 级联 + `probe-models`）；可选同步 provider/baseUrl 若该密钥已存 meta。
3. **保存**：写入该 `credentialId` 的 meta（`modelId` 等）；若该密钥当前为启用态，同步刷新对应 duty 的 contract 行（`model_id`/`provider`/`base_url`），使生图 / 提示词优化 / 预审 / 最终检测等运行时下次请求立即读到新配置（全站对应模块同步，不改进行中任务快照）。
4. 后端：补最小 API（如 `POST /provider-contracts/credentials` 或等价）+ `supplier_secrets.update_credential_meta`；启用密钥路径已有 `_set_credential_enabled` 可复用镜像逻辑。
5. 单测/脚本：改 disabled key 的 model → enable → 断言 contract/runtime；或改已启用 key → 断言 contract 立即更新。

## T2 上线前全量本地端测

范围：开发机本地（`192.168.19.128` / 本机已部署栈），**非**生产发布（R9/S7 blocked）。

角色：商家 / 订单客服 / 技术客服 / 平台管理员（种子或物料账号）。

必测（含但不限于）：

| 项 | 角色侧重 |
|----|----------|
| 登录 / 注册（验证码） | 商家 |
| 生图 | 商家 |
| 提示词优化 | 商家 |
| 图片处理（含检测） | 商家 |
| 积分充值 | 商家 + 订单客服确认 |
| 账号解冻 / 积分解冻 | 技术客服 |
| API 新增或更换 / 模型更换（含本工单设置） | 管理员 |
| 工单 / 用户管理冒烟 | 技术客服、管理员 |

证据写入 `docs/mihuanyuantu-v2/input/PRELAUNCH-E2E-2026-11-15.txt`（或分角色附件），标记 `PRELAUNCH_E2E_PASS` 或明确 FAIL 项；禁止编造未跑通结论。

## 验收

- T1：UI 可按密钥设置模型并保存；启用密钥变更后 `enabled(duty)` 读到新 model。
- T2：端测清单逐项有证据；失败项可复现说明。
- ruff / 相关 pytest 绿；禁密钥入库。
