# Branch Inheritance Checklist

适用场景：

- `nextjs-base -> nextjs-plugins`
- `nextjs-base -> nextjs-radio`
- `nextjs-plugins -> 其他业务分支`
- 任意下游分支回灌共享底层修复

目标：

- 不漏掉共享内核修复
- 不把业务分支特有代码误灌回基座
- 在 push 前把远端并发提交和本地脏工作区处理干净

## 1. 先做变更分级

每次准备同步前，先把待迁移提交分成三类：

- 共享内核：认证、权限、租户隔离、trusted proxy、分享页、公共序列化、通用 API 层
- 分支特有：某个模块独有的 domain / route / UI / seed / menu
- 文档模板：README、SOP、`.env.production.template`、checklists

规则：

- 只有共享内核和必要文档模板允许跨分支同步
- 分支特有改动必须先确认目标分支确实存在对应模块

## 2. 先查目标分支是否“有这个模块”

同步前先检查目标分支是否真的存在对应代码路径。

最少检查：

- `backend/app/api/v1/endpoints/<module>.py`
- `backend/app/domain/<module>/`
- `frontend/src/lib/api/<module>.ts`
- `frontend/src/app/.../<module>/`
- 对应测试文件

结论规则：

- 文件不存在：判定为“不适用”，不要硬迁移
- 只有部分路径存在：按文件粒度移植，不能整提交照搬

示例：

- `nextjs-plugins` 的 `agents/public-share-groups` 修复不应同步到 `nextjs-base` / `nextjs-radio`，因为这两个分支没有 `agents.py` 与 `domain/agents/service.py`

## 3. 同步认证 / 安全修复时的必查项

涉及下列内容时，必须成套核对：

- `HttpOnly` auth cookie
- `/api/v1/auth/session`
- refresh token 续期
- logout 清理 cookie
- cookie CSRF 防护
- trusted proxy / `x-aoju-proxy-key`
- SSR -> backend 的 `x-forwarded-host`
- 前端 `credentials: 'include'`
- AI 助手 / SSE / 上传下载是否仍绕过统一会话层

如果只迁一半，最容易出现：

- 页面能打开但登录后立即 401
- SSR 页返回 403 / 500
- AI 助手流式接口单独失效
- logout 失效或循环跳登录

## 4. 同步公开分享修复时的必查项

涉及 `share` / `share-groups` / `public-share` 时，至少检查：

- 路由层序列化是否读到了刷新后的对象
- service 层是否会触发懒加载 / expired attribute 问题
- `X-Frame-Options` / CSP 是否放宽到正确路径
- SSR 元数据获取是否会被 trusted proxy 拦截
- 密码校验、访问计数、过期判断是否仍然一致

## 5. 文档模板同步规则

以下文件建议与基座保持一致，再按分支附加补充：

- `README.md`
- `NEXTJS_BASE_MINIMAL_DEPLOY_SOP.md`
- `backend/.env.production.template`
- `backend/README.md`
- `frontend/README.md`
- `devdocs/reference/AUTH_SECURITY_BASELINE.md`
- `devdocs/checklists/README.md`

允许分支保留自己的附加说明：

- 模块特有环境变量
- 模块运行路径
- 特定部署入口
- 特定菜单/路由说明

## 6. 提交前先看工作区

每次操作前先跑：

```bash
git status --short
```

规则：

- 未跟踪的本地工作文件不要误提交
- 如果目标分支已经有用户未提交改动，优先避开这些文件
- 如果必须修改同一文件且冲突风险高，先停下来确认

常见需要排除的内容：

- `agent.md`
- `.artifacts/`
- `.autubuild/`
- 本地 `.env*`

## 7. push 前先处理远端并发提交

推送前固定流程：

```bash
git fetch origin <branch>
git rebase origin/<branch>
git push origin <branch>
```

规则：

- 不要假设远端在你工作期间没有新提交
- 被 fast-forward 拒绝时，先看远端新增内容是否与当前修复冲突
- 无冲突优先 rebase，不要直接强推

## 8. 最小验证集

### 8.1 后端

- `python3 -m compileall backend/app`
- 相关 targeted pytest

### 8.2 前端

- `corepack pnpm build`

### 8.3 共享能力

- 登录
- 刷新后恢复会话
- logout
- 一个受保护页面
- 一个 SSR 公共页面
- 一个公开分享页面
- 一个 AI 助手 / SSE 场景

## 9. 提交信息建议

按内容拆分提交，不要把运行层修复和文档模板混在一起：

- 运行层修复：`Port hardened auth session flow from nextjs-base`
- 文档模板：`Document auth and security baseline for <branch>`
- 模块特定修复：`fix public share group verify serialization`

## 10. 完成后复盘

每次同步结束后记录三件事：

- 哪些修复已被证明是共享内核
- 哪些修复被判定为“不适用”
- 哪些文件最容易在跨分支同步时冲突
