# DET-SCORE-NONLEGACY-LIFT · 约束账本

日期：2026-11-14  
工单：`docs/mihuanyuantu-v2/input/DET-SCORE-NONLEGACY-LIFT-work-order-2026-11-14.md`  
继承：`DET-SCORE-OPTIMIZE` → `FIVE-LAYER-LEGACY-ALIGN`

| ID | 约束 | 状态 |
| --- | --- | --- |
| Q-PASS | `PASS_SCORE=75` 不放宽 | LOCKED |
| Q-HEMO | 止血 A+D+B 为默认底线（Layer0 默认 0、`_CA_INTENSITY=0`、async join）；试点不得无门禁破坏 | LOCKED |
| Q-NO-ADV | 禁止对抗优化 / weaponized ISP 攻击管线入库 | LOCKED |
| Q-NO-LEGACY-LOOP | 禁止以旧 ALIGN 杠杆复跑代替本单研究 | LOCKED |
| Q-E2E | 里程碑完成 = 开发机真 Gemini 证据，非仅 Cloud pytest | LOCKED |
| Q-PR | 双账号；squash；秘密扫描；不提交 `.env` / `生产物料` | LOCKED |
| Q12 | SHORTFALL / 无增益 → 停止加码、不硬开 PR 冒充达标 | LOCKED |
| Q-NO-R4-DEFAULT | R4 测量值禁止升为默认 | LOCKED |
| Q-NO-S7 | 禁止 S7 / 生产部署 | LOCKED |
| Q-GATE | 无 `NONLEGACY_FEASIBILITY_PASS` 不得改 `five_layer` 默认行为 | LOCKED |

## 止血基线冻结（H0）

| 项 | 值 |
| --- | --- |
| 证据 | `DET-SCORE-OPTIMIZE-protocol-c-2026-11-14.txt` |
| 配置 | Layer0=0、CA=0、score_fn 开、26mm、n=12、seed=`20261113` |
| `hemo_baseline` mean_v3 | **66.92** |
| mean_v2 | 65.75 |
| gain_vs_v2 | +1.17（SHORTFALL；非本单达标声明） |
| PR 止血 | https://github.com/nancywrayg57-jpg/mihuanyuantu-v2/pull/55（CI gate pass；待非作者合入） |
