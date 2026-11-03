"""Worker 声明与发现：后台常驻进程也要"不安装就不启动"。

## 为什么需要它

`autubuild/scripts/manage.sh` 里三个 worker 的名字是**写死的**：

    start_backend_worker "$branch" "harness_worker" "app.tasks.harness_worker" "AOJU_HARNESS_WORKER_CONCURRENCY"
    start_backend_worker "$branch" "agent_worker"   ...
    start_backend_worker "$branch" "ppt_master_worker" ...

后果有两个，都已经真实发生过：

1. **新模块的 worker 运维侧看不见**——不会被 start，不会被 stop，status 里也没有。
2. **停不干净**：2026-08-09 停 nextjs-plugins 时，`manage.sh stop` 只杀掉了绑端口的
   uvicorn，三个 worker（510 MB）继续在后台空转，因为它们是旁路起的、pid 文件对不上。

所以 worker 必须变成**声明式**的：模块自己声明，基座扫描发现，运维侧读生成出来的清单。
这和能力包（`capability_registry`）是同一套思路，刻意保持一致——
新人学一次"声明 + 发现"就够了。

## 与模块安装状态的关系

worker 归属某个模块（`module_code`）。**模块没装，worker 就不该被发现**——
否则会出现"路由没挂载、菜单没有，但后台有个进程在轮询它的表"这种荒唐状态。
判定复用 `feature_switches.is_module_installed`，与路由挂载用的是同一个判据。

`module_code=None` 表示内核级 worker（比如消息网关重试），任何部署都要有。

## 怎么加一个 worker

在能力包里建 `app/capabilities/<code>/worker.py`，导出 `WORKER`：

    from app.core.worker_registry import WorkerDefinition

    WORKER = WorkerDefinition(
        code="sample_items_sync",
        label="样例条目同步",
        module_code="sample_items",
        task_source_factory="app.capabilities.sample_items.worker:build_task_source",
        default_concurrency=1,
    )

不需要改中央文件，不需要改 manage.sh——清单由 `scripts/export_worker_manifest.py` 生成。
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from functools import lru_cache

from app.core.task_queue import QueuePolicy

WORKER_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# `module:attr` 形式的工厂路径
FACTORY_RE = re.compile(r"^[\w.]+:[\w]+$")


@dataclass(frozen=True, slots=True)
class WorkerDefinition:
    """一个后台常驻 worker 的声明。

    `task_source_factory` 用 `模块路径:函数名` 字符串而不是直接放函数对象——
    这样**发现阶段不需要 import 业务代码**。清单导出、manage.sh 读取都只用到元数据，
    真正 import 发生在 worker 进程自己启动时。模块没装时，那份业务代码根本不会被加载。
    """

    code: str
    label: str
    task_source_factory: str
    module_code: str | None = None
    default_concurrency: int = 1
    max_concurrency: int = 8
    poll_interval: float = 2.0
    #: 队列的交付语义（L0）。DB 队列**应当**声明它——"崩了重跑还是判死"原来是隐式的、
    #: 藏在各自的认领 SQL 里，还能自相矛盾（见 task_queue.py 文件头）。None = 尚未接入 L0 / 不是 DB 队列。
    queue: QueuePolicy | None = None
    description: str = ""

    def validate(self, *, source: str) -> None:
        if not WORKER_CODE_RE.fullmatch(self.code):
            raise ValueError(f"{source}: invalid worker code {self.code!r}")
        if not FACTORY_RE.fullmatch(self.task_source_factory):
            raise ValueError(
                f"{source}: task_source_factory must look like 'package.module:factory', "
                f"got {self.task_source_factory!r}"
            )
        if self.default_concurrency < 1:
            raise ValueError(f"{source}: default_concurrency must be >= 1")
        if self.max_concurrency < self.default_concurrency:
            raise ValueError(f"{source}: max_concurrency must be >= default_concurrency")
        if self.poll_interval <= 0:
            raise ValueError(f"{source}: poll_interval must be > 0")
        if self.queue is not None:
            self.queue.validate(source=f"{source}:{self.code}.queue")

    @property
    def settings_concurrency_key(self) -> str:
        """并发度配置的来源说明（供清单展示）。

        实际取值走 `AOJ_WORKER_CONCURRENCY` 这一个通用映射字段，
        不是每个 worker 一个 Settings 字段——后者等于"加 worker 要改中央文件"。
        """
        return f"AOJ_WORKER_CONCURRENCY[{self.code}]"

    @property
    def module_path(self) -> str:
        return self.task_source_factory.split(":", 1)[0]

    @property
    def factory_name(self) -> str:
        return self.task_source_factory.split(":", 1)[1]


# 内核级 worker：不属于任何可选模块，任何部署都要有。
# 目前为空——基座自带的消息网关重试走的是调度器（app/core/scheduler.py），不是常驻 worker。
# 往这里加东西前先想清楚：它真的每个部署都必须常驻吗？
_BUILTIN_WORKERS: tuple[WorkerDefinition, ...] = ()


def _iter_capability_workers() -> list[WorkerDefinition]:
    """收集各能力包的 `worker.py` 里的 WORKER 声明。

    枚举**委托给 `capability_registry`**，本文件不自己扫 `app.capabilities`——
    内核纯度（GOV-14）只给发现机制开了一个口子，不该为了 worker 再开第二个。
    多一个扫描器也意味着多一处会和能力包目录约定漂移的地方。
    """
    from app.core.capability_registry import discover_capabilities

    found: list[WorkerDefinition] = []
    for capability in discover_capabilities():
        module_name = f"app.capabilities.{capability.code}.worker"
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue  # 能力包没有 worker 是正常的
        definition = getattr(module, "WORKER", None)
        if definition is None:
            continue
        if not isinstance(definition, WorkerDefinition):
            raise TypeError(f"{module_name}.WORKER must be a WorkerDefinition")
        definition.validate(source=module_name)
        found.append(definition)
    return found


@lru_cache(maxsize=1)
def discover_workers() -> tuple[WorkerDefinition, ...]:
    """所有**已声明**的 worker（不过滤安装状态）。"""
    for definition in _BUILTIN_WORKERS:
        definition.validate(source="_BUILTIN_WORKERS")
    workers = list(_BUILTIN_WORKERS) + _iter_capability_workers()
    codes = [item.code for item in workers]
    duplicates = sorted({code for code in codes if codes.count(code) > 1})
    if duplicates:
        raise ValueError(f"duplicate worker codes: {duplicates}")
    return tuple(sorted(workers, key=lambda item: item.code))


def clear_worker_caches() -> None:
    discover_workers.cache_clear()


def installed_workers() -> tuple[WorkerDefinition, ...]:
    """当前部署真正该启动的 worker。

    模块没装就不返回——避免"路由没挂、菜单没有，却有个进程在轮询它的表"。
    """
    from app.core.feature_switches import is_module_installed

    return tuple(
        definition
        for definition in discover_workers()
        if definition.module_code is None or is_module_installed(definition.module_code)
    )


def worker_by_code(code: str) -> WorkerDefinition | None:
    return next((item for item in discover_workers() if item.code == code), None)


def parse_concurrency_map(raw: str | None) -> dict[str, int]:
    """解析 `AOJ_WORKER_CONCURRENCY`，形如 `code:2,other:4`。

    解析失败的条目**静默忽略**而不是抛异常：一个配置项写错不应该让所有 worker 起不来。
    但会返回已解析成功的部分，便于调用方按默认值兜底。
    """
    result: dict[str, int] = {}
    for chunk in str(raw or "").split(","):
        item = chunk.strip()
        if not item or ":" not in item:
            continue
        code, _, value = item.partition(":")
        code = code.strip()
        try:
            parsed = int(value.strip())
        except (TypeError, ValueError):
            continue
        if code and parsed > 0:
            result[code] = parsed
    return result


def resolve_concurrency(definition: WorkerDefinition) -> int:
    """并发度：配置映射优先，否则用声明的默认值，最后按声明的上限收口。

    **上限不能被配置顶穿**——一个 worker 起 50 个槽会把连接池打满，
    而连接池打满的表现是"整个服务变慢"，很难定位回某个 worker 的配置。
    """
    from app.core.config import settings

    configured = parse_concurrency_map(getattr(settings, "AOJ_WORKER_CONCURRENCY", ""))
    value = configured.get(definition.code, definition.default_concurrency)
    return max(1, min(value, definition.max_concurrency))


def build_task_source(definition: WorkerDefinition):
    """按需 import 业务代码并构造 TaskSource。**只有 worker 进程自己会调它**。"""
    module = importlib.import_module(definition.module_path)
    factory = getattr(module, definition.factory_name, None)
    if factory is None:
        raise AttributeError(
            f"worker {definition.code!r}: {definition.module_path} has no {definition.factory_name!r}"
        )
    return factory()
