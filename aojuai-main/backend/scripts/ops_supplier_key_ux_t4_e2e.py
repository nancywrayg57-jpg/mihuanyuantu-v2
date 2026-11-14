"""T4: admin-configurable Gemini detection pass score.

Isolated SQLite. Does not lower the code default PASS_SCORE below 75.
Writes T4_E2E_PASS or T4_E2E_FAIL to /tmp/ops-supplier-key-ux-e2e.log.
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from pathlib import Path

LOG_PATH = Path("/tmp/ops-supplier-key-ux-e2e.log")
BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def note(message: str) -> None:
    line = message.rstrip()
    print(line)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def fail(message: str) -> int:
    note(f"T4_E2E_FAIL {message}")
    return 1


async def _main() -> int:
    from fastapi import FastAPI, Request
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool
    from starlette.responses import JSONResponse

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.api.deps import get_current_user, get_db
    from app.capabilities.realphotos.api import detection_pass_score as score_api
    from app.capabilities.realphotos.models import RealphotosDetectionResult
    from app.capabilities.realphotos.services import gemini_detector
    from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
    from app.capabilities.realphotos.services.detection_pass_score import DetectionPassScoreService
    from app.capabilities.realphotos.services.redo_policy import PASS_SCORE, accepted
    from app.capabilities.realphotos.services.s1_processing import RealphotosS1Service
    from app.core.config import settings
    from app.core.exceptions import AOJUException
    from app.domain.users.models import User
    from app.infrastructure.database.session import Base

    redo_src = (BACKEND / "app/capabilities/realphotos/services/redo_policy.py").read_text(encoding="utf-8")
    if "PASS_SCORE = 75" not in redo_src:
        return fail("code default is no longer PASS_SCORE = 75")
    if PASS_SCORE != 75:
        return fail(f"PASS_SCORE runtime {PASS_SCORE}")

    labels = (ROOT / "aojuai-main/frontend/src/lib/realphotos-labels.ts").read_text(encoding="utf-8")
    system_client = (
        ROOT / "aojuai-main/frontend/src/app/(app)/realphotos/system/system-client.tsx"
    ).read_text(encoding="utf-8")
    card = (
        ROOT / "aojuai-main/frontend/src/app/(app)/realphotos/system/detection-pass-score-card.tsx"
    ).read_text(encoding="utf-8")
    if "DETECTION_PASS_SCORE = 75" not in labels or "passScoreThreshold" not in labels:
        return fail("frontend labels still hard-code the line without the API field")
    if "DetectionPassScoreCard" not in system_client or "passScore" not in card:
        return fail("system page is missing the pass-score card")
    router_src = (BACKEND / "app/capabilities/realphotos/api/__init__.py").read_text(encoding="utf-8")
    if "detection_pass_score" not in router_src:
        return fail("pass-score router is not mounted")

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        users = {
            name: await db.get(User, int(summary[name]["userId"]))
            for name in ("rp_admin", "rp_merchant_a1", "rp_tech_support", "rp_order_support")
        }
        if any(user is None for user in users.values()):
            return fail("bootstrap users missing")

        holder: dict[str, User] = {"user": users["rp_admin"]}

        app = FastAPI()

        @app.exception_handler(AOJUException)
        async def handle_aoju(request: Request, exc: AOJUException):  # noqa: ARG001
            return JSONResponse(
                status_code=exc.status_code,
                content={"success": False, "code": exc.code, "message": exc.message},
            )

        app.include_router(score_api.router, prefix="/api/v1/realphotos")

        async def override_db():
            yield db

        async def override_user():
            return holder["user"]

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[score_api.detection_pass_score_guard] = lambda: None

        path = "/api/v1/realphotos/detection-pass-score"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            default = await client.get(path)
            if default.status_code != 200:
                return fail(f"admin GET default status {default.status_code} {default.text}")
            body = default.json()["data"]
            if int(body["passScore"]) != 75 or int(body["defaultPassScore"]) != 75:
                return fail(f"default payload {body}")
            if "≥ 75" not in str(body["promptLine"]) or "≥ 75" not in gemini_detector.detection_prompt(75):
                return fail("default prompt is not aligned to 75")
            if not body["writable"]:
                return fail("admin GET is not writable")

            holder["user"] = users["rp_merchant_a1"]
            merchant = await client.put(path, json={"passScore": 60})
            if merchant.status_code != 403:
                return fail(f"merchant PUT status {merchant.status_code} {merchant.text}")
            holder["user"] = users["rp_tech_support"]
            tech = await client.put(path, json={"passScore": 60})
            if tech.status_code != 403:
                return fail(f"tech PUT status {tech.status_code} {tech.text}")
            holder["user"] = users["rp_order_support"]
            order = await client.put(path, json={"passScore": 60})
            if order.status_code != 403:
                return fail(f"order-support PUT status {order.status_code} {order.text}")

            holder["user"] = users["rp_admin"]
            still = await client.get(path)
            if int(still.json()["data"]["passScore"]) != 75:
                return fail("non-admin write changed the default")

            raised = await client.put(path, json={"passScore": 80})
            if raised.status_code != 200:
                return fail(f"admin PUT 80 status {raised.status_code} {raised.text}")
            raised_body = raised.json()["data"]
            if int(raised_body["passScore"]) != 80 or "≥ 80" not in str(raised_body["promptLine"]):
                return fail(f"raised payload {raised_body}")
            if "≥ 80" not in gemini_detector.detection_prompt(int(raised_body["passScore"])):
                return fail("detector prompt did not follow the API line")
            if not accepted(passed=True, total_score=80, pass_score=80):
                return fail("accepted() rejected a score on the new line")
            if accepted(passed=True, total_score=79, pass_score=80):
                return fail("accepted() ignored the raised line")

            captured: dict[str, str] = {}
            original_urlopen = gemini_detector.urllib.request.urlopen

            class _Response:
                def __enter__(self) -> _Response:
                    return self

                def __exit__(self, *_args: object) -> bool:
                    return False

                def read(self) -> bytes:
                    report = {
                        "noise": 80,
                        "depthOfField": 80,
                        "lighting": 80,
                        "colorRealism": 80,
                        "overallRealism": 80,
                        "total_score": 80,
                        "passed": True,
                        "reason": "ok",
                    }
                    return json.dumps(
                        {"candidates": [{"content": {"parts": [{"text": json.dumps(report)}]}}]}
                    ).encode()

            def _urlopen(req, timeout=90):  # noqa: ARG001
                captured["body"] = req.data.decode()
                return _Response()

            settings.GEMINI_API_KEY = "unit-test-key"
            settings.GEMINI_MODEL = "gemini-test"
            settings.GEMINI_API_BASE = "https://example.test/v1beta"
            gemini_detector.urllib.request.urlopen = _urlopen
            try:
                report = gemini_detector.detect_jpeg(b"\xff\xd8\xff", pass_score=80)
            finally:
                gemini_detector.urllib.request.urlopen = original_urlopen
            sent = json.loads(captured.get("body") or "{}")
            prompt = str(sent["contents"][0]["parts"][0]["text"])
            if "≥ 80" not in prompt or int(report["passScoreThreshold"]) != 80:
                return fail("detect_jpeg request was not aligned to 80")

            admin_tenant = int(summary["rp_admin"]["tenantId"])
            db.add(
                RealphotosDetectionResult(
                    tenant_id=admin_tenant,
                    task_id=900001,
                    noise=70,
                    depth_of_field=70,
                    lighting=70,
                    color_realism=70,
                    overall_realism=70,
                    total_score=70,
                    passed=False,
                    reason="old-report",
                    detector="gemini-test",
                    pass_score_threshold=75,
                )
            )
            await db.commit()
            payload = await RealphotosS1Service(db).detection_payload(tenant_id=admin_tenant, task_id=900001)
            if payload is None or int(payload["passScoreThreshold"]) != 75:
                return fail(f"old report lost its snapshot {payload}")
            if "75" not in str(payload["platformGateExplanation"]):
                return fail("old report explanation does not keep 75")
            live = await DetectionPassScoreService(db).current()
            if live != 80:
                return fail(f"live line drifted to {live} while checking the old snapshot")

            restored = await client.put(path, json={"passScore": 75})
            if restored.status_code != 200 or int(restored.json()["data"]["passScore"]) != 75:
                return fail(f"restore status {restored.status_code} {restored.text}")
            if int(await DetectionPassScoreService(db).current()) != 75 or PASS_SCORE != 75:
                return fail("restore did not return the live line to 75, or the code default moved")
            if "≥ 75" not in str(restored.json()["data"]["promptLine"]):
                return fail("restored prompt is not aligned to 75")

    await engine.dispose()
    note("T4 admin set 80; prompt and detect_jpeg aligned; non-admin 403; old report kept 75; restored to 75")
    note("T4_E2E_PASS")
    return 0


def main() -> int:
    try:
        return asyncio.run(_main())
    except Exception as exc:  # noqa: BLE001
        note("T4_E2E_FAIL " + "".join(traceback.format_exception_only(type(exc), exc)).strip())
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
