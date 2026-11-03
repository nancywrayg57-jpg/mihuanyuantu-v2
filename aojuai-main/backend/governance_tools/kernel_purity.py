"""GOV-14: 内核不得依赖能力域。

架构文档里最硬的一条判据：**把 app/core 与 app/infrastructure 拷进一个空基座，
应该能直接跑**。它一直只是文字，没有机器验证——而这条线一旦破，四层分工就名存实亡。

允许内核认识的只有"多租户与授权根"这一组：auth / users / roles / menus / teams /
organizations / user_groups。它们不是可选能力，删掉就没法认证和鉴权。
其余一律不许（notifications / operation_logs / cms / speech / assistant / credits /
capabilities / …），需要收尾或联动就由那个模块**主动注册钩子**进来。

## 三种 import 形态怎么判（2026-09 明确）

扫描器按 import 语句所处的**语法位置**分成三类，判法不同：

1. **模块级 import**——最硬的违规。它在 import 期就把能力域拖进内核，
   空基座里连 `import app.core.xxx` 都会炸。一律报错，只能进
   `KERNEL_IMPORT_ALLOWLIST`（整文件豁免，给"发现机制"这种极少数情况）。

2. **`if TYPE_CHECKING:` 块里的 import**——**不算违规，直接跳过**。
   这类 import 运行期根本不执行（配合 `from __future__ import annotations`，
   注解也不求值），空基座里 import 内核模块照样成功；它只是让类型检查器和
   IDE 能看懂签名。把它也判红只会逼着内核把注解退化成 `Any`，
   拿"可读性"换一个并不存在的运行期依赖，不划算。
   注意只跳过 `if TYPE_CHECKING:` 的**主体**；`else:` 分支是运行期代码，照常判。

3. **函数体内的延迟 import（lazy import）**——**默认仍然报错**。
   它确实不构成模块级依赖（能打破 import 环），但 GOV-14 锁的是"内核不许认识
   业务"这条分层判据，不只是"import 期不炸"：延迟 import 只是把同一个依赖推迟到
   调用时，空基座里那个函数一调就 ImportError。历史上被 GOV-14 抓到的
   `core/scheduler.py` 关停飞书长连接，挪进函数体照样是层次倒置。
   所以它需要**逐条**（文件 + 被 import 模块）写进 `KERNEL_LAZY_IMPORT_ALLOWLIST`
   并写明理由，粒度比整文件豁免细：同一个文件里再多一个别的延迟 import 仍会变红。
"""

from __future__ import annotations

import ast
from pathlib import Path

from .common import ScanResult, Violation, require_discovered, validate_allowlist

KERNEL_ROOTS = ("app/core", "app/infrastructure")

# 认证/租户/鉴权根：内核缺了它们无法工作，不算"能力"。
KERNEL_DOMAIN_ALLOWLIST = frozenset(
    {
        "auth",
        "users",
        "roles",
        "menus",
        "teams",
        "organizations",
        "user_groups",
    }
)

# 带原因的显式豁免（**整文件**）。加条目前先问：这真的是"机制"，还是把业务塞进了内核？
KERNEL_IMPORT_ALLOWLIST: dict[str, str] = {
    # 发现机制本身必须知道能力包住在哪个包下才能扫描；它只读 CAPABILITY 声明，
    # 不 import 任何**具体**能力包（那种情况仍会被本规则抓到）。
    "app/core/capability_registry.py": "capability discovery must scan the app.capabilities package",
}

# 函数体内延迟 import 的**逐条**豁免，键是 "<内核文件相对路径>::<被 import 的模块>"。
# 粒度刻意做细：豁免只对这一对生效，同一文件里换一个模块、或把它提到模块级，都仍然变红。
KERNEL_LAZY_IMPORT_ALLOWLIST: dict[str, str] = {
    # ai_client_factory 是"统一 AI client 工厂"，返回值类型就是 assistant 域的
    # OpenAIClient——依赖是真实存在的，不是笔误。它之所以还留在 app/core，是因为
    # aippt / harness / cms_ai 等多个域都要用同一份构造逻辑，放进任何一个域都会变成
    # 域间互相 import。回流提交 6c325130e 把它从模块级改成函数体内延迟 import，
    # 正是为了掐断 core → domain.assistant → …… → core 的 import 环
    # （aippt 顶层 import 本工厂时会绕回来），干净解释器里 import app.core.ai_client_factory
    # 现在可以独立成功。类型注解那份在 `if TYPE_CHECKING:` 下，本规则本来就不计。
    # 后续正解是把 OpenAIClient 下沉到 infrastructure 或改成注册式 provider，
    # 在那之前保留这条**单点**豁免，不要扩大成整文件豁免。
    "app/core/ai_client_factory.py::app.domain.assistant.openai_client": (
        "unified AI client factory is shared by several domains; the lazy import breaks the "
        "core -> domain.assistant import cycle introduced by backflow 6c325130e"
    ),
}


