"""硬卸载（code-level uninstall）：删掉模块代码之后，整条链路都要跟着消失。

三种"未安装"里最彻底的一种（对照表见 app/core/module_manifest.py 顶部）：
删掉 `app/domain/speech/` 之后，语音不该出现在模块目录里、不该有开关项，
而且——最容易踩的一条——**应用还得起得来**。

前缀映射是个例外：它**故意保留**卸载掉的模块，否则子域路由会解析不到模块、
被门禁当成公共 API 放行（fail-open，实测过）。留着才拒得掉。
改造前 `app/domain/__init__.py` 与 `alembic/env.py` 都写死了 speech/cms 的
模型 import，删代码等于让整个进程 ModuleNotFoundError。

验证手法：把 `module_manifest.BACKEND_ROOT` 指到一个不存在的目录，
于是所有内置模块的 code_paths 都"查无此物"。

## 这里能证明什么、不能证明什么

**能**：开关链路读得对——目录项消失、`is_module_installed` 为假、
门禁据此拒绝、残留表被 autogenerate 排除。

**不能**：证明"物理删掉之后应用还起得来"。源码一行没少，
`import app.main` 当然成功；而且这样等于**所有模块一起未安装**，
真实场景恰恰是"只卸一个"。实测差距：真删一遍时 15 个模块里只有 1 个起得来，
这里却一直是绿的。

真删探针（nextjs-plugins 的 GOV-22 `hard_uninstall_probe.py`，整树拷贝后 `rm -rf`）
与那边的 15 模块清单强绑定，base 未回流；base 用下面的 speech 真删子进程用例覆盖
"删掉之后应用还起得来"这一条。

必须在子进程里跑：模块一旦 import 就留在 sys.modules 里，
同进程回不到"从未 import"的状态。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.core import module_manifest as mm

BACKEND = Path(__file__).resolve().parents[1]


def _probe(source: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_manifest_declares_every_hard_uninstallable_builtin() -> None:
    """内置能力必须登记物理边界，否则"删代码"这条路对它不成立。

    目录与清单的一一对应由 GOV-18 静态门禁保证（见 governance_tools/
    module_manifest_check.py）；这里只验声明出来的路径确实存在。
    """
    assert mm.BUILTIN_MODULE_MANIFESTS, "清单为空"
    for manifest in mm.BUILTIN_MODULE_MANIFESTS:
        assert manifest.code_paths, f"{manifest.code} 没声明 code_paths"
        assert manifest.model_modules, f"{manifest.code} 没声明 model_modules"
        assert manifest.table_prefixes, f"{manifest.code} 没声明 table_prefixes"
        for relative in manifest.code_paths:
            assert (BACKEND / relative).exists(), f"{manifest.code} 的 {relative} 不存在"


def test_capability_pack_tables_are_never_touched_by_core_autogenerate() -> None:
    """能力包自带迁移链，核心链的 autogenerate 不该看见它们的表。"""
    assert mm.is_unmanaged_table("cap_sample_items") is True
    assert mm.is_unmanaged_table("users") is False


def test_absent_module_tables_are_excluded_from_autogenerate(monkeypatch) -> None:
    """硬卸载后残留表要被 autogenerate 忽略——否则第一次 autogenerate 就 DROP 掉数据。"""
    monkeypatch.setattr(mm, "BACKEND_ROOT", BACKEND / "__no_such_checkout__")

    assert mm.module_code_is_present("speech") is False
    assert set(mm.absent_table_prefixes()) == {"assistant_", "speech_", "cms_"}
    assert mm.is_unmanaged_table("speech_tenant_configs") is True
    # 内核表不受影响：它们不属于任何可卸载模块。
    assert mm.is_unmanaged_table("users") is False


def test_hard_uninstalled_builtin_disappears_and_app_still_boots() -> None:
    """端到端：代码不在 => 目录无此项、开关判定为未安装、应用照常启动。"""
    payload = _probe(
        "import json, sys, pathlib;"
        "import app.core.module_manifest as mm;"
        "mm.BACKEND_ROOT = pathlib.Path('/nonexistent-checkout');"
        "from app.core import feature_switches as fs;"
        "fs.settings.AOJ_ENABLED_MODULES='all';"
        "fs.clear_module_install_caches();"
        "from app.main import app;"
        "biz=[m for m in sys.modules if m.startswith('app.domain.speech')"
        " or m.startswith('app.domain.cms') or m.startswith('app.api.v1.endpoints.cms')];"
        "print(json.dumps({"
        "'catalog': [i['code'] for i in fs.list_module_catalog(include_uninstalled=True)],"
        "'speech_installed': fs.is_module_installed('speech'),"
        "'assistant_installed': fs.is_module_installed('assistant'),"
        "'route_prefixes': [p for p, _ in fs.ROUTE_PREFIX_MODULES],"
        "'permission_prefixes': sorted(fs.PERMISSION_PREFIX_MODULES),"
        "'speech_enabled_for_open_config': fs.is_module_enabled({}, 'speech'),"
        "'routes': len(app.routes),"
        "'loaded_business_modules': biz,"
        "}))"
    )

    assert "speech" not in payload["catalog"]
    assert "public_site" not in payload["catalog"]
    # always_installed 也拦不住硬卸载：代码不在就是不在。
    assert "assistant" not in payload["catalog"]
    assert payload["speech_installed"] is False
    assert payload["assistant_installed"] is False

    # 前缀映射**故意保留**卸载掉的模块——这条曾经断言的是相反的。
    #
    # 把前缀一起摘掉会造成 fail-open：模块的子域（代码在别的目录里、不在它的
    # code_paths）路由仍然挂着，而请求路径解析不到模块，门禁把"解析不到"
    # 当成公共/内核 API 放行。实测过：硬卸载 knowledge_base 之后
    # `/api/v1/documents/*` 还有 11 条路由，归属解析为 None。
    #
    # 现在留在映射里，`is_module_enabled()` 查到未安装直接返回 False，请求被拒。
    # 模块自己的路由本来就没挂载（404），所以留着不会让任何东西多暴露。
    # 详见 GOV-22 的 test_uninstalled_module_prefixes_still_resolve_so_the_gate_can_deny。
    assert "/speech" in payload["route_prefixes"]
    assert "speech" in payload["permission_prefixes"]
    assert payload["speech_enabled_for_open_config"] is False, "前缀留着，但门禁必须拒绝"

    assert payload["loaded_business_modules"] == []
    assert payload["routes"] > 0, "内核路由不该被一起干掉"


def test_partially_missing_code_paths_is_a_broken_deployment_not_an_uninstall(monkeypatch, tmp_path) -> None:
    """三态：全在 = 装着；全不在 = 卸载了；缺一部分 = 部署残缺，必须炸而不是静默当成卸载。

    回流自 nextjs-plugins 373d0ba0：选择性 rsync / 打包裁剪 / 漏提交一个文件，
    以前和干净卸载返回值相同（False），模块悄悄消失、日志一个字没有。
    """
    from app.core import module_manifest as mm

    manifest = mm.MANIFEST_BY_CODE["speech"]
    assert len(manifest.code_paths) >= 2, "该用例需要一个多路径模块"
    root = tmp_path / "backend"
    for rel in manifest.code_paths:
        (root / rel).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(mm, "BACKEND_ROOT", root)
    assert mm.module_code_is_present("speech") is True

    victim = root / manifest.code_paths[0]
    victim.rmdir()
    with pytest.raises(mm.ModuleInstallationBroken) as excinfo:
        mm.module_code_is_present("speech")
    assert excinfo.value.code == "speech"
    assert manifest.code_paths[0] in excinfo.value.missing

    for rel in manifest.code_paths[1:]:
        (root / rel).rmdir()
    assert mm.module_code_is_present("speech") is False, "全部删掉才是硬卸载"
