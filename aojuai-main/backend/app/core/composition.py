"""内核对"业务组合层"的扩展点（回流自 nextjs-plugins 042e9c16 / 14b17607）。

`nextjs-base` 是内核，业务分支在其上叠模块。内核文件里一旦出现业务名，每加一条业务线都要改内核、
且两分支在同一文件上永久冲突。所以：**内核只提供扩展点，业务分支把自己接上去**——
业务分支放一个 `app/plugins/` 包，里面的 `app_wiring` 模块实现下列阶段函数（都可缺省）：

- `install_plugin_routes(app)`、`register_plugin_scheduler_jobs(scheduler)`
- `async run_plugin_startup(app)` / `async run_plugin_after_scheduler(app)` / `async run_plugin_shutdown(app)`
- `translate_plugin_exception(exc) -> AOJUException | None`

纯 base 部署没有 `app/plugins` 包：所有钩子静默跳过。
"""

from __future__ import annotations

from importlib import import_module
from importlib.util import find_spec
from typing import Any

COMPOSITION_PACKAGE = "app.plugins"


def load_composition(module_name: str) -> Any | None:
    """加载组合层下的某个模块；**纯 base 部署**返回 None。

    判据是 `find_spec(COMPOSITION_PACKAGE)`——父包在不在。**不能用 `ModuleNotFoundError.name`**：
    那只说明异常声称缺哪个模块，不能证明是纯 base；组合模块漏打包、`__init__` 加载中抛同名异常、
    `sys.modules` 污染都会被误当成"正常缺席"而吞掉真故障。父包在 → 导入过程中的任何异常都往上抛。
    """
    if find_spec(COMPOSITION_PACKAGE) is None:
        return None
    return import_module(f"{COMPOSITION_PACKAGE}.{module_name}")


def load_app_wiring() -> Any | None:
    return load_composition("app_wiring")


async def run_lifecycle_phase(phase: str, app: Any) -> None:
    """调用组合层的某个异步阶段；纯 base 或该阶段未实现都直接返回。"""
    wiring = load_app_wiring()
    if wiring is None:
        return
    hook = getattr(wiring, phase, None)
    if hook is None:
        return
    await hook(app)


def register_scheduler_jobs(scheduler: Any) -> tuple[str, ...]:
    wiring = load_app_wiring()
    hook = getattr(wiring, "register_plugin_scheduler_jobs", None) if wiring is not None else None
    if hook is None:
        return ()
    return tuple(hook(scheduler) or ())


def install_routes(app: Any) -> None:
    wiring = load_app_wiring()
    hook = getattr(wiring, "install_plugin_routes", None) if wiring is not None else None
    if hook is not None:
        hook(app)


def translate_exception(exc: Exception) -> Any | None:
    """让组合层按清单把底层异常翻成业务异常（AOJUException）；纯 base 返回 None。"""
    wiring = load_app_wiring()
    hook = getattr(wiring, "translate_plugin_exception", None) if wiring is not None else None
    if hook is None:
        return None
    return hook(exc)


def module_code_is_installed(module_path: str) -> bool:
    """`module_path` 所属的业务模块，代码还在磁盘上吗（组合层清单指向已硬卸载模块时应跳过而不是炸）。

    判据借用内核的 `module_code_is_present`；没匹配到任何清单条目的路径一律判为常在（保守方向）。
    """
    from app.core.module_manifest import BUILTIN_MODULE_MANIFESTS, module_code_is_present

    relative = module_path.replace(".", "/")
    for manifest in BUILTIN_MODULE_MANIFESTS:
        for code_path in manifest.code_paths:
            stem = code_path[:-3] if code_path.endswith(".py") else code_path
            if relative == stem or relative.startswith(f"{stem}/"):
                return module_code_is_present(manifest.code)
    return True