def _domain_of(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) >= 3 and parts[0] == "app" and parts[1] == "domain":
        return parts[2]
    return None


def _capability_import(module: str) -> bool:
    return module == "app.capabilities" or module.startswith("app.capabilities.")


def _is_type_checking_test(test: ast.expr) -> bool:
    """认 `if TYPE_CHECKING:` 与 `if typing.TYPE_CHECKING:` 两种写法。"""
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def _imported_modules(node: ast.stmt) -> list[tuple[str, int]]:
    if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
        return [(node.module, node.lineno)]
    if isinstance(node, ast.Import):
        return [(alias.name, node.lineno) for alias in node.names]
    return []


def collect_runtime_imports(tree: ast.AST) -> tuple[tuple[str, int, bool], ...]:
    """收集运行期会执行的 import：返回 (模块, 行号, 是否在函数体内)。

    `if TYPE_CHECKING:` 的主体整块跳过（`else:` 分支照收）。
    """
    found: list[tuple[str, int, bool]] = []

    def walk(node: ast.AST, *, inside_function: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.If) and _is_type_checking_test(child.test):
                # 只跳过主体；else 分支是运行期代码。
                for orelse in child.orelse:
                    walk_stmt(orelse, inside_function=inside_function)
                continue
            walk_stmt(child, inside_function=inside_function)

    def walk_stmt(node: ast.AST, *, inside_function: bool) -> None:
        modules = _imported_modules(node) if isinstance(node, ast.stmt) else []
        for module, lineno in modules:
            found.append((module, lineno, inside_function))
        nested = inside_function or isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        walk(node, inside_function=nested)

    walk(tree, inside_function=False)
    return tuple(found)


def discover_kernel_files(backend_root: Path) -> tuple[Path, ...]:
    found: list[Path] = []
    for root in KERNEL_ROOTS:
        base = backend_root / root
        if base.is_dir():
            found.extend(sorted(base.rglob("*.py")))
    return tuple(found)


def scan_kernel_purity(
    backend_root: Path,
    *,
    allowlist: dict[str, str] | None = None,
    lazy_allowlist: dict[str, str] | None = None,
) -> ScanResult:
    allowed = KERNEL_IMPORT_ALLOWLIST if allowlist is None else allowlist
    validate_allowlist("GOV-14", allowed)
    allowed_lazy = KERNEL_LAZY_IMPORT_ALLOWLIST if lazy_allowlist is None else lazy_allowlist
    validate_allowlist("GOV-14", allowed_lazy)

    discovered = discover_kernel_files(backend_root)
    require_discovered("GOV-14", discovered, "Python files under app/core and app/infrastructure")

    violations: list[Violation] = []
    for path in discovered:
        relative = path.relative_to(backend_root).as_posix()
        if relative in allowed:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            violations.append(Violation("GOV-14", relative, 0, f"cannot parse Python source: {exc}"))
            continue

        for module, lineno, inside_function in collect_runtime_imports(tree):
            domain = _domain_of(module)
            if domain is not None and domain not in KERNEL_DOMAIN_ALLOWLIST:
                message = (
                    f"kernel imports capability domain '{domain}' ({module}); "
                    "let that module register a hook instead"
                )
            elif _capability_import(module):
                message = f"kernel imports capability package ({module}); capability packages must self-register"
            else:
                continue

            if inside_function:
                if f"{relative}::{module}" in allowed_lazy:
                    continue
                message = (
                    f"{message}; a lazy import inside a function only defers the same dependency "
                    "(the kernel still cannot run standalone) — register a hook, or add "
                    f"'{relative}::{module}' to KERNEL_LAZY_IMPORT_ALLOWLIST with a reason"
                )

            violations.append(Violation("GOV-14", relative, lineno, message))

    return ScanResult(rule="GOV-14", discovered=discovered, violations=tuple(violations))
