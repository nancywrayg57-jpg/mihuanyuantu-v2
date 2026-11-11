"""REMAIN-GAP-PLAN W1 e2e → /tmp/remain-gap-e2e.log

R1 base login bypass closed · R2 asset server pagination.
R9_S7_BLOCKED=true · production_billing=false.
"""

from __future__ import annotations

import asyncio
import io
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image

LOG = Path("/tmp/remain-gap-e2e.log")
REPO = Path(__file__).resolve().parents[3]


def note(msg: str) -> None:
    line = msg.rstrip()
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def must(cond: bool, msg: str) -> None:
    if not cond:
        note(f"FAIL {msg}")
        raise AssertionError(msg)
    note(f"PASS {msg}")


def _jpeg(color=(40, 80, 120)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1280, 960), color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def main() -> int:
    LOG.write_text("", encoding="utf-8")
    from dotenv import load_dotenv

    load_dotenv(REPO / "aojuai-main/backend/.env")

    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401

    from app.capabilities.realphotos.services.bootstrap import DEFAULT_PASSWORD, bootstrap_s0_accounts
    from app.capabilities.realphotos.seed import reconcile
    from app.core.config import settings
    from app.infrastructure.database.session import Base, async_session_factory, engine, init_db
    from app.main import app as fastapi_app

    note(f"remain_gap_w1_e2e start at={datetime.now(UTC).isoformat()}")
    note("R9_S7_BLOCKED=true")
    note("production_billing=false")
    note("R4_NEEDS_ADMIN_CHOICE=true path_A_or_B_unresolved")

    must(str(settings.DB_DIALECT).startswith("postgres"), f"postgresql_required got={settings.DB_DIALECT}")
    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        platform = int(summary["rp_admin"]["tenantId"])
        tenant = int(summary["rp_merchant_a1"]["tenantId"])
        await reconcile(db, tenant_id=platform)
        await reconcile(db, tenant_id=tenant)
        await db.commit()

    flags = {"R1_AUTH_BYPASS_CLOSED_PASS": False, "R2_ASSET_SERVER_PAGE_PASS": False}
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=120.0) as client:
        # R1：底座无 captcha 对商家拒；realphotos 仍通
        bypass = await client.post(
            "/api/v1/auth/login",
            json={"username": "rp_merchant_a1", "password": DEFAULT_PASSWORD},
        )
        must(bypass.status_code == 403, f"r1_bypass_status={bypass.status_code} {bypass.text[:200]}")
        must(bypass.json().get("code") == "AUTH_CAPTCHA_REQUIRED", f"r1_code={bypass.json().get('code')}")
        note("PASS r1_base_login_blocked")

        for role_user in ("rp_order_support", "rp_admin"):
            blocked = await client.post(
                "/api/v1/auth/login",
                json={"username": role_user, "password": DEFAULT_PASSWORD},
            )
            must(blocked.status_code == 403, f"r1_blocked_{role_user}={blocked.status_code}")

        ch = await client.post("/api/v1/realphotos/auth/challenges")
        must(ch.status_code == 200, f"r1_challenge={ch.status_code}")
        data = ch.json()["data"]
        ok = await client.post(
            "/api/v1/realphotos/auth/login",
            json={
                "username": "rp_merchant_a1",
                "password": DEFAULT_PASSWORD,
                "challengeId": data["challengeId"],
                "challengeCode": data["devCode"],
            },
        )
        must(ok.status_code == 200, f"r1_realphotos_login={ok.status_code}")
        merchant = {"Authorization": "Bearer " + ok.json()["data"]["accessToken"]}
        flags["R1_AUTH_BYPASS_CLOSED_PASS"] = True
        note("R1_AUTH_BYPASS_CLOSED_PASS=true")

        # R2：造 >20 张后分页
        for i in range(22):
            up = await client.post(
                "/api/v1/realphotos/assets",
                headers=merchant,
                files={"file": (f"w1-{i}.jpg", _jpeg((i % 160, 50, 90)), "image/jpeg")},
            )
            must(up.status_code == 200, f"r2_upload_{i}={up.status_code}")

        p1 = await client.get("/api/v1/realphotos/assets?page=1&pageSize=20", headers=merchant)
        must(p1.status_code == 200, f"r2_p1={p1.status_code}")
        d1 = p1.json()["data"]
        must(len(d1["items"]) == 20, f"r2_p1_len={len(d1['items'])}")
        must(int(d1["total"]) >= 22, f"r2_total={d1['total']}")
        must(int(d1["pageSize"]) == 20, "r2_page_size")
        p2 = await client.get("/api/v1/realphotos/assets?page=2&pageSize=20", headers=merchant)
        d2 = p2.json()["data"]
        must(len(d2["items"]) >= 2, f"r2_p2_len={len(d2['items'])}")
        ids1 = {item["id"] for item in d1["items"]}
        ids2 = {item["id"] for item in d2["items"]}
        must(ids1.isdisjoint(ids2), "r2_pages_disjoint")
        big = await client.get("/api/v1/realphotos/assets?page=1&pageSize=10000", headers=merchant)
        must(int(big.json()["data"]["pageSize"]) == 100, f"r2_clamp={big.json()['data']['pageSize']}")
        flags["R2_ASSET_SERVER_PAGE_PASS"] = True
        note("R2_ASSET_SERVER_PAGE_PASS=true")

    all_pass = all(flags.values())
    note("R9_S7_BLOCKED=true")
    note("production_billing=false")
    for key, value in flags.items():
        note(f"{key}={'true' if value else 'false'}")
    note(f"REMAIN_GAP_W1_PASS={'true' if all_pass else 'false'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
