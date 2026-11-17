# 上线前收尾清单 · 2026-11-17

发布目录：`90e5ad1`（前端 `BUILD_ID=InQPFm3W-gnIE-YvWJqsM`）  
环境：`https://exif-demo.honeybadgersoft.com`（生产 `47.242.28.49`）

## 1. 本轮已完成的界面收尾

| 项 | 结果 |
| --- | --- |
| 登录页「演示账号（点击填入）」区块 | 已删除（含 admin/test 快捷填入） |
| 登录页左上技术标签 | 由 NEURAL NETWORKS / GENERATIVE AI 等改为：电商原图 / 相机参数还原 / EXIF 写入 / 真实性检测 / 批量处理 / 业务 API |
| 登录页主视觉副标题 | `Artificial Intelligence Frontier` → `Photo Authenticity Platform` |
| 登录页卡片标题/正文 | 改为产品说明：真实原图 · 一站生成；三行介绍入库→处理→检测→交付与批量/API 能力 |
| 登录页卡片页脚 | `System Status: Optimal / Live Connected` → `系统状态：正常 / 服务在线` |
| 注册页提示 | 删除「注册将创建独立商家租户与商家岗位，无需租户编码或邀请码。」 |

多语言（zh / en / es）标题与正文同步更新。

## 2. 运行时状态

| 检查 | 结果 |
| --- | --- |
| `realphotos-api/web/process/notify/cleanup` | 全部 `active` |
| `nginx`、`gemini-egress-proxy` | `active` |
| 健康检查 | `health=200`、`login=200` |
| 任务队列 | 无 `SUBMITTED` 残留（DELIVERED 58 / FAILED 13 / PRE_REVIEW_FAILED 5） |
| 作业队列 | 无 `queued` / `running` 残留 |

## 3. 供应商与计费口径（未变更）

| 职责 | 模型 | Base URL | 状态 |
| --- | --- | --- | --- |
| 生成 | gpt-image-2 | apis.aoju.ai | 启用 |
| 提示词优化 | deepseek-flash | api.deepseek.com | 启用 |
| 图片预审 | qwen3-vl-plus | dashscope | 启用 |
| 最终检测 | gemini-2.5-flash | Google Gemini | 启用 |
| 资源导入 | api-image-host | http://47.85.47.252 | **停用**（保持测试前状态） |

`production_billing=false`（按 S7 约定保持关闭，未做任何收费开关变更）。

## 4. 上线前仍需管理员处理

1. **PR #68 合入**：分支 `cursor/s7-prod-deploy-9973` 已推送，作者为 Owner 账号，按双账号纪律需由**非作者**账号审批后合并（squash）。
2. **Gemini API Key 轮换**：此前诊断中该 Key 曾出现在聊天记录，建议在正式上线前轮换并写入 `realphotos-duty-secrets.json`。
3. **出口代理到期**：Xray `gemini-egress-proxy` 节点到期日 2026-12-06，需在此之前续期或迁移。
4. **演示/端测数据清理**（可选）：租户 2 下现有 50 张端测上传图、76 条任务、66 条未读消息；如需干净演示环境可安排清理。

## 5. 已知非阻塞项

- JSON 导入条目必须带 `name`，页面暂未提示；
- 单 worker 顺序处理，50 张约 70 分钟；
- 打开任务详情时会解码原图判断图片锁定（约 100–300ms）。
