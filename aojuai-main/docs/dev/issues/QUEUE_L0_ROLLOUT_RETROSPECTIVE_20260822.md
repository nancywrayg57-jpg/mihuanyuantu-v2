# 队列 L0 落地与两日集中审查复盘（2026-08-21/22）

范围：队列 L0（QueuePolicy/claim_one/租约票据/栅栏）、message_relay 与
course_studio 接入、codex 两日终审 20 条的处置、生产/测试环境部署。
本文只记**可复用的稳定经验**；单次修了什么看 commit 历史。

## 新入库的失败类与护栏

1. **`git apply --3way` 是原子的，逐文件 "Applied cleanly" 是假象。**
   多文件补丁里任何一个文件冲突，整个补丁回滚——但成功文件的日志已经打出来了。
   本轮据此把 i18n key 引用手工搬进组件、语言包却从未落盘，生产界面直接显示
   裸 key（tsc 查不出：参数只是 string）。
   护栏：`tests/test_frontend_i18n_keys.py` 全仓扫描 translateActive 字面量，
   key 必须有注册。**合补丁后必须验内容，不要信 apply 的逐文件输出。**

2. **"单跑绿、全量红"的两类测试污染**（合计二分了十几轮）：
   - 进程级单例 engine 的池化连接跨 pytest 事件循环 → asyncpg
     "attached to a different loop"。护栏：conftest autouse 每测后 dispose。
   - `sys.modules.pop("app.core")` 后重导，新包对象上没有子模块属性，
     此后所有 `monkeypatch.setattr("app.core.x.y", ...)` 全部 AttributeError，
     且**单文件配对无法复现**（多文件组合才触发）。护栏：conftest autouse
     修复父包→子模块属性绑定；肇事测试改 try/finally 原样还原。

3. **公平认领的子查询在 READ COMMITTED 下必然失效**（实测，非理论）：
   看不见并发事务未提交的 running 行，SKIP LOCKED 挡不住（两行无锁冲突）。
   解法是认领前 pg_advisory_xact_lock 串行化。**用 asyncio.gather 测不出
   这个竞态**——协程各自等 IO 时先发者往往已提交；要把一方事务卡在未提交
   状态再让另一方认领，窗口才确定打开。

4. **所有权票据的三个坑**（都被 codex 终审抓出、都已护栏化）：
   进程 ID 当租约标识（同进程多槽接管不可见）→ 每次认领唯一票据；
   比对内存 ORM 值（expire_on_commit=False 下永远是旧值）→ 条件 UPDATE；
   续租/栅栏只保护部分路径 → 终态提交、异常恢复、收口全部带票据条件。

5. **环境操作的三个复发坑**：
   - `pgrep -f` 会匹配到自己的包装 shell（cmdline 里含搜索串），kill 会
     误杀正在执行的命令——先打印 cwd/args 人工确认再 kill 精确 PID。
   - 后台任务只留 `tail -2` 会把多条 FAILED 挤掉，误判失败数量——
     失败清单要 `grep FAILED | sort -u` 全量落盘。
   - 活 worker 会认领测试种进真实库的 queued 行，全量测试与 worker
     并跑必然互相污染——安静窗口跑测试，或接受偶发并复跑确认。

6. **部署链路**（autubuild 实例首次跑通声明式 worker）：
   - 迁移前先 pg_dump 备份（本轮 <db-name> 一次跨一个月的链）。
   - `deploy/workers.json` 声明的 worker 由 manage.sh 拉起；模块未启用时
     worker 拒启是**设计行为**，不是故障。
   - autubuild 的前端 import 审计把 `index.generated` 的 `.generated`
     误判为扩展名（已修 audit_frontend_imports.py）：点分基名不再被报 missing。

## 环境现状（2026-08-22 之后的约定）

- **唯一测试环境：<port>/<port>**（库 <db-name>），前端 next start
  跑 build 产物（不用 dev 模式，省内存）；worker 五个常驻。
- 另一个 nextjs-plugins 实例（<port>/<port>，库 <db-name>）
  平时**停**；其 worktree 与迁移保持可随时拉起。
- 遗留待办集中在任务清单 #116 之后的常规迭代；队列设计文档见
  `docs/dev/reference/TASK_QUEUE_TOP_LEVEL_DESIGN.md`（含实现补记与勘误）。
