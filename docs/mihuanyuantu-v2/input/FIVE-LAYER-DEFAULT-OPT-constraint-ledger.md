# FIVE-LAYER-DEFAULT-OPT · 约束账本

日期：2026-11-14  
工单：`FIVE-LAYER-DEFAULT-OPT-work-order-2026-11-14.md`

| ID | 约束 | 状态 |
| --- | --- | --- |
| Q-PASS | `PASS_SCORE=75` 不放宽 | LOCKED |
| Q-HEMO | CA=0、Layer0 img2img 默认 0、Bayer 默认关 | LOCKED |
| Q-RETARGET | 主门禁=`DEFAULT_OPT_MEAN_GAIN`（Δ≥+3）或 `PASS75_LIFT`（+2 张）；旧 Q1 仅 probe | LOCKED |
| Q-ONE-VAR | 消融与升默认必须单变量 | LOCKED |
| Q-NO-ADV | 禁止对抗/武器化 ISP | LOCKED |
| Q-E2E | 真 Gemini；Cloud pytest ≠ 完成 | LOCKED |
| Q-PR | 双账号；squash；不提交密钥 | LOCKED |
| Q12 | 无达标证据不改模块默认常量、不硬开「达标」文案 | LOCKED |
| Q-NO-S7 | 禁止 S7 | LOCKED |

## H0 冻结约定

- 分支：`cursor/five-layer-default-opt-9973`（自含 #55+#56 的 `main`）
- 样本：合同 12、seed=`20261113`、26mm、Layer0 img2img=0、CA=0
- **score_fn=None**（消融主臂；达标候选再另跑 score_fn）
- 证据：`FIVE-LAYER-DEFAULT-OPT-e2e-h0-2026-11-14.txt`
