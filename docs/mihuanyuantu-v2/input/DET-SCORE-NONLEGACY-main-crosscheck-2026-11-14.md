# DET-SCORE-NONLEGACY · 主会话独立联网交叉核实

日期：2026-11-14  
角色：主会话（Owner）交叉核实；**不替代** R1/R2 子代理全文  
侧聊 §1.3：仅作种子，下列为独立 WebSearch 结论

## 核实摘要

| 种子主张 | 独立核实 | 结论 |
| --- | --- | --- |
| Bayer/CFA 统计可区分真机 vs 生成图 | ICIPW 2025 Bayer one-class；arXiv:2310.16684 局部方差/对角线 Bayer 峰 | **成立**（取证侧） |
| 传感器噪声宜用 Poisson–Gaussian | SamsungLabs unified demosaicing（arXiv:2504.07145）标定 ISO 相关 Poisson–Gaussian；JDD 文献同模型 | **成立**（仿真侧） |
| ISPCloak 全套为对抗武器化 | arXiv:2607.21897 摘要明确 *weaponizing ISP*、*adversarial*、自适应 mask、逃逸检测器 | **红线 REJECT 全套** |
| 弱前馈 mosaicing→噪声→demosaic 可作良性子集 | ISPCloak 管线中「RAW 噪声 + 前向 ISP」物理块与攻击目标可拆；取证文献用 Bayer 作真机签名 | **ALLOW_BENIGN_SUBSET**（无 invertible 攻击网、无自适应逃逸 mask、无梯度） |
| 仅堆 EXIF 不够 | 本仓已有 L4；Gemini 五维主看像素（历史证据） | **辅助保留** |
| 默认开 Layer0/CA | 协议 C/W 已证 CA 伤分；Layer0 未兑现 +10 | **禁止恢复默认** |

## 主会话初判（待与 R1/R2/A 汇合）

| 候选 | 初判 |
| --- | --- |
| 弱 Bayer↔RGB 往返 + 微弱信号噪声 | **试 → 倾向 OPEN_PILOT（测量臂）** |
| 平坦区 Poisson–Gaussian 微调（解耦现有 L1） | **试 → 倾向 OPEN_PILOT（测量臂）** |
| encode/JPEG 温和扫档 | **缓/试**：先测五维是否掉；掉则 DEFER |
| Layer0 测量臂（默认仍 0） | **试测量臂 only**；不改默认 |
| ISPCloak / FPBA / 梯度 camouflage / 改 PASS_SCORE | **禁** |

## 引用

- https://doi.org/10.1109/icipw68931.2025.11386324  
- https://arxiv.org/html/2310.16684  
- https://arxiv.org/html/2504.07145  
- https://arxiv.org/abs/2607.21897  
