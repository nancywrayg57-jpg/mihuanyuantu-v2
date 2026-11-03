from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import v1


def _fake_pack_router() -> APIRouter:
    router = APIRouter()

    @router.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    return router


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("installed", "expected_status", "expected_in_openapi"),
    [
        (False, 404, False),
        (True, 200, True),
    ],
)
async def test_pack_router_is_only_assembled_when_installed(
    monkeypatch: pytest.MonkeyPatch,
    installed: bool,
    expected_status: int,
    expected_in_openapi: bool,
) -> None:
    test_api_router = APIRouter()
    monkeypatch.setattr(v1, "api_router", test_api_router)
    monkeypatch.setattr(v1, "is_module_installed", lambda code: installed and code == "fake_pack")

    registered = v1.register_capability_router(
        "fake_pack",
        _fake_pack_router(),
        prefix="/fake-pack",
        tags=["Fake Pack"],
    )
    app = FastAPI()
    app.include_router(test_api_router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/fake-pack/ping")

    assert registered is installed
    assert response.status_code == expected_status
    assert ("/fake-pack/ping" in app.openapi()["paths"]) is expected_in_openapi


def test_builtin_capability_is_not_imported_when_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """内置能力未安装时，连它的模块都不该被 import。

    改造前：assistant / speech / cms 是顶层 import + 无条件挂载，
    `AOJ_ENABLED_MODULES=none` 只是把菜单藏了，进程里 7 个 CMS 模块照样加载、
    27 条路由照样注册。开关必须是"真的不装"，不是"装了不给看"。

    这条只能在**子进程**里验：模块一旦被 import 就留在 sys.modules 里，
    同进程内没法回到"从未 import"的状态。
    """
    import subprocess
    import sys as _sys
    from pathlib import Path

    probe = (
        "import sys;"
        "from app.core import feature_switches as fs;"
        "fs.settings.AOJ_ENABLED_MODULES='none';"
        "fs.clear_module_install_caches();"
        "import app.api.v1 as v1;"
        # 只数「业务代码」：端点、service、schemas。models 是有意的例外——
        # 它按代码在不在注册（见 app/core/module_manifest.py），
        # 否则同一份 checkout 的 alembic 元数据会随环境变量漂移。
        "allowed={'app.domain.cms','app.domain.cms.models'};"
        "cms=[m for m in sys.modules "
        "if 'cms' in m and m.startswith('app.') and m not in allowed];"
        "print(len(cms), len(v1.api_router.routes))"
    )
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [_sys.executable, "-c", probe],
        cwd=backend,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    loaded, routes = (int(part) for part in result.stdout.split())

    assert loaded == 0, (
        f"未安装 public_site 时仍加载了 {loaded} 个 CMS 业务模块；"
        "多半是有人把它加回了 app/api/v1/__init__.py 的顶层 import"
    )
    assert routes > 0, "内核路由不该被一起干掉"
