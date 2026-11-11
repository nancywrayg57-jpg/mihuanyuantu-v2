# MODEL-API-CONFIG-2026-11-11 · 约束台账

依据：工单原文、PRD FR-012/FR-030/PG-011、架构 AD-008、`prototype/prototype.js`、AGENTS.md。

## 冲突 / 歧义 / 前置

| ID | 类型 | 原文 | 处理 |
| --- | --- | --- | --- |
| C1 | 冲突 | 原型多 Key 权重轮询 vs PRD FR-012「第一版每职责只启用一套、不轮询」 | **听 PRD**：UI 单 Key；`polling_enabled=false`；不提供第 2+ 槽 |
| C2 | 冲突风险 | FR-030「不记录模型配置」vs 工单审计 | **默认不进用户操作日志**；审计落点=合同行 `updated_at` + 应用日志脱敏字段（工单默认建议） |
| C3 | 硬约束 | `ensure()` 不得覆盖管理员已保存配置 | 仅无行时插种子；已有行不覆盖 provider/modelId/baseUrl/enabled/capabilities 管理员字段 |
| C4 | 跳过 | gpt-image-2 尺寸 / B2-X | 证据 `SKIP_GPT_IMAGE_SIZE=true`；不改 PASS_SCORE |
| C5 | 密钥 | 明文仅保存时写保密存储；响应/日志/Git 禁止全文 | 落盘 `生产物料/realphotos-duty-secrets.json`（gitignore `/生产物料/`）或仓内 `.secrets/`；合同表只存 `keyPrefix` |

## 现状核实（开干时）

- 前端 `system?tab=models`：只读表；链到独立合同页
- `POST /provider-contracts`：仅改 modelId；`apiKey` 现拒绝接收
- `supplier_clients`：硬编码 `GENERATION_BASE` / `DEEPSEEK_URL` / `DASHSCOPE_URL` + `read_material_secret`
- `gemini_detector`：读 `settings.GEMINI_*`，未走合同表
- `ensure()`：对 final_detection/import/generation 仍会改写已有行

## 声明假设

- `[DECLARED]` 删除语义：软删合同行；同 duty 再次保存可新建；ensure 仅在「无未删除行」时插种子。
- `[DECLARED]` 单进程预览保存后立刻生效；多 worker 无 Redis 时证据注明「须滚动重启」诚实口径。
