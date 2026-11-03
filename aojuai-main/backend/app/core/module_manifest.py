"""内置能力的**硬安装清单**：一个模块的代码、模型、表分别住在哪里。

为什么单独一个文件、且只依赖标准库：
`app/domain/__init__.py` 与 `alembic/env.py` 都要在**模型注册之前**问一句
"这个模块的代码还在吗"。如果它们去 import `feature_switches`，链路会变成
domain → feature_switches → capability_registry → app.capabilities.<x> ——
下游分支（比如 plugins）的能力包 `__init__.py` 只要 import 一次模型，
就会绕回 app.domain，形成半初始化的循环导入。所以这一层保持成叶子模块。

三种"未安装"的区别（BASE_ARCHITECTURE §5.1 有完整表）：

| 层级 | 做法 | 代码 | 路由 | 开关项 | 表 |
|------|------|------|------|--------|----|
| 租户级停用 | feature_switches | 加载 | 挂载 | 显示(关) | 在 |
| 部署级不装 | AOJ_ENABLED_MODULES | 不 import | 不挂载 | 不显示 | 在 |
| 硬卸载 | 删掉 code_paths 里的目录 | 不存在 | 不挂载 | 不显示 | 残留 |

硬卸载后表会残留：内置能力的迁移在核心 alembic 链上，摘掉会撕裂链。
残留表不会被 autogenerate 误删——`alembic/env.py` 用 `absent_table_prefixes()`
把它们排除在比对之外。真要清表，走 `scripts/capability.py db purge`
（能力包）或人工 SQL（内置能力），并且先备份。

能力包（`app/capabilities/<code>/`）不需要在这里登记：它们本来就靠目录扫描
发现，删掉目录就整条消失，迁移链和表也随包走。
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class BuiltinModuleManifest:
    """内置能力的物理边界声明。"""

    code: str
    # 相对 backend/ 的路径。**全部**存在才算装着；任意一个被删就算硬卸载。
    code_paths: tuple[str, ...]
    # 需要注册进 SQLAlchemy 元数据的模型模块（按代码存在与否决定是否 import）。
    model_modules: tuple[str, ...] = field(default_factory=tuple)
    # 该模块拥有的表名前缀。硬卸载后用于把残留表排除出 autogenerate 比对。
    table_prefixes: tuple[str, ...] = field(default_factory=tuple)


BUILTIN_MODULE_MANIFESTS: tuple[BuiltinModuleManifest, ...] = (
    BuiltinModuleManifest(
        code="assistant",
        code_paths=("app/domain/assistant", "app/api/v1/endpoints/assistant.py"),
        model_modules=("app.domain.assistant.config_models", "app.domain.assistant.models"),
        table_prefixes=("assistant_",),
    ),
    BuiltinModuleManifest(
        code="speech",
        code_paths=("app/domain/speech", "app/api/v1/endpoints/speech.py"),
        model_modules=("app.domain.speech.models", "app.domain.speech.voice_clone_models"),
        table_prefixes=("speech_",),
    ),
    BuiltinModuleManifest(
        code="public_site",
        code_paths=(
            "app/domain/cms",
            "app/api/v1/endpoints/cms.py",
            "app/api/v1/endpoints/cms_ai.py",
            "app/api/v1/endpoints/cms_public.py",
        ),
        model_modules=("app.domain.cms.models",),
        table_prefixes=("cms_",),
    ),
)


MANIFEST_BY_CODE: dict[str, BuiltinModuleManifest] = {
    manifest.code: manifest for manifest in BUILTIN_MODULE_MANIFESTS
}

# 能力包的表统一走 cap_ 前缀（`scripts/new_module.py` 强制校验）。它们由各自
# 独立的迁移链管理，核心链的 autogenerate 永远不该碰。
CAPABILITY_TABLE_PREFIX = "cap_"


class ModuleInstallationBroken(RuntimeError):
    """模块的 code_paths **只缺了一部分**——这不是卸载，是部署残缺。

    判据原来是 `all(exists)`：70 条路径里缺 1 条，和干干净净卸载掉整个模块，返回值完全一样
    （都是 False）。后果是**静默的**——那个模块的路由不再挂载、worker 不再启动、菜单里也没有，
    而进程正常运行、日志里一个字都没有；现象是"这个功能昨天还在，今天没了"。

    这类残缺来自现实中的部署方式：选择性 rsync、打包时按目录裁剪、合并冲突后漏提交一个文件、
    `.gitignore` 误伤。真正的硬卸载是删掉整份 `code_paths`，那是运维的明确动作，照常返回 False。

    所以三态分开：全在 = 装着；全不在 = 卸载了；缺一部分 = 部署坏了，立刻炸。
    （回流自 nextjs-plugins 373d0ba0）
    """

    def __init__(self, code: str, missing: tuple[str, ...], total: int) -> None:
        self.code = code
        self.missing = missing
        super().__init__(
            f"模块 {code!r} 的代码残缺：{len(missing)}/{total} 个 code_paths 不存在。\n"
            f"缺失：{', '.join(missing)}\n"
            "这不是硬卸载（硬卸载要删掉全部 code_paths），是部署产物不完整。"
            "请补齐这些文件；确实要卸载该模块就把 code_paths 全部删掉。"
        )


def module_code_is_present(code: str) -> bool:
    """模块代码是否还在磁盘上。未登记的 code 视为常在（内核不可卸载）。

    **只缺一部分会抛 `ModuleInstallationBroken`**，不会悄悄返回 False——理由见那个异常类。
    """
    manifest = MANIFEST_BY_CODE.get(code)
    if manifest is None:
        return True
    missing = [rel for rel in manifest.code_paths if not (BACKEND_ROOT / rel).exists()]
    if not missing:
        return True
    if len(missing) == len(manifest.code_paths):
        return False
    raise ModuleInstallationBroken(code, tuple(missing), len(manifest.code_paths))


def present_manifests() -> tuple[BuiltinModuleManifest, ...]:
    return tuple(m for m in BUILTIN_MODULE_MANIFESTS if module_code_is_present(m.code))


def absent_table_prefixes() -> tuple[str, ...]:
    """已被硬卸载的内置模块的表前缀（残留表，autogenerate 应当忽略）。"""
    return tuple(
        prefix
        for manifest in BUILTIN_MODULE_MANIFESTS
        if not module_code_is_present(manifest.code)
        for prefix in manifest.table_prefixes
    )


def is_unmanaged_table(table_name: str) -> bool:
    """这张表是否不该进入核心链的 autogenerate 比对。

    两类：能力包自管的 cap_*，以及硬卸载后残留的内置模块表。
    """
    name = str(table_name or "")
    if name.startswith(CAPABILITY_TABLE_PREFIX):
        return True
    return any(name.startswith(prefix) for prefix in absent_table_prefixes())


def import_present_model_modules() -> tuple[str, ...]:
    """import 仍然装着的内置模块的模型，返回实际 import 的模块名。

    注意用的是**代码是否存在**、而不是 `AOJ_ENABLED_MODULES`：同一份 checkout
    的元数据必须稳定，否则同一次 autogenerate 会随环境变量给出不同结果。
    部署级开关只决定路由挂不挂载。
    """
    imported: list[str] = []
    for manifest in present_manifests():
        for module_path in manifest.model_modules:
            importlib.import_module(module_path)
            imported.append(module_path)
    return tuple(imported)
